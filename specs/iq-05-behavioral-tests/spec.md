# IQ-05: Behavioral Test Generation with Assertions — Design Specification

**Status**: In Progress
**Created**: 2026-03-15
**Prerequisites**: IQ-01 (conditional logic), IQ-02 (copybook fields), IQ-04 (business rules)

---

## Problem Statement

Generated tests only check `hasattr` and `callable`. No test verifies that the
reimplemented code produces correct output for a given input. Tests should encode
the decision tree from the COBOL source as expected behavior.

### Evidence

`test_cosgn00c.py` has 16 tests; 10 are `hasattr` checks, 6 are `# TODO`
comments. None assert business behavior.

Source: `test-codebases/carddemo/_analysis/generated_tests/test_cosgn00c.py`

---

## Design Decisions

### DD-01: One test per leaf branch in the decision tree

Each conditional block branch from IQ-01 produces a test scenario. For
EVALUATE with nested IF, each combination of WHEN branch + IF branch = one test.
Test names encode the path:
`test_read_user_sec_file_resp_0_password_match_admin`.

### DD-02: Typed fixtures from IQ-02 copybook metadata

Fixture helpers pre-populate copybook fields using IQ-02 metadata:
- `str` + max_length → filled string
- `int` + max_digits → valid integer
- `Decimal` + scale → valid decimal

### DD-03: Assertions from IQ-04 business rules + data flows

For each branch, assertions check data flow targets (MOVE destinations) and
service calls (XCTL/CALL targets) from the conditional block body.

### DD-04: New `_generate_behavioral_tests()` alongside existing generators

Existing structural tests kept intact. New function adds behavioral tests.

### DD-05: Generated tests use pytest.mark.skip for unimplemented skeletons

Behavioral tests are marked `@pytest.mark.skip(reason="skeleton not yet
implemented")` so they appear as pending work without failing the suite.

---

## Test file: `pipeline/tests/test_behavioral_gen.py`
