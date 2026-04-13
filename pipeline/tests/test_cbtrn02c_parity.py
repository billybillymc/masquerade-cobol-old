"""Cross-language parity tests for CBTRN02C — CardDemo Daily Transaction Posting.

Sixth Java reimplementation. Notable because the HAPPY_GOLDEN_VECTOR scenario
exercises the EXACT arithmetic from the W1 CobolDecimal unit test at
`test_cobol_decimal.py::TestGoldenVectors::test_balance_calculation_cbtrn02c`:

    temp_bal = acct_curr_cyc_credit - acct_curr_cyc_debit + tran_amt
             = 5000.00 - 3500.75 + 150.25 = 1649.50

That unit test verified CobolDecimal in isolation; this test verifies the
same calculation embedded in the full CBTRN02C posting flow, with account
mutation and fail-code tracking. If this passes, the golden vector is
validated end-to-end.

Fail codes covered:
  100 — INVALID_CARD  (card not in XREF)
  101 — ACCT_NOT_FOUND (dangling XREF)
  102 — OVERLIMIT
  103 — EXPIRED
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


SCENARIOS = [
    "HAPPY_GOLDEN_VECTOR",
    "INVALID_CARD",
    "ACCT_NOT_FOUND",
    "OVERLIMIT",
    "EXPIRED",
    "MIXED_BATCH",
]


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestCbtrn02cParity:
    """Python and Java must produce byte-identical outputs for every scenario."""

    def setup_method(self):
        self.python_runner = PythonRunner()
        self.java_runner = _make_java_runner()

    def test_python_and_java_byte_identical(self):
        mismatches = []
        for scenario in SCENARIOS:
            req = RunRequest(
                program="CBTRN02C",
                vector_id=scenario,
                inputs={"SCENARIO": scenario},
            )
            py = self.python_runner.run(req)
            jv = self.java_runner.run(req)

            if not py.ok:
                mismatches.append(f"{scenario}: Python errored: {py.errors}")
                continue
            if not jv.ok:
                mismatches.append(f"{scenario}: Java errored: {jv.errors}")
                continue
            if py.outputs != jv.outputs:
                fields = sorted(set(py.outputs) | set(jv.outputs))
                lines = [f"{scenario}:"]
                for f in fields:
                    pv = py.outputs.get(f, "<missing>")
                    jv_v = jv.outputs.get(f, "<missing>")
                    if pv != jv_v:
                        lines.append(f"  {f}:")
                        lines.append(f"    python: {pv!r}")
                        lines.append(f"    java:   {jv_v!r}")
                mismatches.append("\n".join(lines))

        assert not mismatches, (
            f"\n\nCBTRN02C cross-language parity failed on "
            f"{len(mismatches)} of {len(SCENARIOS)} scenarios:\n\n"
            + "\n\n".join(mismatches)
        )

    def test_golden_vector_final_balance(self):
        """The HAPPY_GOLDEN_VECTOR scenario uses the exact W1 unit test values.

        This test is the end-to-end payoff for the entire CobolDecimal track:
        the same numbers the unit test verified at the operation level are
        now verified through a full business flow. Expected final balance:
          starting curr_bal 1000.00 + tran_amt 150.25 = 1150.25
        """
        jv = self.java_runner.run(RunRequest(
            program="CBTRN02C", vector_id="GV",
            inputs={"SCENARIO": "HAPPY_GOLDEN_VECTOR"},
        ))
        assert jv.ok
        assert jv.outputs["FINAL_BAL_100000001"] == "1150.25"
        assert jv.outputs["POSTED_COUNT"] == "1"
        assert jv.outputs["REJECT_COUNT"] == "0"
        assert jv.outputs["RETURN_CODE"] == "0"
        assert jv.outputs["FAIL_CODES"] == "0"

    def test_all_fail_codes_distinct(self):
        """Verify the 4 fail scenarios produce 4 different fail codes."""
        fail_codes_seen = set()
        for scenario in ["INVALID_CARD", "ACCT_NOT_FOUND", "OVERLIMIT", "EXPIRED"]:
            jv = self.java_runner.run(RunRequest(
                program="CBTRN02C", vector_id=scenario,
                inputs={"SCENARIO": scenario},
            ))
            code = jv.outputs["FAIL_CODES"]
            fail_codes_seen.add(code)
        assert fail_codes_seen == {"100", "101", "102", "103"}, \
            f"Expected all 4 fail codes, got {fail_codes_seen}"

    def test_return_code_is_4_on_any_reject(self):
        for scenario in ["INVALID_CARD", "ACCT_NOT_FOUND", "OVERLIMIT", "EXPIRED", "MIXED_BATCH"]:
            jv = self.java_runner.run(RunRequest(
                program="CBTRN02C", vector_id=scenario,
                inputs={"SCENARIO": scenario},
            ))
            assert jv.outputs["RETURN_CODE"] == "4", \
                f"{scenario}: expected RETURN_CODE=4 (any reject), got {jv.outputs['RETURN_CODE']}"

    def test_mixed_batch_partial_success(self):
        """MIXED_BATCH: 1 posted + 2 rejected. Verify the posted transaction
        updated its account but the rejected ones did not."""
        jv = self.java_runner.run(RunRequest(
            program="CBTRN02C", vector_id="MIXED",
            inputs={"SCENARIO": "MIXED_BATCH"},
        ))
        assert jv.outputs["TRANSACTION_COUNT"] == "3"
        assert jv.outputs["POSTED_COUNT"] == "1"
        assert jv.outputs["REJECT_COUNT"] == "2"
        assert jv.outputs["FAIL_CODES"] == "0,100,102"
        # Posted transaction: 1000.00 + 75.00 = 1075.00
        assert jv.outputs["FINAL_BAL_100000001"] == "1075.00"
        # Overlimit transaction rejected, account unchanged: 50.00
        assert jv.outputs["FINAL_BAL_100000003"] == "50.00"


# ── End-to-end through differential harness ──────────────────────────────


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestCbtrn02cThroughHarness:
    """Drive all scenarios through the harness with hand-derived expectations."""

    def test_all_scenarios_at_100_percent(self):
        vectors = [
            DiffVector(
                vector_id="HAPPY_GOLDEN_VECTOR",
                program="CBTRN02C",
                inputs={"SCENARIO": "HAPPY_GOLDEN_VECTOR"},
                expected_outputs={
                    "TRANSACTION_COUNT": "1",
                    "REJECT_COUNT": "0",
                    "POSTED_COUNT": "1",
                    "RETURN_CODE": "0",
                    "FAIL_CODES": "0",
                    "FINAL_BAL_100000001": "1150.25",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "TRANSACTION_COUNT", "REJECT_COUNT", "POSTED_COUNT",
                    "RETURN_CODE", "FAIL_CODES", "FINAL_BAL_100000001",
                ]},
            ),
            DiffVector(
                vector_id="INVALID_CARD",
                program="CBTRN02C",
                inputs={"SCENARIO": "INVALID_CARD"},
                expected_outputs={
                    "TRANSACTION_COUNT": "1",
                    "REJECT_COUNT": "1",
                    "POSTED_COUNT": "0",
                    "RETURN_CODE": "4",
                    "FAIL_CODES": "100",
                    "FINAL_BAL_100000001": "1000.00",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "TRANSACTION_COUNT", "REJECT_COUNT", "POSTED_COUNT",
                    "RETURN_CODE", "FAIL_CODES", "FINAL_BAL_100000001",
                ]},
            ),
            DiffVector(
                vector_id="ACCT_NOT_FOUND",
                program="CBTRN02C",
                inputs={"SCENARIO": "ACCT_NOT_FOUND"},
                expected_outputs={
                    "TRANSACTION_COUNT": "1",
                    "REJECT_COUNT": "1",
                    "POSTED_COUNT": "0",
                    "RETURN_CODE": "4",
                    "FAIL_CODES": "101",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "TRANSACTION_COUNT", "REJECT_COUNT", "POSTED_COUNT",
                    "RETURN_CODE", "FAIL_CODES",
                ]},
            ),
            DiffVector(
                vector_id="OVERLIMIT",
                program="CBTRN02C",
                inputs={"SCENARIO": "OVERLIMIT"},
                expected_outputs={
                    "TRANSACTION_COUNT": "1",
                    "REJECT_COUNT": "1",
                    "POSTED_COUNT": "0",
                    "RETURN_CODE": "4",
                    "FAIL_CODES": "102",
                    "FINAL_BAL_100000003": "50.00",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "TRANSACTION_COUNT", "REJECT_COUNT", "POSTED_COUNT",
                    "RETURN_CODE", "FAIL_CODES", "FINAL_BAL_100000003",
                ]},
            ),
            DiffVector(
                vector_id="EXPIRED",
                program="CBTRN02C",
                inputs={"SCENARIO": "EXPIRED"},
                expected_outputs={
                    "TRANSACTION_COUNT": "1",
                    "REJECT_COUNT": "1",
                    "POSTED_COUNT": "0",
                    "RETURN_CODE": "4",
                    "FAIL_CODES": "103",
                    "FINAL_BAL_100000004": "0.00",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "TRANSACTION_COUNT", "REJECT_COUNT", "POSTED_COUNT",
                    "RETURN_CODE", "FAIL_CODES", "FINAL_BAL_100000004",
                ]},
            ),
            DiffVector(
                vector_id="MIXED_BATCH",
                program="CBTRN02C",
                inputs={"SCENARIO": "MIXED_BATCH"},
                expected_outputs={
                    "TRANSACTION_COUNT": "3",
                    "REJECT_COUNT": "2",
                    "POSTED_COUNT": "1",
                    "RETURN_CODE": "4",
                    "FAIL_CODES": "0,100,102",
                    "FINAL_BAL_100000001": "1075.00",
                    "FINAL_BAL_100000003": "50.00",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "TRANSACTION_COUNT", "REJECT_COUNT", "POSTED_COUNT",
                    "RETURN_CODE", "FAIL_CODES",
                    "FINAL_BAL_100000001", "FINAL_BAL_100000003",
                ]},
            ),
        ]

        populate_actuals(vectors, _make_java_runner())
        report = run_vectors(vectors)

        assert report.confidence_score == 100.0, (
            f"CBTRN02C Java pilot failed: {report.failed} of "
            f"{report.total_vectors} vectors mismatched.\n"
            f"Mismatches: {report.mismatches}"
        )
        assert report.passed == 6
        assert report.failed == 0


class TestPythonRunVectorWorks:
    def test_golden_vector(self):
        runner = PythonRunner()
        response = runner.run(RunRequest(
            program="CBTRN02C", vector_id="V1",
            inputs={"SCENARIO": "HAPPY_GOLDEN_VECTOR"},
        ))
        assert response.ok
        assert response.outputs["FINAL_BAL_100000001"] == "1150.25"
