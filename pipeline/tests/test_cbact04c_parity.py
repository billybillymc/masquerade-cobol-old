"""Cross-language parity tests for CBACT04C — CardDemo Interest Calculator.

Fourth Java reimplementation. Exercises:

  - Iterative batch processing with account-boundary detection
  - Decimal * Decimal / Decimal chain with explicit HALF_UP rounding
  - Repository pattern with multiple lookup tables (accounts, xrefs, rates)
  - Disclosure group fallback logic (DEFAULT group when specific not found)
  - Zero-rate skip branch

The arithmetic is the most interesting part: interest is computed as
`(catBal * rate / 1200).quantize(0.01, HALF_UP)`. Python uses its Decimal
module's default context (28 digits, HALF_EVEN) for the intermediate, then
quantizes to 2dp HALF_UP for the final value. The Java side MUST use
`MathContext(28, HALF_EVEN)` and `setScale(2, HALF_UP)` to match exactly.
Any divergence in the intermediate precision would cause double-rounding
parity bugs.
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


SCENARIOS = ["SINGLE", "MULTI_CAT", "TWO_ACCOUNTS", "ZERO_RATE"]


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestCbact04cParity:
    """Python and Java produce byte-identical output for every scenario."""

    def setup_method(self):
        self.python_runner = PythonRunner()
        self.java_runner = _make_java_runner()

    def test_python_and_java_byte_identical(self):
        mismatches = []
        for scenario in SCENARIOS:
            req = RunRequest(
                program="CBACT04C",
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
                diff_lines = [f"{scenario}:"]
                for f in fields:
                    pv = py.outputs.get(f, "<missing>")
                    jv_v = jv.outputs.get(f, "<missing>")
                    if pv != jv_v:
                        diff_lines.append(f"  {f}:")
                        diff_lines.append(f"    python: {pv!r}")
                        diff_lines.append(f"    java:   {jv_v!r}")
                mismatches.append("\n".join(diff_lines))

        assert not mismatches, (
            f"\n\nCBACT04C cross-language parity failed on "
            f"{len(mismatches)} of {len(SCENARIOS)} scenarios:\n\n"
            + "\n\n".join(mismatches)
        )

    def test_total_interest_is_scale_2(self):
        """Every TOTAL_INTEREST value must be exactly 2 decimal places."""
        for scenario in SCENARIOS:
            jv = self.java_runner.run(RunRequest(
                program="CBACT04C", vector_id=scenario,
                inputs={"SCENARIO": scenario},
            ))
            assert jv.ok
            ti = jv.outputs["TOTAL_INTEREST"]
            assert "." in ti and len(ti.split(".")[-1]) == 2, \
                f"{scenario}: TOTAL_INTEREST {ti!r} not scale 2"

    def test_zero_rate_writes_no_transactions(self):
        jv = self.java_runner.run(RunRequest(
            program="CBACT04C", vector_id="ZERO_RATE",
            inputs={"SCENARIO": "ZERO_RATE"},
        ))
        assert jv.outputs["TRANSACTIONS_WRITTEN"] == "0"
        assert jv.outputs["TOTAL_INTEREST"] == "0.00"

    def test_multi_cat_accumulates_across_categories(self):
        """MULTI_CAT has 3 catbal records for 1 account — all interest
        should sum into a single account update."""
        jv = self.java_runner.run(RunRequest(
            program="CBACT04C", vector_id="MULTI_CAT",
            inputs={"SCENARIO": "MULTI_CAT"},
        ))
        # 5000*18.99/1200 = 79.125 → 79.13 (HALF_UP)
        # 3000*22.49/1200 = 56.225 → 56.23 (HALF_UP)
        # 2000*24.99/1200 = 41.65 (exact)
        # sum = 177.01
        # starting balance = 10000.00 → 10177.01
        assert jv.outputs["TOTAL_INTEREST"] == "177.01"
        assert jv.outputs["FINAL_BAL_1"] == "10177.01"
        assert jv.outputs["TRANSACTIONS_WRITTEN"] == "3"

    def test_two_accounts_tracks_each_separately(self):
        """TWO_ACCOUNTS has catbals for 2 different accounts — the break
        on account boundary must update both."""
        jv = self.java_runner.run(RunRequest(
            program="CBACT04C", vector_id="TWO_ACCOUNTS",
            inputs={"SCENARIO": "TWO_ACCOUNTS"},
        ))
        # 500 * 15 / 1200 = 6.25
        # 800 * 15 / 1200 = 10.00
        assert jv.outputs["FINAL_BAL_1"] == "1006.25"
        assert jv.outputs["FINAL_BAL_2"] == "2010.00"
        assert jv.outputs["TOTAL_INTEREST"] == "16.25"


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestCbact04cThroughHarness:
    """End-to-end differential harness drive with hand-computed expected outputs."""

    def test_all_scenarios_at_100_percent(self):
        vectors = [
            DiffVector(
                vector_id="SINGLE",
                program="CBACT04C",
                inputs={"SCENARIO": "SINGLE"},
                expected_outputs={
                    "RECORDS_PROCESSED": "1",
                    "TOTAL_INTEREST": "15.83",
                    "TRANSACTIONS_WRITTEN": "1",
                    "FINAL_BAL_1": "5015.83",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "RECORDS_PROCESSED", "TOTAL_INTEREST",
                    "TRANSACTIONS_WRITTEN", "FINAL_BAL_1",
                ]},
            ),
            DiffVector(
                vector_id="MULTI_CAT",
                program="CBACT04C",
                inputs={"SCENARIO": "MULTI_CAT"},
                expected_outputs={
                    "RECORDS_PROCESSED": "3",
                    "TOTAL_INTEREST": "177.01",
                    "TRANSACTIONS_WRITTEN": "3",
                    "FINAL_BAL_1": "10177.01",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "RECORDS_PROCESSED", "TOTAL_INTEREST",
                    "TRANSACTIONS_WRITTEN", "FINAL_BAL_1",
                ]},
            ),
            DiffVector(
                vector_id="TWO_ACCOUNTS",
                program="CBACT04C",
                inputs={"SCENARIO": "TWO_ACCOUNTS"},
                expected_outputs={
                    "RECORDS_PROCESSED": "2",
                    "TOTAL_INTEREST": "16.25",
                    "TRANSACTIONS_WRITTEN": "2",
                    "FINAL_BAL_1": "1006.25",
                    "FINAL_BAL_2": "2010.00",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "RECORDS_PROCESSED", "TOTAL_INTEREST",
                    "TRANSACTIONS_WRITTEN", "FINAL_BAL_1", "FINAL_BAL_2",
                ]},
            ),
            DiffVector(
                vector_id="ZERO_RATE",
                program="CBACT04C",
                inputs={"SCENARIO": "ZERO_RATE"},
                expected_outputs={
                    "RECORDS_PROCESSED": "1",
                    "TOTAL_INTEREST": "0.00",
                    "TRANSACTIONS_WRITTEN": "0",
                    "FINAL_BAL_1": "5000.00",
                },
                actual_outputs={},
                field_types={k: "str" for k in [
                    "RECORDS_PROCESSED", "TOTAL_INTEREST",
                    "TRANSACTIONS_WRITTEN", "FINAL_BAL_1",
                ]},
            ),
        ]

        populate_actuals(vectors, _make_java_runner())
        report = run_vectors(vectors)

        assert report.confidence_score == 100.0, (
            f"CBACT04C Java pilot failed: {report.failed} of "
            f"{report.total_vectors} vectors mismatched.\n"
            f"Mismatches: {report.mismatches}"
        )
        assert report.passed == 4
        assert report.failed == 0


class TestPythonRunVectorWorks:
    """Independent Python-side sanity checks (no Java required)."""

    def test_single_scenario(self):
        runner = PythonRunner()
        response = runner.run(RunRequest(
            program="CBACT04C", vector_id="V1",
            inputs={"SCENARIO": "SINGLE"},
        ))
        assert response.ok, response.errors
        assert response.outputs["TOTAL_INTEREST"] == "15.83"
        assert response.outputs["FINAL_BAL_1"] == "5015.83"

    def test_unknown_scenario_returns_error(self):
        runner = PythonRunner()
        response = runner.run(RunRequest(
            program="CBACT04C", vector_id="V2",
            inputs={"SCENARIO": "BOGUS"},
        ))
        # Python returns {"error": "unknown scenario: ..."} — the runner
        # passes it through as outputs since it's a dict. The absence of
        # the expected keys would cause the differential harness to
        # report all fields as missing, which is the desired behavior.
        assert response.ok
        assert "error" in response.outputs
