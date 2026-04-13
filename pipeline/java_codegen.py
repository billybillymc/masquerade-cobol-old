"""
Java code generation orchestrator (W8).

Top-level entry point that takes a COBOL program and produces a complete Java
output tree:
  - A buildable Maven module via JavaRenderer.write_module
  - Spring Data repository interfaces via repository_mapper
  - Spring REST controllers + JSR-380 DTOs via api_contract_mapper
  - JUnit 5 test class via test_generator

This is what `analyze.py --target java` would conceptually do, kept as a
standalone script so analyze.py stays focused on parsing/graph building.

Usage:

    python pipeline/java_codegen.py \\
        --codebase test-codebases/carddemo \\
        --program COSGN00C \\
        --output out/java/cosgn00c \\
        --codebase-name carddemo

    # Or for all programs in a codebase:
    python pipeline/java_codegen.py \\
        --codebase test-codebases/carddemo \\
        --output out/java \\
        --codebase-name carddemo
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skeleton_ir import JavaRenderer, spec_to_ir
from spec_generator import generate_program_spec, _load_program_data
from graph_context import GraphIndex
from skeleton_generator import _cobol_name_to_python
from copybook_dict import CopybookDictionary
from repository_mapper import map_cics_repositories, map_sequential_files, generate_repository_code_java, generate_file_reader_code_java
from api_contract_mapper import map_screen_contracts, generate_request_model_code_java, generate_response_model_code_java, generate_route_stub_code_java
from test_generator import generate_test_suite_java


@dataclass
class JavaCodegenResult:
    """Result of generating Java code for a single program."""
    program: str
    module_root: Path
    files_written: list


def generate_java_for_program(
    program_id: str,
    codebase_dir: Path,
    output_dir: Path,
    codebase_name: Optional[str] = None,
    copybook_dict: Optional["CopybookDictionary"] = None,
) -> JavaCodegenResult:
    """Generate the full Java module for one COBOL program.

    Output structure::

        <output_dir>/<program_lower>/
          pom.xml
          src/main/java/com/modernization/<codebase>/<program>/
            Main.java
            dto/<DataClass>.java           ← typed fields from copybooks (GAP 1)
            service/<Stub>.java
            repository/<Repo>.java         ← Spring Data interfaces (GAP 2)
            controller/<Ctrl>Controller.java  ← from BMS screens (GAP 2)
            controller/dto/<Req>Request.java  ← JSR-380 validated (GAP 2)
            controller/dto/<Resp>Response.java

    When ``copybook_dict`` is provided, DTO class bodies are populated with
    typed fields extracted from the copybook PIC clauses. Without it, DTOs
    are empty shells (backward-compatible with the pre-GAP-1 behavior).
    """
    codebase_name = codebase_name or codebase_dir.name
    analysis_dir = codebase_dir / "_analysis"
    if not analysis_dir.exists():
        raise FileNotFoundError(
            f"No _analysis directory at {analysis_dir} — "
            f"run `python pipeline/analyze.py {codebase_dir}` first"
        )

    graph = GraphIndex(str(analysis_dir))
    program_data_all = _load_program_data(analysis_dir)

    spec = generate_program_spec(program_id, graph, program_data_all, str(codebase_dir))
    if spec is None:
        raise ValueError(f"Could not generate spec for program {program_id}")

    # Build copybook dict if not passed (lazy — built once per codebase
    # in generate_java_for_codebase, but one-off callers get it for free).
    if copybook_dict is None:
        try:
            copybook_dict = CopybookDictionary(str(codebase_dir))
        except Exception:
            copybook_dict = None  # graceful degradation: empty DTOs

    # GAP 1: pass copybook_dict so IR dataclasses get real typed fields
    ir = spec_to_ir(spec, copybook_dict=copybook_dict)
    renderer = JavaRenderer()

    module_root = output_dir / _cobol_name_to_python(program_id)
    clean_codebase = codebase_name.lower()
    files = renderer.render_module(ir, codebase=clean_codebase)

    # GAP 2: compose repository interfaces for CICS programs
    pgm_data = program_data_all.get(
        program_id, program_data_all.get(program_id.upper(), {})
    )
    base_pkg = JavaRenderer._java_package(clean_codebase, ir.name)
    pkg_path = base_pkg.replace(".", "/")

    repos = map_cics_repositories(program_id, pgm_data, str(codebase_dir))
    for repo in repos:
        dto_pkg = base_pkg + ".dto"
        repo_pkg = base_pkg + ".repository"
        code = generate_repository_code_java(
            repo, package=repo_pkg, record_package=dto_pkg,
        )
        rel = f"src/main/java/{pkg_path}/repository/{repo.class_name}.java"
        files[rel] = code

    # GAP 2: compose API contract DTOs + controllers for CICS programs
    if spec.program_type == "CICS Online":
        contracts = map_screen_contracts(program_id, str(codebase_dir))
        for contract in contracts:
            ctrl_pkg = base_pkg + ".controller"
            ctrl_dto_pkg = ctrl_pkg + ".dto"
            ctrl_dto_path = f"src/main/java/{pkg_path}/controller/dto"

            req_code = generate_request_model_code_java(
                contract, package=ctrl_dto_pkg,
            )
            files[f"{ctrl_dto_path}/{contract.request_class}.java"] = req_code

            resp_code = generate_response_model_code_java(
                contract, package=ctrl_dto_pkg,
            )
            files[f"{ctrl_dto_path}/{contract.response_class}.java"] = resp_code

            route_code = generate_route_stub_code_java(
                contract, package=ctrl_pkg, dto_package=ctrl_dto_pkg,
            )
            controller_name = contract.request_class.replace("Request", "") + "Controller"
            files[f"src/main/java/{pkg_path}/controller/{controller_name}.java"] = route_code

    # Sequential file readers/writers for batch programs
    seq_files = map_sequential_files(program_id, pgm_data)
    for seq in seq_files:
        io_pkg = base_pkg + ".io"
        code = generate_file_reader_code_java(seq, package=io_pkg)
        rel = f"src/main/java/{pkg_path}/io/{seq.class_name}.java"
        files[rel] = code

    # JUnit 5 test class
    test_pkg = base_pkg
    test_code = generate_test_suite_java(
        spec, program_data=pgm_data,
        package=test_pkg, main_class="Main",
    )
    test_class_name = ir.main_class + "Test"
    files[f"src/test/java/{pkg_path}/{test_class_name}.java"] = test_code

    # Write all files to disk
    written = []
    for rel_path, contents in files.items():
        full_path = module_root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(contents, encoding="utf-8")
        written.append(str(full_path))

    return JavaCodegenResult(
        program=program_id,
        module_root=module_root,
        files_written=written,
    )


def generate_java_for_codebase(
    codebase_dir: Path,
    output_dir: Path,
    codebase_name: Optional[str] = None,
) -> dict:
    """Generate Java modules for every program in a codebase."""
    codebase_name = codebase_name or codebase_dir.name
    analysis_dir = codebase_dir / "_analysis"
    if not analysis_dir.exists():
        raise FileNotFoundError(
            f"No _analysis directory at {analysis_dir} — "
            f"run `python pipeline/analyze.py {codebase_dir}` first"
        )

    graph = GraphIndex(str(analysis_dir))
    results = {}
    failures = {}

    # Build copybook dict once for the whole codebase (avoids re-parsing
    # .cpy files for every program).
    try:
        cbd = CopybookDictionary(str(codebase_dir))
    except Exception:
        cbd = None

    for program_id in sorted(graph.program_names()):
        try:
            result = generate_java_for_program(
                program_id,
                codebase_dir,
                output_dir,
                codebase_name,
                copybook_dict=cbd,
            )
            results[program_id] = result
        except Exception as e:
            failures[program_id] = f"{type(e).__name__}: {e}"

    return {"results": results, "failures": failures}


# ── CLI ────────────────────────────────────────────────────────────────────


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Java reimplementation skeletons (Maven modules) for one "
            "COBOL program or an entire codebase. Produces the same structural "
            "output as the Python skeleton generator but as buildable Java."
        ),
    )
    parser.add_argument(
        "--codebase",
        required=True,
        help="Path to the COBOL codebase root (must already have _analysis/)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for the generated Maven modules",
    )
    parser.add_argument(
        "--program",
        help="Generate only this COBOL program (omit to generate all programs)",
    )
    parser.add_argument(
        "--codebase-name",
        help="Override the codebase name used in the Java package "
             "(defaults to the directory basename)",
    )
    args = parser.parse_args(argv)

    codebase_dir = Path(args.codebase).resolve()
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.program:
        try:
            result = generate_java_for_program(
                args.program,
                codebase_dir,
                output_dir,
                args.codebase_name,
            )
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2
        print(f"Generated Java module for {result.program}:")
        print(f"  Module root: {result.module_root}")
        print(f"  Files: {len(result.files_written)}")
        return 0

    summary = generate_java_for_codebase(
        codebase_dir,
        output_dir,
        args.codebase_name,
    )
    successes = summary["results"]
    failures = summary["failures"]

    print(f"Generated {len(successes)} Java modules under {output_dir}")
    if failures:
        print(f"\n{len(failures)} failures:", file=sys.stderr)
        for pgm, err in failures.items():
            print(f"  {pgm}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
