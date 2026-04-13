"""End-to-end pilot test for the Java runner (W6).

This is the gate that proves the entire Java track works:
  1. The Java fat-jar runner (pipeline/reimpl/java/runner) builds and runs
  2. The JavaRunner from vector_runner.py can invoke it via JSON over stdin/stdout
  3. The Java COSGN00C reimplementation produces the same outputs as the
     Python COSGN00C reimplementation for the same input vectors
  4. The differential harness reports 100% confidence when fed Java actuals
     against the expected outputs that the Python (and COBOL) versions produce

Skips cleanly if the Java toolchain or the runner JAR isn't built. Build with:
  cd pipeline/reimpl/java/cobol-decimal && mvn install
  cd pipeline/reimpl/java/runner && mvn package
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from differential_harness import DiffVector, run_vectors
from vector_runner import (
    JavaRunner,
    PythonRunner,
    RunRequest,
    populate_actuals,
)


RUNNER_JAR = (
    Path(__file__).resolve().parent.parent
    / "reimpl" / "java" / "runner" / "target" / "masquerade-runner.jar"
)


def _java_available() -> bool:
    """The Java runner is available if the fat jar exists and `java` is on PATH."""
    if not RUNNER_JAR.exists():
        return False
    import shutil
    if shutil.which("java") is None:
        # Try the known JDK 17 location for this machine
        return Path("C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot/bin/java.exe").exists()
    return True


def _make_java_runner() -> JavaRunner:
    """Build a JavaRunner that points at our actual fat jar and the local JDK."""
    java_bin = "java"
    if Path("C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot/bin/java.exe").exists():
        java_bin = "C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot/bin/java.exe"
    return JavaRunner(jar_path=RUNNER_JAR, java_bin=java_bin)


# ── Pilot acceptance gate ──────────────────────────────────────────────────


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestJavaRunnerPilot:
    """The W6 acceptance gate: Java COSGN00C end-to-end through the harness."""

    def setup_method(self):
        self.runner = _make_java_runner()

    def test_admin_login_via_java_runner(self):
        response = self.runner.run(RunRequest(
            program="COSGN00C",
            vector_id="ADMIN_LOGIN",
            inputs={"USERID": "ADMIN001", "PASSWD": "PASS1234"},
        ))
        assert response.ok, f"Java runner errored: {response.errors}"
        assert response.outputs["XCTL_TARGET"] == "COADM01C"
        assert response.outputs["HAS_COMMAREA"] == "Y"
        assert response.outputs["ERROR_MSG"] == ""

    def test_regular_user_login_via_java_runner(self):
        response = self.runner.run(RunRequest(
            program="COSGN00C",
            vector_id="USER_LOGIN",
            inputs={"USERID": "USER0001", "PASSWD": "MYPASSWD"},
        ))
        assert response.ok
        assert response.outputs["XCTL_TARGET"] == "COMEN01C"
        assert response.outputs["HAS_COMMAREA"] == "Y"
        assert response.outputs["ERROR_MSG"] == ""

    def test_wrong_password_via_java_runner(self):
        response = self.runner.run(RunRequest(
            program="COSGN00C",
            vector_id="WRONG_PWD",
            inputs={"USERID": "ADMIN001", "PASSWD": "WRONGPWD"},
        ))
        assert response.ok
        assert response.outputs["XCTL_TARGET"] == ""
        assert response.outputs["HAS_COMMAREA"] == "N"
        assert response.outputs["ERROR_MSG"] == "Wrong Password"

    def test_unknown_user_via_java_runner(self):
        response = self.runner.run(RunRequest(
            program="COSGN00C",
            vector_id="NOT_FOUND",
            inputs={"USERID": "UNKNOWN1", "PASSWD": "ANYTHING"},
        ))
        assert response.ok
        assert response.outputs["ERROR_MSG"] == "User not found"


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestJavaPythonParity:
    """The same vector set should produce IDENTICAL outputs in Python and Java.

    This is the cross-language correctness gate. If Java and Python disagree
    on any field for any input, one of them is wrong — and we know it
    immediately instead of finding out later in production.
    """

    SCENARIOS = [
        ("ADMIN_LOGIN", "ADMIN001", "PASS1234"),
        ("USER_LOGIN", "USER0001", "MYPASSWD"),
        ("WRONG_PWD", "ADMIN001", "WRONGPWD"),
        ("NOT_FOUND", "UNKNOWN1", "ANYTHING"),
        ("BLANK_USER", "", "PASS1234"),
        ("BLANK_PWD", "ADMIN001", ""),
    ]

    def test_python_and_java_outputs_match_per_scenario(self):
        py_runner = PythonRunner()
        java_runner = _make_java_runner()

        mismatches = []
        for vid, userid, passwd in self.SCENARIOS:
            req = RunRequest(
                program="COSGN00C",
                vector_id=vid,
                inputs={"USERID": userid, "PASSWD": passwd},
            )
            py_resp = py_runner.run(req)
            java_resp = java_runner.run(req)

            if not py_resp.ok:
                mismatches.append(f"{vid}: Python errored: {py_resp.errors}")
                continue
            if not java_resp.ok:
                mismatches.append(f"{vid}: Java errored: {java_resp.errors}")
                continue
            if py_resp.outputs != java_resp.outputs:
                mismatches.append(
                    f"{vid}: outputs differ\n"
                    f"  python: {py_resp.outputs}\n"
                    f"  java:   {java_resp.outputs}"
                )

        assert not mismatches, "Cross-language parity failures:\n" + "\n".join(mismatches)


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestJavaRunnerThroughDifferentialHarness:
    """End-to-end: differential harness driven by JavaRunner reaches 100% confidence."""

    def test_java_runner_full_diff_to_100_percent(self):
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
                actual_outputs={},
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

        populate_actuals(vectors, _make_java_runner())
        report = run_vectors(vectors)

        assert report.confidence_score == 100.0, (
            f"Java pilot mismatch: {report.failed} of {report.total_vectors} "
            f"vectors failed.\nMismatches: {report.mismatches}"
        )
        assert report.passed == 4
        assert report.failed == 0
