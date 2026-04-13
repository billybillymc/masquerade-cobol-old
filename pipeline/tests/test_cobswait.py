"""
Differential tests for COBSWAIT — CardDemo wait utility.

All tests mock time.sleep so the suite runs in milliseconds.
Expected values are derived from the COBOL source and PIC 9(8) COMP semantics.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reimpl"))

from reimpl.python.cobswait import coerce_parm, wait_centiseconds, run
from differential_harness import DiffVector, run_vectors, render_report_text


# ── coerce_parm: PIC X(8) → PIC 9(8) COMP ────────────────────────────────────

class TestCoerceParm:
    def test_numeric_string_parsed(self):
        assert coerce_parm("100     ") == 100

    def test_leading_zeros_ok(self):
        assert coerce_parm("00000250") == 250

    def test_blank_parm_is_zero(self):
        assert coerce_parm("        ") == 0

    def test_non_numeric_is_zero(self):
        assert coerce_parm("ABCDEFGH") == 0

    def test_negative_clamped_to_zero(self):
        assert coerce_parm("-100    ") == 0

    def test_overflow_left_truncated(self):
        # PIC 9(8) COMP: 999999999 (9 digits) → mod 10^8 = 99999999
        assert coerce_parm("999999999") == 99_999_999

    def test_exactly_at_pic_ceiling(self):
        assert coerce_parm("99999999") == 99_999_999

    def test_zero_is_zero(self):
        assert coerce_parm("0       ") == 0


# ── wait_centiseconds: sleep behaviour ───────────────────────────────────────

class TestWaitCentiseconds:
    def test_sleeps_correct_fraction(self):
        with patch("reimpl.python.cobswait.time.sleep") as mock_sleep:
            result = wait_centiseconds(100)
        mock_sleep.assert_called_once_with(1.0)
        assert result.requested_cs == 100
        assert result.actual_seconds == 1.0

    def test_zero_centiseconds_no_sleep(self):
        with patch("reimpl.python.cobswait.time.sleep") as mock_sleep:
            result = wait_centiseconds(0)
        mock_sleep.assert_called_once_with(0.0)
        assert result.requested_cs == 0

    def test_one_centisecond_is_ten_milliseconds(self):
        with patch("reimpl.python.cobswait.time.sleep") as mock_sleep:
            wait_centiseconds(1)
        mock_sleep.assert_called_once_with(0.01)

    def test_negative_clamped_to_zero(self):
        with patch("reimpl.python.cobswait.time.sleep") as mock_sleep:
            result = wait_centiseconds(-50)
        mock_sleep.assert_called_once_with(0.0)
        assert result.requested_cs == 0

    def test_large_value_clamped_to_pic_ceiling(self):
        with patch("reimpl.python.cobswait.time.sleep") as mock_sleep:
            result = wait_centiseconds(200_000_000)
        assert result.requested_cs == 99_999_999
        mock_sleep.assert_called_once_with(999_999.99)


# ── run: full PROCEDURE DIVISION entry point ─────────────────────────────────

class TestRun:
    def test_run_delegates_correctly(self):
        with patch("reimpl.python.cobswait.time.sleep") as mock_sleep:
            result = run("200     ")
        mock_sleep.assert_called_once_with(2.0)
        assert result.requested_cs == 200

    def test_run_blank_parm_no_wait(self):
        with patch("reimpl.python.cobswait.time.sleep") as mock_sleep:
            result = run("        ")
        mock_sleep.assert_called_once_with(0.0)
        assert result.requested_cs == 0

    def test_run_invalid_parm_no_wait(self):
        with patch("reimpl.python.cobswait.time.sleep") as mock_sleep:
            run("INVALID ")
        mock_sleep.assert_called_once_with(0.0)


# ── DiffVector harness: COBOL-spec driven scenarios ───────────────────────────

class TestDifferentialCobswait:
    """
    Verifies COBSWAIT business rules via the DiffVector harness.

    Expected values derived from:
      - PIC 9(8) COMP semantics (unsigned 8-digit)
      - MVSWAIT spec: centiseconds → sleep duration
      - COBOL MOVE numeric coercion rules
    """

    _cases = [
        # (case_id, parm_value, expected_cs, expected_seconds)
        ("ZERO",        "0       ", 0,           0.0),
        ("ONE_SECOND",  "100     ", 100,          1.0),
        ("HALF_SEC",    "50      ", 50,           0.5),
        ("BLANK",       "        ", 0,            0.0),
        ("LEADING_ZERO","00000100", 100,          1.0),
        ("CEILING",     "99999999", 99_999_999,   999_999.99),
        ("OVERFLOW",    "999999999", 99_999_999,  999_999.99),
        ("NON_NUMERIC", "ABCDEFGH", 0,            0.0),
    ]

    def test_all_scenarios_match_spec(self):
        vectors = []
        for case_id, parm, expected_cs, expected_sec in self._cases:
            with patch("reimpl.python.cobswait.time.sleep"):
                result = run(parm)

            vectors.append(DiffVector(
                vector_id=case_id,
                program="COBSWAIT",
                inputs={"PARM-VALUE": parm.strip()},
                expected_outputs={
                    "CENTISECONDS": str(expected_cs),
                    "SLEEP_SECONDS": f"{expected_sec:.2f}",
                },
                actual_outputs={
                    "CENTISECONDS": str(result.requested_cs),
                    "SLEEP_SECONDS": f"{result.actual_seconds:.2f}",
                },
                field_types={"CENTISECONDS": "str", "SLEEP_SECONDS": "str"},
            ))

        report = run_vectors(vectors)
        print("\n" + render_report_text(report))
        assert report.confidence_score == 100.0, render_report_text(report)
