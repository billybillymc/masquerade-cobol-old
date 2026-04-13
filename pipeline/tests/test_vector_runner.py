"""Tests for pipeline/vector_runner.py — the language-agnostic runner contract.

These tests do NOT depend on GnuCOBOL or WSL. They exercise the runner contract
itself: PythonRunner against the COSGN00C reimpl, JavaRunner failure modes, the
end-to-end orchestration through populate_actuals + run_vectors, and the CLI
factory.

The Python differential test in test_differential_cosgn00c.py uses the same
COSGN00C reimpl but goes through GnuCOBOL — these tests are the runner's
self-check, not a replacement for that.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from differential_harness import DiffVector, run_vectors
from vector_runner import (
    JavaRunner,
    PythonRunner,
    RunRequest,
    RunResponse,
    Runner,
    make_runner,
    populate_actuals,
)


# ── PythonRunner against the real COSGN00C reimpl ──────────────────────────


class TestPythonRunnerCosgn00c:
    """PythonRunner drives the COSGN00C reimpl through its run_vector adapter."""

    def setup_method(self):
        self.runner = PythonRunner()

    def test_admin_login_succeeds(self):
        response = self.runner.run(RunRequest(
            program="COSGN00C",
            vector_id="ADMIN_LOGIN",
            inputs={"USERID": "ADMIN001", "PASSWD": "PASS1234"},
        ))
        assert response.ok, response.errors
        assert response.outputs["XCTL_TARGET"] == "COADM01C"
        assert response.outputs["HAS_COMMAREA"] == "Y"
        assert response.outputs["ERROR_MSG"] == ""

    def test_regular_user_login_succeeds(self):
        response = self.runner.run(RunRequest(
            program="COSGN00C",
            vector_id="USER_LOGIN",
            inputs={"USERID": "USER0001", "PASSWD": "MYPASSWD"},
        ))
        assert response.ok
        assert response.outputs["XCTL_TARGET"] == "COMEN01C"
        assert response.outputs["HAS_COMMAREA"] == "Y"
        assert response.outputs["ERROR_MSG"] == ""

    def test_wrong_password_returns_error_message(self):
        response = self.runner.run(RunRequest(
            program="COSGN00C",
            vector_id="WRONG_PWD",
            inputs={"USERID": "ADMIN001", "PASSWD": "WRONGPWD"},
        ))
        assert response.ok
        assert response.outputs["XCTL_TARGET"] == ""
        assert response.outputs["HAS_COMMAREA"] == "N"
        assert response.outputs["ERROR_MSG"] == "Wrong Password"

    def test_unknown_user_returns_not_found(self):
        response = self.runner.run(RunRequest(
            program="COSGN00C",
            vector_id="NOT_FOUND",
            inputs={"USERID": "UNKNOWN1", "PASSWD": "ANYTHING"},
        ))
        assert response.ok
        assert response.outputs["ERROR_MSG"] == "User not found"

    def test_outputs_are_string_normalized(self):
        """Cross-language contract: every output value must be a string."""
        response = self.runner.run(RunRequest(
            program="COSGN00C",
            vector_id="ADMIN_LOGIN",
            inputs={"USERID": "ADMIN001", "PASSWD": "PASS1234"},
        ))
        for key, val in response.outputs.items():
            assert isinstance(val, str), f"{key} is {type(val).__name__}, not str"


# ── PythonRunner failure modes ─────────────────────────────────────────────


class TestPythonRunnerErrors:
    """PythonRunner must report failures clearly instead of crashing."""

    def test_missing_program_returns_error(self):
        runner = PythonRunner()
        response = runner.run(RunRequest(
            program="NOPE_NOT_REAL",
            vector_id="V001",
            inputs={},
        ))
        assert not response.ok
        assert "not found" in response.errors[0].lower()
        assert response.outputs == {}

    def test_module_without_run_vector_returns_error(self, tmp_path):
        # Drop a stub module that doesn't define run_vector
        stub = tmp_path / "stubprog.py"
        stub.write_text("X = 42\n", encoding="utf-8")

        runner = PythonRunner(reimpl_root=tmp_path)
        response = runner.run(RunRequest(
            program="STUBPROG",
            vector_id="V001",
            inputs={},
        ))
        assert not response.ok
        assert "run_vector" in response.errors[0]

    def test_run_vector_exception_is_captured(self, tmp_path):
        stub = tmp_path / "boomprog.py"
        stub.write_text(
            "def run_vector(inputs):\n"
            "    raise ValueError('intentional')\n",
            encoding="utf-8",
        )

        runner = PythonRunner(reimpl_root=tmp_path)
        response = runner.run(RunRequest(
            program="BOOMPROG",
            vector_id="V001",
            inputs={},
        ))
        assert not response.ok
        assert "ValueError" in response.errors[0]
        assert "intentional" in response.errors[0]

    def test_run_vector_must_return_dict(self, tmp_path):
        stub = tmp_path / "wrongtype.py"
        stub.write_text(
            "def run_vector(inputs):\n"
            "    return 'not a dict'\n",
            encoding="utf-8",
        )

        runner = PythonRunner(reimpl_root=tmp_path)
        response = runner.run(RunRequest(
            program="WRONGTYPE",
            vector_id="V001",
            inputs={},
        ))
        assert not response.ok
        assert "expected dict" in response.errors[0]


# ── JavaRunner stub behavior ───────────────────────────────────────────────


class TestJavaRunnerStub:
    """JavaRunner gracefully reports the missing JAR until W6 builds it."""

    def test_missing_jar_returns_clear_error(self, tmp_path):
        nonexistent_jar = tmp_path / "does-not-exist.jar"
        runner = JavaRunner(jar_path=nonexistent_jar)
        response = runner.run(RunRequest(
            program="COSGN00C",
            vector_id="V001",
            inputs={"USERID": "ADMIN001", "PASSWD": "PASS1234"},
        ))
        assert not response.ok
        assert "JAR not found" in response.errors[0]
        assert response.outputs == {}

    def test_default_jar_path_points_to_pilot_location(self):
        runner = JavaRunner()
        # The path is just a contract — the JAR doesn't exist yet, but the
        # location it would live at must be stable.
        assert runner.jar_path.name == "masquerade-runner.jar"
        assert "java" in str(runner.jar_path)


# ── End-to-end through populate_actuals + differential harness ─────────────


class TestEndToEndOrchestration:
    """populate_actuals + run_vectors should reproduce the existing differential
    test pattern, but driven through the runner abstraction instead of inlined
    function calls in each test file."""

    def test_python_runner_drives_full_diff_to_100_percent(self):
        # Build vectors with EXPECTED outputs that match what we know the
        # COSGN00C reimpl produces. This is what the COBOL run would produce
        # too, since the existing test_differential_cosgn00c.py test already
        # demonstrates COBOL/Python parity at 100%.
        vectors = [
            DiffVector(
                vector_id="ADMIN_LOGIN",
                program="COSGN00C",
                inputs={"USERID": "ADMIN001", "PASSWD": "PASS1234"},
                expected_outputs={
                    "XCTL_TARGET": "COADM01C",
                    "HAS_COMMAREA": "Y",
                    "ERROR_MSG": "",
                },
                actual_outputs={},  # populated by runner
                field_types={
                    "XCTL_TARGET": "str",
                    "HAS_COMMAREA": "str",
                    "ERROR_MSG": "str",
                },
            ),
            DiffVector(
                vector_id="USER_LOGIN",
                program="COSGN00C",
                inputs={"USERID": "USER0001", "PASSWD": "MYPASSWD"},
                expected_outputs={
                    "XCTL_TARGET": "COMEN01C",
                    "HAS_COMMAREA": "Y",
                    "ERROR_MSG": "",
                },
                actual_outputs={},
                field_types={
                    "XCTL_TARGET": "str",
                    "HAS_COMMAREA": "str",
                    "ERROR_MSG": "str",
                },
            ),
            DiffVector(
                vector_id="WRONG_PWD",
                program="COSGN00C",
                inputs={"USERID": "ADMIN001", "PASSWD": "WRONGPWD"},
                expected_outputs={
                    "XCTL_TARGET": "",
                    "HAS_COMMAREA": "N",
                    "ERROR_MSG": "Wrong Password",
                },
                actual_outputs={},
                field_types={
                    "XCTL_TARGET": "str",
                    "HAS_COMMAREA": "str",
                    "ERROR_MSG": "str",
                },
            ),
            DiffVector(
                vector_id="NOT_FOUND",
                program="COSGN00C",
                inputs={"USERID": "UNKNOWN1", "PASSWD": "ANYTHING"},
                expected_outputs={
                    "XCTL_TARGET": "",
                    "HAS_COMMAREA": "N",
                    "ERROR_MSG": "User not found",
                },
                actual_outputs={},
                field_types={
                    "XCTL_TARGET": "str",
                    "HAS_COMMAREA": "str",
                    "ERROR_MSG": "str",
                },
            ),
        ]

        populate_actuals(vectors, PythonRunner())
        report = run_vectors(vectors)

        assert report.confidence_score == 100.0, (
            f"PythonRunner-driven harness failed: "
            f"{report.failed} of {report.total_vectors} vectors mismatched.\n"
            f"Mismatches: {report.mismatches}"
        )
        assert report.passed == 4
        assert report.failed == 0


# ── Factory + JSON contract ────────────────────────────────────────────────


class TestRunnerFactory:
    def test_make_runner_python(self):
        runner = make_runner("python")
        assert isinstance(runner, PythonRunner)

    def test_make_runner_java(self):
        runner = make_runner("java")
        assert isinstance(runner, JavaRunner)

    def test_make_runner_case_insensitive(self):
        assert isinstance(make_runner("PYTHON"), PythonRunner)
        assert isinstance(make_runner("Java"), JavaRunner)

    def test_make_runner_unknown_raises(self):
        with pytest.raises(ValueError, match="unknown runner"):
            make_runner("cobol")


class TestRunResponseJsonContract:
    """RunResponse <-> JSON round-trip is the wire format Java will speak."""

    def test_round_trip(self):
        original = RunResponse(
            vector_id="V001",
            outputs={"FOO": "1", "BAR": "two"},
            errors=[],
        )
        restored = RunResponse.from_json(original.to_json())
        assert restored.vector_id == "V001"
        assert restored.outputs == {"FOO": "1", "BAR": "two"}
        assert restored.errors == []

    def test_from_json_handles_errors_array(self):
        raw = '{"vector_id": "V002", "outputs": {}, "errors": ["boom"]}'
        response = RunResponse.from_json(raw)
        assert not response.ok
        assert response.errors == ["boom"]

    def test_from_json_defaults_missing_fields(self):
        response = RunResponse.from_json('{}')
        assert response.vector_id == ""
        assert response.outputs == {}
        assert response.errors == []
