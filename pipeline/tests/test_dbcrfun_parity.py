"""Cross-language parity tests for DBCRFUN — CBSA Debit/Credit engine.

This is the third Java reimplementation pilot, and the FIRST one that exercises
CobolDecimal arithmetic on the Java side. Every other reimpl ported so far has
been pure string/control-flow logic.

Verifies that pipeline/reimpl/cbsa_dbcrfun.py and the Java twin produce
byte-identical outputs across:
  - Successful credits (positive amount)
  - Successful debits (negative amount)
  - Account not found (fail_code 1)
  - Insufficient funds for payment (fail_code 3)
  - Restricted account types (MORTGAGE/LOAN) on payment (fail_code 4)
  - Non-payment debits on restricted accounts (allowed)
  - Boundary conditions: exact-balance debit, zero-amount

Together with test_csutldtc_parity and test_java_runner_pilot, this is the
running parity-coverage matrix for the Java track.
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
JAVA_BIN = "C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot/bin/java.exe"


def _java_available() -> bool:
    return RUNNER_JAR.exists() and Path(JAVA_BIN).exists()


def _make_java_runner() -> JavaRunner:
    return JavaRunner(jar_path=RUNNER_JAR, java_bin=JAVA_BIN)


# ── Test scenarios ─────────────────────────────────────────────────────────
#
# Seeded accounts (in both Python and Java run_vector adapters):
#   ACC00001  CHECKING  1000.00  — normal account, debits and credits
#   ACC00002  CHECKING  10.00    — low balance, for insufficient funds
#   ACC00003  MORTGAGE  5000.00  — restricted, no payment debit/credit
#   ACC00004  LOAN      500.00   — restricted
#   ACC00005  SAVING    2000.00  — variety
#
# Each entry: (vector_id, ACC_NO, AMOUNT, FACIL_TYPE, ORIGIN, description)

SCENARIOS = [
    # Happy paths
    ("CREDIT_100",      "ACC00001", "100.00",   "0",   "", "Teller credit 100 to checking"),
    ("DEBIT_50",        "ACC00001", "-50.00",   "0",   "", "Teller debit 50 from checking"),
    ("PAYMENT_CREDIT",  "ACC00005", "250.00",   "496", "PAYROLL APR  ", "Payment credit 250 (PCR)"),
    ("PAYMENT_DEBIT",   "ACC00001", "-200.00",  "496", "RENT APR     ", "Payment debit 200 (PDR)"),

    # Failure paths
    ("NOT_FOUND",       "ACC99999", "100.00",   "0",   "", "Account does not exist (fail 1)"),
    ("INSUFFICIENT",    "ACC00002", "-200.00",  "496", "BIG BILL     ", "Payment debit > balance (fail 3)"),
    ("RESTRICTED_DEBIT_PAY",  "ACC00003", "-100.00", "496", "OOPS         ", "Payment debit MORTGAGE (fail 4)"),
    ("RESTRICTED_CREDIT_PAY", "ACC00004", "100.00",  "496", "OOPS         ", "Payment credit LOAN (fail 4)"),

    # Important: non-payment debit on MORTGAGE is ALLOWED (teller operation)
    ("TELLER_DEBIT_MORTGAGE", "ACC00003", "-100.00", "0", "", "Teller debit MORTGAGE (allowed)"),

    # Boundary: exact-balance payment debit (succeeds — diff is 0, not < 0)
    ("EXACT_BALANCE_DEBIT", "ACC00002", "-10.00", "496", "EXACT MATCH  ", "Payment debit exact balance"),

    # Boundary: zero amount (technically not negative, classified as credit)
    ("ZERO_AMOUNT",     "ACC00001", "0.00",     "0",   "", "Zero amount transaction"),

    # Decimal precision exercise — non-integer amount
    ("CENTS_DEBIT",     "ACC00001", "-12.34",   "0",   "", "Debit a cents-precise amount"),
    ("CENTS_CREDIT",    "ACC00005", "0.01",     "0",   "", "Credit one cent"),
]


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestDbcrfunParity:
    """Python and Java must produce IDENTICAL outputs for every scenario.

    This test is the proof that CobolDecimal-based Java arithmetic produces
    the same results as Python's plain Decimal arithmetic for in-range values.
    Failure here is the strongest signal yet of a CobolDecimal port bug.
    """

    def setup_method(self):
        self.python_runner = PythonRunner()
        self.java_runner = _make_java_runner()

    def test_python_and_java_byte_identical(self):
        mismatches = []

        for vid, acc_no, amount, facil_type, origin, desc in SCENARIOS:
            req = RunRequest(
                program="DBCRFUN",
                vector_id=vid,
                inputs={
                    "ACC_NO": acc_no,
                    "AMOUNT": amount,
                    "FACIL_TYPE": facil_type,
                    "ORIGIN": origin,
                },
            )
            py = self.python_runner.run(req)
            jv = self.java_runner.run(req)

            if not py.ok:
                mismatches.append(f"{vid} ({desc}): Python errored: {py.errors}")
                continue
            if not jv.ok:
                mismatches.append(f"{vid} ({desc}): Java errored: {jv.errors}")
                continue
            if py.outputs != jv.outputs:
                fields = sorted(set(py.outputs) | set(jv.outputs))
                diff_lines = [f"{vid} ({desc}):"]
                for f in fields:
                    pv = py.outputs.get(f, "<missing>")
                    jv_v = jv.outputs.get(f, "<missing>")
                    if pv != jv_v:
                        diff_lines.append(f"  {f}:")
                        diff_lines.append(f"    python: {pv!r}")
                        diff_lines.append(f"    java:   {jv_v!r}")
                mismatches.append("\n".join(diff_lines))

        assert not mismatches, (
            f"\n\nDBCRFUN cross-language parity failed on "
            f"{len(mismatches)} of {len(SCENARIOS)} scenarios:\n\n"
            + "\n\n".join(mismatches)
        )

    def test_balances_always_have_two_decimal_places(self):
        """Every balance string from either language must be scale-2 fixed point."""
        for vid, acc_no, amount, facil_type, origin, _desc in SCENARIOS:
            req = RunRequest(
                program="DBCRFUN",
                vector_id=vid,
                inputs={
                    "ACC_NO": acc_no, "AMOUNT": amount,
                    "FACIL_TYPE": facil_type, "ORIGIN": origin,
                },
            )
            jv = self.java_runner.run(req)
            assert jv.ok, f"{vid}: {jv.errors}"
            avail = jv.outputs["AVAIL_BAL"]
            actual = jv.outputs["ACTUAL_BAL"]
            # Format: optional sign, digits, dot, exactly 2 digits
            assert "." in avail and len(avail.split(".")[-1]) == 2, \
                f"{vid}: AVAIL_BAL {avail!r} not scale 2"
            assert "." in actual and len(actual.split(".")[-1]) == 2, \
                f"{vid}: ACTUAL_BAL {actual!r} not scale 2"

    def test_sortcode_constant(self):
        """SORTCODE is the constant 987654 regardless of input."""
        for vid, acc_no, amount, facil_type, origin, _desc in SCENARIOS:
            req = RunRequest(
                program="DBCRFUN",
                vector_id=vid,
                inputs={
                    "ACC_NO": acc_no, "AMOUNT": amount,
                    "FACIL_TYPE": facil_type, "ORIGIN": origin,
                },
            )
            jv = self.java_runner.run(req)
            assert jv.outputs["SORTCODE"] == "987654"


# ── Differential harness with hand-derived expected outputs ────────────────


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestDbcrfunThroughHarness:
    """End-to-end: drive Java through the differential harness against
    expected outputs derived by hand from the COBOL/Python contract.

    These vectors are the strictest possible parity gate — both the Java
    runtime values AND the hand-computed expected values must agree."""

    def test_full_diff_at_100_percent(self):
        vectors = [
            DiffVector(
                vector_id="CREDIT_100",
                program="DBCRFUN",
                inputs={
                    "ACC_NO": "ACC00001", "AMOUNT": "100.00",
                    "FACIL_TYPE": "0", "ORIGIN": "",
                },
                expected_outputs={
                    "SUCCESS": "Y", "FAIL_CODE": "0",
                    "AVAIL_BAL": "1100.00", "ACTUAL_BAL": "1100.00",
                    "SORTCODE": "987654",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "SUCCESS", "FAIL_CODE", "AVAIL_BAL", "ACTUAL_BAL", "SORTCODE",
                ]},
            ),
            DiffVector(
                vector_id="DEBIT_50",
                program="DBCRFUN",
                inputs={
                    "ACC_NO": "ACC00001", "AMOUNT": "-50.00",
                    "FACIL_TYPE": "0", "ORIGIN": "",
                },
                expected_outputs={
                    "SUCCESS": "Y", "FAIL_CODE": "0",
                    "AVAIL_BAL": "950.00", "ACTUAL_BAL": "950.00",
                    "SORTCODE": "987654",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "SUCCESS", "FAIL_CODE", "AVAIL_BAL", "ACTUAL_BAL", "SORTCODE",
                ]},
            ),
            DiffVector(
                vector_id="NOT_FOUND",
                program="DBCRFUN",
                inputs={
                    "ACC_NO": "ACC99999", "AMOUNT": "100.00",
                    "FACIL_TYPE": "0", "ORIGIN": "",
                },
                expected_outputs={
                    "SUCCESS": "N", "FAIL_CODE": "1",
                    "AVAIL_BAL": "0.00", "ACTUAL_BAL": "0.00",
                    "SORTCODE": "987654",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "SUCCESS", "FAIL_CODE", "AVAIL_BAL", "ACTUAL_BAL", "SORTCODE",
                ]},
            ),
            DiffVector(
                vector_id="INSUFFICIENT",
                program="DBCRFUN",
                inputs={
                    "ACC_NO": "ACC00002", "AMOUNT": "-200.00",
                    "FACIL_TYPE": "496", "ORIGIN": "BIG BILL     ",
                },
                expected_outputs={
                    "SUCCESS": "N", "FAIL_CODE": "3",
                    "AVAIL_BAL": "0.00", "ACTUAL_BAL": "0.00",
                    "SORTCODE": "987654",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "SUCCESS", "FAIL_CODE", "AVAIL_BAL", "ACTUAL_BAL", "SORTCODE",
                ]},
            ),
            DiffVector(
                vector_id="RESTRICTED_DEBIT_PAY",
                program="DBCRFUN",
                inputs={
                    "ACC_NO": "ACC00003", "AMOUNT": "-100.00",
                    "FACIL_TYPE": "496", "ORIGIN": "OOPS         ",
                },
                expected_outputs={
                    "SUCCESS": "N", "FAIL_CODE": "4",
                    "AVAIL_BAL": "0.00", "ACTUAL_BAL": "0.00",
                    "SORTCODE": "987654",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "SUCCESS", "FAIL_CODE", "AVAIL_BAL", "ACTUAL_BAL", "SORTCODE",
                ]},
            ),
            DiffVector(
                vector_id="TELLER_DEBIT_MORTGAGE",
                program="DBCRFUN",
                inputs={
                    "ACC_NO": "ACC00003", "AMOUNT": "-100.00",
                    "FACIL_TYPE": "0", "ORIGIN": "",
                },
                expected_outputs={
                    "SUCCESS": "Y", "FAIL_CODE": "0",
                    "AVAIL_BAL": "4900.00", "ACTUAL_BAL": "4900.00",
                    "SORTCODE": "987654",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "SUCCESS", "FAIL_CODE", "AVAIL_BAL", "ACTUAL_BAL", "SORTCODE",
                ]},
            ),
            DiffVector(
                vector_id="CENTS_DEBIT",
                program="DBCRFUN",
                inputs={
                    "ACC_NO": "ACC00001", "AMOUNT": "-12.34",
                    "FACIL_TYPE": "0", "ORIGIN": "",
                },
                expected_outputs={
                    "SUCCESS": "Y", "FAIL_CODE": "0",
                    "AVAIL_BAL": "987.66", "ACTUAL_BAL": "987.66",
                    "SORTCODE": "987654",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "SUCCESS", "FAIL_CODE", "AVAIL_BAL", "ACTUAL_BAL", "SORTCODE",
                ]},
            ),
        ]

        populate_actuals(vectors, _make_java_runner())
        report = run_vectors(vectors)

        assert report.confidence_score == 100.0, (
            f"DBCRFUN Java pilot failed: {report.failed} of {report.total_vectors} "
            f"vectors mismatched.\n"
            f"Mismatches: {report.mismatches}"
        )
        assert report.passed == 7
        assert report.failed == 0


# ── Python-side smoke tests ───────────────────────────────────────────────


class TestPythonRunVectorWorks:
    """Independent Python-side sanity checks (no Java needed)."""

    def test_credit_succeeds(self):
        runner = PythonRunner()
        response = runner.run(RunRequest(
            program="DBCRFUN", vector_id="V1",
            inputs={"ACC_NO": "ACC00001", "AMOUNT": "50.00", "FACIL_TYPE": "0", "ORIGIN": ""},
        ))
        assert response.ok
        assert response.outputs["SUCCESS"] == "Y"
        assert response.outputs["AVAIL_BAL"] == "1050.00"

    def test_not_found_returns_fail_code_1(self):
        runner = PythonRunner()
        response = runner.run(RunRequest(
            program="DBCRFUN", vector_id="V2",
            inputs={"ACC_NO": "BOGUS", "AMOUNT": "10.00", "FACIL_TYPE": "0", "ORIGIN": ""},
        ))
        assert response.ok
        assert response.outputs["SUCCESS"] == "N"
        assert response.outputs["FAIL_CODE"] == "1"
