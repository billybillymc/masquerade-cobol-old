"""Cross-language parity tests for CSUTLDTC (CardDemo date validation utility).

This is the second Java reimplementation pilot. It verifies that
`pipeline/reimpl/csutldtc.py` and `Csutldtc.java` produce byte-identical
outputs for a comprehensive set of input scenarios covering:

  - Valid dates in each supported format mask
  - Invalid dates (bad month, bad day, non-numeric)
  - Edge cases (insufficient data, range boundaries, unsupported masks)

The strict gate is byte-for-byte equality of the 80-char RAW_MESSAGE field —
this is the COBOL LS-RESULT output that downstream programs depend on.

Skips cleanly if the Java runner JAR isn't built.
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
    if not RUNNER_JAR.exists():
        return False
    return Path("C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot/bin/java.exe").exists()


def _make_java_runner() -> JavaRunner:
    return JavaRunner(
        jar_path=RUNNER_JAR,
        java_bin="C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot/bin/java.exe",
    )


# ── Test scenarios — drives both runners ──────────────────────────────────


# Each entry: (vector_id, ls_date, ls_date_format, scenario description)
# These cover every distinct code path in csutldtc.py validate_date.
SCENARIOS = [
    # Valid dates in each supported format
    ("VALID_ISO",            "2026-04-08", "YYYY-MM-DD", "Valid ISO date"),
    ("VALID_US",             "04/08/2026", "MM/DD/YYYY", "Valid US date"),
    ("VALID_COMPACT",        "20260408",   "YYYYMMDD",   "Valid compact date"),
    ("VALID_TWODIGIT_YEAR",  "04/08/26",   "MM/DD/YY",   "Valid two-digit year"),
    ("VALID_DMY",            "08/04/2026", "DD/MM/YYYY", "Valid day-first format"),
    ("VALID_YYYYSLASH",      "2026/04/08", "YYYY/MM/DD", "Valid slash-separated ISO"),

    # Lilian range boundaries
    ("MIN_VALID",            "1582-10-15", "YYYY-MM-DD", "Earliest valid Lilian date"),
    ("ONE_DAY_BEFORE_RANGE", "1582-10-14", "YYYY-MM-DD", "One day before valid range"),
    ("MAX_VALID",            "9999-12-31", "YYYY-MM-DD", "Latest valid date"),

    # Invalid month
    ("MONTH_13_ISO",         "2026-13-08", "YYYY-MM-DD", "Month 13 in ISO format"),
    ("MONTH_00_US",          "00/08/2026", "MM/DD/YYYY", "Month 00 in US format"),
    ("MONTH_99_COMPACT",     "20269908",   "YYYYMMDD",   "Month 99 in compact format"),

    # Invalid day
    ("DAY_32",               "2026-04-32", "YYYY-MM-DD", "Day 32 (no month has 32)"),
    ("FEB_30",               "2026-02-30", "YYYY-MM-DD", "February 30 (impossible)"),

    # Format / input errors
    ("BAD_PIC",              "2026-04-08", "BOGUSFMT",   "Unrecognized format mask"),
    ("EMPTY_DATE",           "",           "YYYY-MM-DD", "Empty date string"),
    ("NON_NUMERIC",          "abcd-ef-gh", "YYYY-MM-DD", "Non-numeric date"),

    # Whitespace / trim handling
    ("LEADING_WHITESPACE",   "  2026-04-08", "YYYY-MM-DD", "Leading whitespace"),
]


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestCsutldtcParity:
    """Python and Java must produce IDENTICAL outputs for every scenario."""

    def setup_method(self):
        self.python_runner = PythonRunner()
        self.java_runner = _make_java_runner()

    def test_python_and_java_byte_identical(self):
        """The single most important test: every field must match exactly."""
        mismatches = []

        for vid, ls_date, fmt, desc in SCENARIOS:
            req = RunRequest(
                program="CSUTLDTC",
                vector_id=vid,
                inputs={"LS_DATE": ls_date, "LS_DATE_FORMAT": fmt},
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
                # Build a precise diff so the failure message is actionable
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
            f"\n\nCross-language parity failed on {len(mismatches)} of "
            f"{len(SCENARIOS)} scenarios:\n\n" + "\n\n".join(mismatches)
        )

    def test_raw_message_is_always_80_chars(self):
        """The COBOL LS-RESULT contract: result is exactly 80 characters."""
        for vid, ls_date, fmt, desc in SCENARIOS:
            req = RunRequest(
                program="CSUTLDTC",
                vector_id=vid,
                inputs={"LS_DATE": ls_date, "LS_DATE_FORMAT": fmt},
            )
            jv = self.java_runner.run(req)
            assert jv.ok, f"{vid}: {jv.errors}"
            raw = jv.outputs["RAW_MESSAGE"]
            assert len(raw) == 80, (
                f"{vid} ({desc}): RAW_MESSAGE length {len(raw)} != 80\n"
                f"  content: {raw!r}"
            )

    def test_severity_only_zero_or_three(self):
        """COBOL CSUTLDTC only ever returns severity 0 (success) or 3 (any error)."""
        for vid, ls_date, fmt, _desc in SCENARIOS:
            req = RunRequest(
                program="CSUTLDTC",
                vector_id=vid,
                inputs={"LS_DATE": ls_date, "LS_DATE_FORMAT": fmt},
            )
            jv = self.java_runner.run(req)
            assert jv.outputs["SEVERITY"] in ("0", "3"), (
                f"{vid}: unexpected SEVERITY {jv.outputs['SEVERITY']!r}"
            )


# ── Differential harness with hand-built expected outputs ──────────────────


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestCsutldtcThroughHarness:
    """End-to-end: drive Java through the differential harness against
    expected outputs derived from the COBOL/Python contract."""

    def test_valid_dates_at_100_percent(self):
        """A small set of well-defined expected outputs that I derived by hand
        from the Python source. If both Python and Java match these, the
        differential harness reports 100% confidence."""
        vectors = [
            DiffVector(
                vector_id="VALID_ISO",
                program="CSUTLDTC",
                inputs={"LS_DATE": "2026-04-08", "LS_DATE_FORMAT": "YYYY-MM-DD"},
                expected_outputs={
                    "SEVERITY": "0",
                    "RESULT_TEXT": "Date is valid  ",
                    "LILLIAN": "161980",
                    "RAW_MESSAGE": (
                        "0000Mesg Code:0000 Date is valid   "
                        "TstDate:2026-04-08 Mask used:YYYY-MM-DD      "
                    ),
                },
                actual_outputs={},
                field_types={
                    "SEVERITY": "str",
                    "RESULT_TEXT": "str",
                    "LILLIAN": "str",
                    "RAW_MESSAGE": "str",
                },
            ),
            DiffVector(
                vector_id="MIN_VALID",
                program="CSUTLDTC",
                inputs={"LS_DATE": "1582-10-15", "LS_DATE_FORMAT": "YYYY-MM-DD"},
                expected_outputs={
                    "SEVERITY": "0",
                    "RESULT_TEXT": "Date is valid  ",
                    "LILLIAN": "2",
                    "RAW_MESSAGE": (
                        "0000Mesg Code:0000 Date is valid   "
                        "TstDate:1582-10-15 Mask used:YYYY-MM-DD      "
                    ),
                },
                actual_outputs={},
                field_types={
                    "SEVERITY": "str",
                    "RESULT_TEXT": "str",
                    "LILLIAN": "str",
                    "RAW_MESSAGE": "str",
                },
            ),
            DiffVector(
                vector_id="BAD_PIC",
                program="CSUTLDTC",
                inputs={"LS_DATE": "2026-04-08", "LS_DATE_FORMAT": "BOGUSFMT"},
                expected_outputs={
                    "SEVERITY": "3",
                    "RESULT_TEXT": "Bad Pic String ",
                    "LILLIAN": "0",
                    "RAW_MESSAGE": (
                        "0003Mesg Code:0777 Bad Pic String  "
                        "TstDate:2026-04-08 Mask used:BOGUSFMT        "
                    ),
                },
                actual_outputs={},
                field_types={
                    "SEVERITY": "str",
                    "RESULT_TEXT": "str",
                    "LILLIAN": "str",
                    "RAW_MESSAGE": "str",
                },
            ),
            DiffVector(
                vector_id="MONTH_13_ISO",
                program="CSUTLDTC",
                inputs={"LS_DATE": "2026-13-08", "LS_DATE_FORMAT": "YYYY-MM-DD"},
                expected_outputs={
                    "SEVERITY": "3",
                    "RESULT_TEXT": "Invalid month  ",
                    "LILLIAN": "0",
                    "RAW_MESSAGE": (
                        "0003Mesg Code:0777 Invalid month   "
                        "TstDate:2026-13-08 Mask used:YYYY-MM-DD      "
                    ),
                },
                actual_outputs={},
                field_types={
                    "SEVERITY": "str",
                    "RESULT_TEXT": "str",
                    "LILLIAN": "str",
                    "RAW_MESSAGE": "str",
                },
            ),
            DiffVector(
                vector_id="EMPTY_DATE",
                program="CSUTLDTC",
                inputs={"LS_DATE": "", "LS_DATE_FORMAT": "YYYY-MM-DD"},
                expected_outputs={
                    "SEVERITY": "3",
                    "RESULT_TEXT": "Insufficient   ",
                    "LILLIAN": "0",
                    "RAW_MESSAGE": (
                        "0003Mesg Code:0777 Insufficient    "
                        "TstDate:           Mask used:YYYY-MM-DD      "
                    ),
                },
                actual_outputs={},
                field_types={
                    "SEVERITY": "str",
                    "RESULT_TEXT": "str",
                    "LILLIAN": "str",
                    "RAW_MESSAGE": "str",
                },
            ),
        ]

        # Drive through Java runner
        populate_actuals(vectors, _make_java_runner())
        report = run_vectors(vectors)

        assert report.confidence_score == 100.0, (
            f"CSUTLDTC Java pilot failed: {report.failed} of {report.total_vectors} "
            f"vectors mismatched.\n"
            f"Mismatches: {report.mismatches}"
        )
        assert report.passed == 5
        assert report.failed == 0


# ── Python-side sanity (no Java needed) ───────────────────────────────────


class TestPythonRunVectorWorks:
    """Independent of the Java side: the Python adapter from W2 still works."""

    def test_python_runner_csutldtc_valid(self):
        runner = PythonRunner()
        response = runner.run(RunRequest(
            program="CSUTLDTC",
            vector_id="V001",
            inputs={"LS_DATE": "2026-04-08", "LS_DATE_FORMAT": "YYYY-MM-DD"},
        ))
        assert response.ok, response.errors
        assert response.outputs["SEVERITY"] == "0"
        assert response.outputs["RESULT_TEXT"] == "Date is valid  "

    def test_python_runner_csutldtc_invalid_format(self):
        runner = PythonRunner()
        response = runner.run(RunRequest(
            program="CSUTLDTC",
            vector_id="V002",
            inputs={"LS_DATE": "2026-04-08", "LS_DATE_FORMAT": "BOGUS"},
        ))
        assert response.ok
        assert response.outputs["SEVERITY"] == "3"
        assert response.outputs["RESULT_TEXT"] == "Bad Pic String "
