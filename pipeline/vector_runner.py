"""
Language-agnostic runner contract for the differential harness.

The differential harness in `differential_harness.py` is a pure comparator —
it takes `DiffVector` objects with `actual_outputs` already populated and
reports field-by-field equivalence. It does NOT know how to invoke a
reimplementation to produce those actuals.

This module fills that gap. It defines:

  1. A `Runner` interface that takes a `RunRequest` (program + vector_id +
     inputs) and returns a `RunResponse` (vector_id + outputs + errors).
  2. `PythonRunner` — dynamically loads a Python reimpl module and calls a
     conventional `run_vector(inputs: dict) -> dict` entry point.
  3. `JavaRunner` — shells out to the Java fat-runner JAR with the same JSON
     contract over stdin/stdout. Used by Java reimplementations once they exist.
  4. `populate_actuals(vectors, runner)` — convenience helper that fills in the
     `actual_outputs` field on each vector in place using the chosen runner.
  5. A small CLI: `python vector_runner.py --program <P> --vectors <path>
     --runner [python|java]` that runs a program through the harness end-to-end.

JSON I/O contract (the same shape both runners speak):

    Request:  {"program": "COSGN00C", "vector_id": "V001",
               "inputs":  {"USERID": "ADMIN001", "PASSWD": "PASS1234"}}

    Response: {"vector_id": "V001",
               "outputs": {"XCTL_TARGET": "COADM01C", "ERROR_MSG": ""},
               "errors":  []}

This contract is the single source of truth for what a "reimplementation" is
expected to look like from the harness's perspective. Both Python and Java
targets must produce byte-identical outputs for byte-identical inputs to clear
the differential gate.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Contract data model ────────────────────────────────────────────────────


@dataclass
class RunRequest:
    """A single invocation request: feed these inputs into this program."""
    program: str
    vector_id: str
    inputs: dict


@dataclass
class RunResponse:
    """The runner's reply: what the program produced for this vector."""
    vector_id: str
    outputs: dict
    errors: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_json(self) -> str:
        return json.dumps({
            "vector_id": self.vector_id,
            "outputs": self.outputs,
            "errors": self.errors,
        })

    @classmethod
    def from_json(cls, raw: str) -> "RunResponse":
        data = json.loads(raw)
        return cls(
            vector_id=data.get("vector_id", ""),
            outputs=data.get("outputs", {}),
            errors=data.get("errors", []),
        )


# ── Runner interface ───────────────────────────────────────────────────────


class Runner(ABC):
    """Abstract runner: produces actual_outputs for a vector regardless of language."""

    @abstractmethod
    def run(self, request: RunRequest) -> RunResponse:
        ...

    def name(self) -> str:
        return self.__class__.__name__


# ── PythonRunner ───────────────────────────────────────────────────────────


class PythonRunner(Runner):
    """Runs a Python reimpl via its conventional `run_vector` entry point.

    Convention: each reimpl module under `pipeline/reimpl/` (or
    `pipeline/reimpl/python/` once the directory split lands) exposes::

        def run_vector(inputs: dict) -> dict:
            ...

    The PythonRunner loads the module by program name, calls `run_vector`, and
    captures any error so the harness can report it instead of crashing.
    """

    def __init__(self, reimpl_root: Optional[Path] = None):
        # Default discovery: pipeline/reimpl/<program>.py with a fallback to
        # pipeline/reimpl/python/<program>.py for the post-split layout.
        self.reimpl_root = reimpl_root or (
            Path(__file__).resolve().parent / "reimpl"
        )

    def _load_module(self, module_path: Path, request: RunRequest):
        """Load a reimpl module with package context where possible.

        Preferred: ``importlib.import_module("<pkg>.<module>")`` with the
        parent directory on ``sys.path``. Needed so relative imports
        (``from .carddemo_data import ...``) resolve.

        Fallback: ``spec_from_file_location`` for stub modules in
        tmp_path test fixtures that don't live under a real package.

        Returns the loaded module on success, or a :class:`RunResponse`
        carrying the error.
        """
        pkg_dir = module_path.parent          # e.g. pipeline/reimpl
        parent_dir = pkg_dir.parent           # e.g. pipeline
        package_name = pkg_dir.name            # e.g. reimpl
        module_stem = module_path.stem          # e.g. cbact04c
        full_name = f"{package_name}.{module_stem}"

        # Prefer package-based import when the module lives under a
        # normal-looking package directory (name is a valid identifier).
        if package_name.isidentifier() and parent_dir.exists():
            if str(parent_dir) not in sys.path:
                sys.path.insert(0, str(parent_dir))
            # Evict any cached version so repeat runs pick up edits
            if full_name in sys.modules:
                del sys.modules[full_name]
            try:
                return importlib.import_module(full_name)
            except ImportError:
                # Package-style import didn't work — fall through to
                # the file-based loader so the test fixtures using
                # tmp_path with non-package dirs still function.
                pass
            except Exception as e:
                return RunResponse(
                    vector_id=request.vector_id,
                    outputs={},
                    errors=[f"PythonRunner: import failed: {type(e).__name__}: {e}"],
                )

        # File-based fallback
        spec_name = f"_runner_reimpl_{request.program.lower()}"
        spec = importlib.util.spec_from_file_location(spec_name, module_path)
        if spec is None or spec.loader is None:
            return RunResponse(
                vector_id=request.vector_id,
                outputs={},
                errors=[f"PythonRunner: unable to build module spec for {module_path}"],
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            return RunResponse(
                vector_id=request.vector_id,
                outputs={},
                errors=[f"PythonRunner: import failed: {type(e).__name__}: {e}"],
            )
        return module

    def _resolve_module_path(self, program: str) -> Optional[Path]:
        """Find the Python reimpl module file for a program ID.

        Resolution order:
          1. Exact match: ``<program_lower>.py``
          2. Post-split layout: ``python/<program_lower>.py``
          3. Codebase-prefixed: ``<prefix>_<program_lower>.py`` — handles
             files like ``cbsa_dbcrfun.py`` where the codebase name is
             encoded in the filename. Strict suffix match: only files
             where the last underscore-separated segment equals the
             program name will be picked.

        Returns the path of the first match, or None.
        """
        module_name = program.lower()

        # 1 + 2: exact match candidates
        candidates = [
            self.reimpl_root / f"{module_name}.py",
            self.reimpl_root / "python" / f"{module_name}.py",
        ]
        for path in candidates:
            if path.exists():
                return path

        # 3: codebase-prefixed match — scan the reimpl root for any file
        # whose stem ends in `_<program_lower>` (e.g., cbsa_dbcrfun.py).
        if self.reimpl_root.exists():
            for entry in sorted(self.reimpl_root.glob(f"*_{module_name}.py")):
                # Strict suffix match: stem split by '_' must end with module_name
                parts = entry.stem.split("_")
                if parts and parts[-1] == module_name:
                    return entry

        return None

    def run(self, request: RunRequest) -> RunResponse:
        module_path = self._resolve_module_path(request.program)
        if module_path is None:
            return RunResponse(
                vector_id=request.vector_id,
                outputs={},
                errors=[f"PythonRunner: reimpl module not found for {request.program}"],
            )

        # Load the module with a package context so relative imports like
        # `from .carddemo_data import ...` in cbact04c.py resolve correctly.
        # Strategy: put the *parent of the reimpl dir* on sys.path, then use
        # importlib.import_module("<package>.<module>"). Falls back to
        # spec_from_file_location only if the package import fails, which
        # covers the test-fixture cases using tmp_path with stub modules
        # that don't live under a real package.
        module = self._load_module(module_path, request)
        if isinstance(module, RunResponse):
            return module  # error already wrapped

        if not hasattr(module, "run_vector"):
            return RunResponse(
                vector_id=request.vector_id,
                outputs={},
                errors=[
                    f"PythonRunner: {request.program} does not define "
                    f"run_vector(inputs: dict) -> dict"
                ],
            )

        try:
            outputs = module.run_vector(request.inputs)
        except Exception as e:
            return RunResponse(
                vector_id=request.vector_id,
                outputs={},
                errors=[f"PythonRunner: run_vector raised {type(e).__name__}: {e}"],
            )

        if not isinstance(outputs, dict):
            return RunResponse(
                vector_id=request.vector_id,
                outputs={},
                errors=[
                    f"PythonRunner: run_vector returned {type(outputs).__name__}, "
                    f"expected dict"
                ],
            )

        # Coerce all values to strings to keep the cross-language contract
        # symmetric (Java's JSON output will arrive as strings too).
        normalized = {k: ("" if v is None else str(v)) for k, v in outputs.items()}

        return RunResponse(
            vector_id=request.vector_id,
            outputs=normalized,
            errors=[],
        )


# ── JavaRunner ─────────────────────────────────────────────────────────────


class JavaRunner(Runner):
    """Runs a Java reimpl by shelling out to the Masquerade Java runner JAR.

    The JAR (built later, see W3/W6) is expected to:
      1. Read a JSON RunRequest from stdin
      2. Dispatch to the right `com.modernization.masquerade...` program class
      3. Write a JSON RunResponse to stdout
      4. Exit 0 on success, non-zero on hard failure

    Until the JAR exists this runner returns a clear error so callers can
    distinguish "Java runner not built yet" from "Java runner ran but produced
    wrong output". The happy-path code is fully written so the moment the JAR
    appears at `pipeline/reimpl/java/runner/target/masquerade-runner.jar` it
    Just Works without further plumbing in this module.
    """

    DEFAULT_JAR_PATH = (
        Path(__file__).resolve().parent
        / "reimpl" / "java" / "runner" / "target" / "masquerade-runner.jar"
    )

    def __init__(
        self,
        jar_path: Optional[Path] = None,
        java_bin: str = "java",
        timeout_seconds: float = 30.0,
    ):
        self.jar_path = Path(jar_path) if jar_path else self.DEFAULT_JAR_PATH
        self.java_bin = java_bin
        self.timeout_seconds = timeout_seconds

    def run(self, request: RunRequest) -> RunResponse:
        if not self.jar_path.exists():
            return RunResponse(
                vector_id=request.vector_id,
                outputs={},
                errors=[
                    f"JavaRunner: runner JAR not found at {self.jar_path}. "
                    "Build the Java pilot first (W6) or pass --jar to override."
                ],
            )

        request_json = json.dumps({
            "program": request.program,
            "vector_id": request.vector_id,
            "inputs": request.inputs,
        })

        try:
            proc = subprocess.run(
                [self.java_bin, "-jar", str(self.jar_path)],
                input=request_json,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError:
            return RunResponse(
                vector_id=request.vector_id,
                outputs={},
                errors=[
                    f"JavaRunner: '{self.java_bin}' not found on PATH. "
                    "Install JDK 17 or pass --java-bin."
                ],
            )
        except subprocess.TimeoutExpired:
            return RunResponse(
                vector_id=request.vector_id,
                outputs={},
                errors=[f"JavaRunner: process timed out after {self.timeout_seconds}s"],
            )

        if proc.returncode != 0:
            return RunResponse(
                vector_id=request.vector_id,
                outputs={},
                errors=[
                    f"JavaRunner: exit {proc.returncode}: {proc.stderr.strip()[:500]}"
                ],
            )

        try:
            response = RunResponse.from_json(proc.stdout)
        except json.JSONDecodeError as e:
            return RunResponse(
                vector_id=request.vector_id,
                outputs={},
                errors=[f"JavaRunner: invalid JSON on stdout: {e}"],
            )

        # Java runner may not echo vector_id back (defensive default).
        if not response.vector_id:
            response.vector_id = request.vector_id
        return response


# ── Orchestration helpers ──────────────────────────────────────────────────


def populate_actuals(vectors: list, runner: Runner) -> list:
    """Run each vector through the runner, populating `actual_outputs` in place.

    Vectors that fail to run get an empty actual_outputs and a runner error
    in the return list. The differential harness will then report all expected
    fields as missing for those vectors, which is the right behavior — a hard
    failure should look like total mismatch, not silent skip.

    Returns the (mutated) vector list for chaining.
    """
    for vec in vectors:
        request = RunRequest(
            program=vec.program,
            vector_id=vec.vector_id,
            inputs=vec.inputs,
        )
        response = runner.run(request)
        vec.actual_outputs = response.outputs
        # If we want to expose runner errors to the caller in the future, this
        # is the place to attach them. For now they're inferable from
        # actual_outputs being empty (treated by the comparator as missing).
    return vectors


def make_runner(name: str, **kwargs) -> Runner:
    """Factory: build a runner by name. Used by the CLI and tests."""
    name = name.lower()
    if name == "python":
        return PythonRunner(**kwargs)
    if name == "java":
        return JavaRunner(**kwargs)
    raise ValueError(f"unknown runner: {name!r} (expected 'python' or 'java')")


# ── CLI ────────────────────────────────────────────────────────────────────


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a program's golden vectors through the differential harness "
            "via the language-agnostic runner contract."
        ),
    )
    parser.add_argument("--program", required=True, help="COBOL program ID, e.g. COSGN00C")
    parser.add_argument("--vectors", required=True, help="Directory containing <program>.json vector file")
    parser.add_argument(
        "--runner",
        choices=["python", "java"],
        default="python",
        help="Which target language to invoke (default: python)",
    )
    parser.add_argument("--jar", help="Override Java runner JAR path (java runner only)")
    parser.add_argument("--java-bin", default="java", help="Override java executable")
    args = parser.parse_args(argv)

    # Imported lazily so the CLI doesn't pay for harness imports unless used.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from differential_harness import load_golden_vectors, run_vectors, render_report_text

    runner_kwargs = {}
    if args.runner == "java":
        if args.jar:
            runner_kwargs["jar_path"] = Path(args.jar)
        runner_kwargs["java_bin"] = args.java_bin
    runner = make_runner(args.runner, **runner_kwargs)

    vectors = load_golden_vectors(args.program, args.vectors)
    if not vectors:
        print(
            f"No vectors found for program {args.program} at {args.vectors}",
            file=sys.stderr,
        )
        return 2

    populate_actuals(vectors, runner)
    report = run_vectors(vectors)
    print(render_report_text(report))
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
