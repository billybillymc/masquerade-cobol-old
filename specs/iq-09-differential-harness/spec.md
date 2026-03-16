# IQ-09: Differential Test Harness — Design Specification

**Status**: In Progress
**Created**: 2026-03-15
**Prerequisites**: IQ-03 (CobolDecimal for numeric comparison), IQ-05 (behavioral tests)

---

## Problem Statement

There is no way to verify that a reimplementation is behaviorally equivalent to
the original COBOL. Without this, no confidence score is meaningful.

---

## Design Decisions

### DD-01: Test vector format — JSON with typed fields
Each vector: `vector_id`, `program`, `inputs`, `expected_outputs`, `field_types`.
Field types drive the comparator: `str` → exact match (trailing-space trimmed),
`int`/`Decimal` → CobolDecimal-aware comparison with PIC metadata.

### DD-02: CobolDecimal-aware numeric comparison
Construct CobolDecimal from field_types metadata, assign both expected and actual,
compare resulting values. Tolerance is "same PIC produces same stored value".

### DD-03: Diff report — JSON + human-readable
Includes: total vectors, passed, failed, confidence_score (pass_rate * 100),
mismatches list with field/expected/actual/type.

### DD-04: Golden output loader
JSON files at `_analysis/golden_vectors/{program}.json`.

---

## New module: `pipeline/differential_harness.py`
## Test file: `pipeline/tests/test_differential_harness.py`
