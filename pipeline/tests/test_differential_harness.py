"""Tests for differential_harness.py — field-by-field equivalence checking.

IQ-09: Runs test vectors against golden COBOL outputs and modern reimplementations,
producing a field-by-field diff report with CobolDecimal-aware numeric comparison.
"""

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from differential_harness import (
    TestVector,
    FieldMismatch,
    DiffReport,
    compare_fields,
    run_vectors,
    generate_report,
    load_golden_vectors,
    save_golden_vectors,
    render_report_text,
)


def _make_vector(
    vector_id="V001",
    inputs=None,
    expected=None,
    actual=None,
    field_types=None,
) -> TestVector:
    return TestVector(
        vector_id=vector_id,
        program="TESTPGM",
        inputs=inputs or {},
        expected_outputs=expected or {},
        actual_outputs=actual or {},
        field_types=field_types or {},
    )


class TestFieldComparison:
    """compare_fields performs type-aware field comparison."""

    def test_identical_strings_pass(self):
        """Identical string values → no mismatch."""
        mismatches = compare_fields(
            expected={"WS-NAME": "JOHN DOE"},
            actual={"WS-NAME": "JOHN DOE"},
            field_types={"WS-NAME": "str"},
        )
        assert len(mismatches) == 0

    def test_trailing_spaces_trimmed_for_strings(self):
        """COBOL pads strings with trailing spaces — these should be trimmed."""
        mismatches = compare_fields(
            expected={"WS-NAME": "JOHN DOE        "},
            actual={"WS-NAME": "JOHN DOE"},
            field_types={"WS-NAME": "str"},
        )
        assert len(mismatches) == 0

    def test_string_difference_fails(self):
        """Different strings → mismatch with expected vs actual."""
        mismatches = compare_fields(
            expected={"WS-NAME": "JOHN"},
            actual={"WS-NAME": "JANE"},
            field_types={"WS-NAME": "str"},
        )
        assert len(mismatches) == 1
        assert mismatches[0].field == "WS-NAME"
        assert mismatches[0].expected == "JOHN"
        assert mismatches[0].actual == "JANE"

    def test_identical_integers_pass(self):
        """Identical integer values → no mismatch."""
        mismatches = compare_fields(
            expected={"WS-COUNT": "42"},
            actual={"WS-COUNT": "42"},
            field_types={"WS-COUNT": {"type": "int", "digits": 5}},
        )
        assert len(mismatches) == 0

    def test_numeric_same_pic_value_passes(self):
        """Two values that produce the same CobolDecimal under the same PIC → pass.
        123.456 and 123.45 under PIC S9(5)V99 (scale=2) both store 123.45."""
        mismatches = compare_fields(
            expected={"WS-AMT": "123.456"},
            actual={"WS-AMT": "123.45"},
            field_types={"WS-AMT": {"type": "Decimal", "digits": 5, "scale": 2, "signed": True}},
        )
        assert len(mismatches) == 0

    def test_numeric_difference_outside_pic_fails(self):
        """Values that differ even under the same PIC → mismatch."""
        mismatches = compare_fields(
            expected={"WS-AMT": "123.45"},
            actual={"WS-AMT": "123.99"},
            field_types={"WS-AMT": {"type": "Decimal", "digits": 5, "scale": 2, "signed": True}},
        )
        assert len(mismatches) == 1
        assert mismatches[0].field == "WS-AMT"

    def test_missing_actual_field_fails(self):
        """Expected field not present in actual → mismatch."""
        mismatches = compare_fields(
            expected={"WS-CODE": "0"},
            actual={},
            field_types={"WS-CODE": "str"},
        )
        assert len(mismatches) == 1
        assert "missing" in mismatches[0].actual.lower() or mismatches[0].actual == ""


class TestVectorRunner:
    """run_vectors executes comparison across multiple vectors."""

    def test_all_pass_gives_100_confidence(self):
        """All vectors matching → confidence 100.0."""
        vectors = [
            _make_vector("V1", expected={"F1": "A"}, actual={"F1": "A"}, field_types={"F1": "str"}),
            _make_vector("V2", expected={"F1": "B"}, actual={"F1": "B"}, field_types={"F1": "str"}),
        ]
        report = run_vectors(vectors)
        assert report.total_vectors == 2
        assert report.passed == 2
        assert report.failed == 0
        assert report.confidence_score == 100.0

    def test_one_fail_reduces_confidence(self):
        """One mismatch out of two vectors → 50% confidence."""
        vectors = [
            _make_vector("V1", expected={"F1": "A"}, actual={"F1": "A"}, field_types={"F1": "str"}),
            _make_vector("V2", expected={"F1": "B"}, actual={"F1": "X"}, field_types={"F1": "str"}),
        ]
        report = run_vectors(vectors)
        assert report.total_vectors == 2
        assert report.passed == 1
        assert report.failed == 1
        assert report.confidence_score == 50.0

    def test_mismatches_have_evidence(self):
        """Failed vectors include mismatch details."""
        vectors = [
            _make_vector("V1", expected={"F1": "A"}, actual={"F1": "B"}, field_types={"F1": "str"}),
        ]
        report = run_vectors(vectors)
        assert len(report.mismatches) == 1
        assert report.mismatches[0]["vector_id"] == "V1"
        assert len(report.mismatches[0]["fields"]) == 1

    def test_empty_vectors_gives_zero_confidence(self):
        """No vectors → 0 confidence (nothing verified)."""
        report = run_vectors([])
        assert report.total_vectors == 0
        assert report.confidence_score == 0.0


class TestReportGeneration:
    """Diff reports in JSON and human-readable text."""

    def test_json_report_has_required_fields(self):
        """JSON report includes program, total, passed, failed, confidence, mismatches."""
        vectors = [
            _make_vector("V1", expected={"F1": "A"}, actual={"F1": "A"}, field_types={"F1": "str"}),
        ]
        report = run_vectors(vectors)
        json_str = generate_report(report)
        data = json.loads(json_str)
        assert "program" in data
        assert "total_vectors" in data
        assert "passed" in data
        assert "failed" in data
        assert "confidence_score" in data
        assert "mismatches" in data

    def test_text_report_readable(self):
        """Text report is human-readable with summary line."""
        vectors = [
            _make_vector("V1", expected={"F1": "A"}, actual={"F1": "B"}, field_types={"F1": "str"}),
        ]
        report = run_vectors(vectors)
        text = render_report_text(report)
        assert "TESTPGM" in text
        assert "0.0%" in text or "0%" in text
        assert "F1" in text


class TestGoldenVectorIO:
    """Load and save golden test vectors."""

    def test_round_trip(self, tmp_path):
        """save then load produces identical vectors."""
        vectors = [
            TestVector(
                vector_id="V001",
                program="CODATE01",
                inputs={"WS-DATE-IN": "20260315"},
                expected_outputs={"WS-DATE-OUT": "03/15/2026"},
                actual_outputs={},
                field_types={"WS-DATE-OUT": "str"},
            ),
        ]
        save_golden_vectors(vectors, "CODATE01", str(tmp_path))
        loaded = load_golden_vectors("CODATE01", str(tmp_path))
        assert len(loaded) == 1
        assert loaded[0].vector_id == "V001"
        assert loaded[0].expected_outputs["WS-DATE-OUT"] == "03/15/2026"

    def test_load_nonexistent_returns_empty(self, tmp_path):
        """Loading from nonexistent file returns empty list."""
        loaded = load_golden_vectors("NONEXISTENT", str(tmp_path))
        assert loaded == []
