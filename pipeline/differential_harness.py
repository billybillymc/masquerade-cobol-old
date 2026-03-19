"""
Differential test harness — field-by-field equivalence checking between
COBOL golden outputs and modern reimplementations.

Uses CobolDecimal (IQ-03) for numeric comparison with PIC-aware tolerance.
Produces JSON and human-readable diff reports with confidence scores.

Golden vectors stored at: _analysis/golden_vectors/{program}.json
"""

import json
import sys
from dataclasses import dataclass, field, asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional, Union

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cobol_decimal import CobolDecimal


# ── Data model ──────────────────────────────────────────────────────────────


@dataclass
class DiffVector:
    """A single test vector: inputs → expected outputs, with optional actuals."""
    vector_id: str
    program: str
    inputs: dict[str, str]
    expected_outputs: dict[str, str]
    actual_outputs: dict[str, str]
    field_types: dict[str, Union[str, dict]]  # "str" or {"type": "Decimal", "digits": 5, "scale": 2, ...}


@dataclass
class FieldMismatch:
    """A single field-level mismatch."""
    field: str
    expected: str
    actual: str
    field_type: str
    reason: str = ""


@dataclass
class DiffReport:
    """Equivalence report across all vectors for a program."""
    program: str
    total_vectors: int
    passed: int
    failed: int
    confidence_score: float  # passed / total * 100, or 0 if no vectors
    mismatches: list[dict] = field(default_factory=list)  # [{vector_id, fields: [FieldMismatch]}]


# ── Field comparison ────────────────────────────────────────────────────────


def _compare_string(expected: str, actual: str) -> bool:
    """Compare strings with COBOL trailing-space trimming."""
    return expected.rstrip() == actual.rstrip()


def _compare_numeric(
    expected: str,
    actual: str,
    field_meta: dict,
) -> bool:
    """Compare numeric values using CobolDecimal PIC semantics.

    Both values are assigned to the same PIC definition. If they produce
    the same stored value, they're considered equal.
    """
    digits = field_meta.get("digits", 9)
    scale = field_meta.get("scale", 0)
    signed = field_meta.get("signed", True)

    try:
        cd_expected = CobolDecimal(digits=digits, scale=scale, signed=signed)
        cd_expected.set(Decimal(str(expected)))

        cd_actual = CobolDecimal(digits=digits, scale=scale, signed=signed)
        cd_actual.set(Decimal(str(actual)))

        return cd_expected.value == cd_actual.value
    except (InvalidOperation, ValueError):
        # If either can't be parsed as a number, fall back to string compare
        return str(expected).rstrip() == str(actual).rstrip()


def compare_fields(
    expected: dict[str, str],
    actual: dict[str, str],
    field_types: dict[str, Union[str, dict]],
) -> list[FieldMismatch]:
    """Compare expected vs actual field values with type-aware comparison.

    Returns a list of mismatches (empty = all fields match).
    """
    mismatches = []

    for field_name, expected_val in expected.items():
        ft = field_types.get(field_name, "str")

        actual_val = actual.get(field_name)
        if actual_val is None:
            mismatches.append(FieldMismatch(
                field=field_name,
                expected=str(expected_val),
                actual="<missing>",
                field_type=ft if isinstance(ft, str) else ft.get("type", "str"),
                reason="Field not present in actual output",
            ))
            continue

        # Determine comparison strategy
        if isinstance(ft, dict):
            ftype = ft.get("type", "str")
        else:
            ftype = ft

        if ftype in ("int", "Decimal"):
            meta = ft if isinstance(ft, dict) else {"type": ftype}
            match = _compare_numeric(str(expected_val), str(actual_val), meta)
        else:
            match = _compare_string(str(expected_val), str(actual_val))

        if not match:
            mismatches.append(FieldMismatch(
                field=field_name,
                expected=str(expected_val),
                actual=str(actual_val),
                field_type=ftype,
                reason=f"{ftype} comparison failed",
            ))

    return mismatches


# ── Vector runner ───────────────────────────────────────────────────────────


def run_vectors(vectors: list[DiffVector]) -> DiffReport:
    """Run all test vectors and produce a diff report."""
    if not vectors:
        return DiffReport(
            program="",
            total_vectors=0,
            passed=0,
            failed=0,
            confidence_score=0.0,
        )

    program = vectors[0].program
    total = len(vectors)
    passed = 0
    failed = 0
    all_mismatches = []

    for vec in vectors:
        field_mismatches = compare_fields(
            vec.expected_outputs,
            vec.actual_outputs,
            vec.field_types,
        )

        if not field_mismatches:
            passed += 1
        else:
            failed += 1
            all_mismatches.append({
                "vector_id": vec.vector_id,
                "fields": [
                    {
                        "field": m.field,
                        "expected": m.expected,
                        "actual": m.actual,
                        "type": m.field_type,
                        "reason": m.reason,
                    }
                    for m in field_mismatches
                ],
            })

    confidence = (passed / total * 100) if total > 0 else 0.0

    return DiffReport(
        program=program,
        total_vectors=total,
        passed=passed,
        failed=failed,
        confidence_score=confidence,
        mismatches=all_mismatches,
    )


# ── Report generation ──────────────────────────────────────────────────────


def generate_report(report: DiffReport) -> str:
    """Generate JSON diff report."""
    data = {
        "program": report.program,
        "total_vectors": report.total_vectors,
        "passed": report.passed,
        "failed": report.failed,
        "confidence_score": report.confidence_score,
        "mismatches": report.mismatches,
    }
    return json.dumps(data, indent=2)


def render_report_text(report: DiffReport) -> str:
    """Generate human-readable text diff report."""
    lines = []
    lines.append(f"Differential Test Report: {report.program}")
    lines.append(f"=" * 50)
    lines.append(f"Total vectors: {report.total_vectors}")
    lines.append(f"Passed: {report.passed}")
    lines.append(f"Failed: {report.failed}")
    lines.append(f"Confidence: {report.confidence_score:.1f}%")
    lines.append(f"")

    if report.mismatches:
        lines.append(f"Mismatches:")
        lines.append(f"-" * 40)
        for mm in report.mismatches:
            lines.append(f"  Vector {mm['vector_id']}:")
            for fm in mm["fields"]:
                lines.append(
                    f"    {fm['field']}: expected={fm['expected']} "
                    f"actual={fm['actual']} ({fm['type']})"
                )
        lines.append(f"")
    else:
        lines.append(f"All vectors passed.")

    return "\n".join(lines)


# ── Golden vector I/O ──────────────────────────────────────────────────────


def save_golden_vectors(
    vectors: list[DiffVector],
    program_id: str,
    output_dir: str,
) -> Path:
    """Save golden vectors to JSON."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"{program_id}.json"

    data = []
    for vec in vectors:
        data.append({
            "vector_id": vec.vector_id,
            "program": vec.program,
            "inputs": vec.inputs,
            "expected_outputs": vec.expected_outputs,
            "field_types": vec.field_types,
        })

    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return file_path


def load_golden_vectors(
    program_id: str,
    vectors_dir: str,
) -> list[DiffVector]:
    """Load golden vectors from JSON."""
    file_path = Path(vectors_dir) / f"{program_id}.json"
    if not file_path.exists():
        return []

    data = json.loads(file_path.read_text(encoding="utf-8"))
    vectors = []
    for d in data:
        vectors.append(DiffVector(
            vector_id=d["vector_id"],
            program=d["program"],
            inputs=d.get("inputs", {}),
            expected_outputs=d.get("expected_outputs", {}),
            actual_outputs={},  # actuals are populated at runtime
            field_types=d.get("field_types", {}),
        ))

    return vectors
