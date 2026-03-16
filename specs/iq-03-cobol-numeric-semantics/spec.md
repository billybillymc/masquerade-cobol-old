# IQ-03: COBOL Numeric Semantics Module — Design Specification

**Status**: In Progress
**Created**: 2026-03-15
**Prerequisites**: IQ-02 (field metadata provides digits/scale/signed/usage)
**Prerequisite for**: IQ-05 (behavioral test fixtures), IQ-09 (differential harness)

---

## Problem Statement

`_pic_to_python_type()` maps PIC to `int`, `str`, or `Decimal` without preserving
the exact precision, scale, sign, or overflow rules. COBOL arithmetic has specific
intermediate precision, truncation on overflow, implied decimal alignment, and
rounding behavior that differ from Python/Java defaults. This is the single most
common source of reimplementation bugs.

### Evidence

`PIC S9(7)V9(2) COMP-3` maps to `Decimal` but loses the constraint that it has
exactly 7 integer digits and 2 decimal places, overflows silently, and truncates
on assignment.

Source: `skeleton_generator._pic_to_field_metadata()` produces
`{'pic': 'S9(07)V99', 'max_digits': 7, 'scale': 2, 'signed': True, 'usage': 'COMP-3'}`
but nothing enforces these constraints at runtime.

Real arithmetic in carddemo:
- `CBTRN02C.cbl:403` — `COMPUTE WS-TEMP-BAL = ACCT-CURR-CYC-CREDIT - ACCT-CURR-CYC-DEBIT + DALYTRAN-AMT`
  (three S9(10)V99 / S9(09)V99 fields — intermediate precision matters)
- `COPAUA0C.cbl:871` — `COMPUTE WS-TIME-WITH-MS = (WS-CUR-TIME-N6 * 1000) + WS-CUR-TIME-MS`
  (multiplication then addition — intermediate digit count expands)
- `COPAUA0C.cbl:874` — `COMPUTE PA-AUTH-DATE-9C = 99999 - WS-YYDDD`
  (subtraction with literal — left-truncation possible)
- Zero `ON SIZE ERROR` clauses found in carddemo — all truncation is silent.

---

## Design Decisions

### DD-01: Truncate-left on overflow (COBOL default)

**Choice**: `CobolDecimal` silently truncates leftmost digits when a value exceeds
the PIC's integer digit capacity. An optional `on_size_error='raise'` mode is
available for reimplementers who want safety.

**Alternatives considered**:
- *Raise by default*: Safer for modern code, but produces false positives in the
  differential harness (IQ-09) since COBOL programs rely on silent truncation.

**Reasoning**: The purpose of this module is faithful COBOL semantics for
correctness verification. The carddemo codebase has zero `ON SIZE ERROR` clauses —
every arithmetic statement relies on silent truncation. If we raise by default,
IQ-09 will flag legitimate COBOL behavior as errors.

**Intended outcome**: `CobolDecimal(digits=5, scale=0).set(123456)` silently
stores `23456` (truncates leading 1). With `on_size_error='raise'`, it raises
`CobolOverflowError`.

---

### DD-02: Truncate fractional digits by default, ROUNDED opt-in

**Choice**: Default rounding mode is truncation toward zero. A `rounded=True`
parameter on arithmetic methods enables COBOL's `ROUNDED` behavior (ROUND_HALF_UP).

**Reasoning**: COBOL truncates by default; `ROUNDED` is opt-in per statement. No
`ROUNDED` phrases were found in carddemo. The COBOL standard specifies
ROUND_HALF_UP for the `ROUNDED` phrase (0.5 rounds away from zero).

**Intended outcome**: `CobolDecimal(digits=5, scale=2).set(Decimal('1.999'))` stores
`1.99` (truncated). With `rounded=True`, stores `2.00`.

---

### DD-03: Full COBOL intermediate precision rules

**Choice**: Implement the exact COBOL standard intermediate precision rules
(based on COBOL-85/2002 Appendix A) for all arithmetic operations.

**Rules** (op1 and op2 have `(d1, s1)` and `(d2, s2)` = integer digits, scale):

| Operation | Intermediate integer digits | Intermediate scale |
|-----------|---------------------------|-------------------|
| ADD / SUBTRACT | max(d1, d2) + 1 | max(s1, s2) |
| MULTIPLY | d1 + d2 | s1 + s2 |
| DIVIDE | ? (see below) | implementation-defined, use max(s1, s2) + dividend scale |
| COMPUTE (mixed) | Apply rules per sub-operation, left to right |

For DIVIDE: The COBOL standard says the intermediate result has enough digits to
hold the exact quotient up to the receiving field's precision. We use
`d1 + s2 + max(s1, s2)` integer digits and `max(s1, s2)` scale as a conservative
upper bound, then truncate on final assignment.

**Alternatives considered**:
- *Python arbitrary precision for intermediates*: Simpler — use `decimal.Decimal`
  with unlimited precision, truncate only on assignment. Covers 99% of cases but
  misses the rare edge where COBOL intermediate overflow truncates differently.

**Reasoning**: The user explicitly chose correctness over simplicity. The
intermediate precision rules are well-documented and finite. Implementing them
exactly means the differential harness (IQ-09) can catch true discrepancies
rather than precision artifacts.

**Intended outcome**: `COMPUTE X = A * B + C` where A is S9(5)V99, B is S9(3)V9,
C is S9(4)V99 computes `A * B` with intermediate precision (8 integer, 3 scale),
then adds C with intermediate precision (max(8,4)+1=9 integer, max(3,2)=3 scale),
then truncates to X's PIC on final assignment.

---

### DD-04: SPACES/blank coercion via from_display()

**Choice**: `CobolDecimal.from_display(value)` handles coercion:
- `SPACES` / empty string / `None` → `Decimal('0')`
- String of digits → parse with implied decimal point at scale position
- `ZEROS` / `'0'` → `Decimal('0')`
- Already `Decimal`, `int`, `float` → convert directly

**Reasoning**: COBOL's `MOVE SPACES TO numeric-field` yields zero. This is a
common initialization pattern. The `from_display()` method encapsulates this
coercion so reimplemented code doesn't need ad-hoc null checks.

---

### DD-05: Arithmetic-only, with storage_bytes property

**Choice**: `CobolDecimal` models precision, scale, sign, and arithmetic behavior.
Storage representation (COMP, COMP-3, DISPLAY) affects only the `storage_bytes`
property — not arithmetic.

**Reasoning**: COMP, COMP-3, and DISPLAY have identical arithmetic semantics.
Only byte-level storage differs. Modeling storage as a property (not behavior)
keeps the class focused. The `storage_bytes` property is useful for record layout
verification in IQ-09 but doesn't affect calculations.

**Storage size rules** (from COBOL standard):
- DISPLAY: 1 byte per digit (+ 1 for sign if separate)
- COMP-3 / PACKED-DECIMAL: ceil((total_digits + 1) / 2) bytes
- COMP / BINARY: 2 bytes (≤4 digits), 4 bytes (≤9), 8 bytes (≤18)

---

### DD-06: Light skeleton integration now, IQ-09 upgrade note

**Choice**: For IQ-03, build `cobol_decimal.py` as a self-contained module with
full arithmetic semantics. Add an import to the skeleton header and a comment on
decimal fields pointing to `CobolDecimal`. Full integration (replacing bare
`Decimal` field types with `CobolDecimal`) is deferred to IQ-09.

**Reasoning**: The `CobolDecimal` class needs to be battle-tested through IQ-05
(behavioral tests) and IQ-09 (differential harness) before we couple it to
skeleton output. Over-coupling now makes skeletons less readable for developers
who just want field layouts.

**IQ-09 UPGRADE NOTE**: When IQ-09 (Differential Test Harness) is implemented,
skeleton integration MUST be upgraded:
1. Replace `Decimal` field types with `CobolDecimal` for all numeric fields
2. Use field metadata (digits, scale, signed, usage) from IQ-02 to construct
   `CobolDecimal` instances as default values
3. Arithmetic in skeleton method bodies should use `CobolDecimal` operations
   This is a BLOCKING requirement for IQ-09's field-by-field comparison to work
   correctly — without it, the harness cannot detect precision/truncation bugs.

---

## Data Model

### CobolDecimal class

```python
class CobolDecimal:
    """Fixed-point decimal with COBOL PIC semantics.

    Enforces exact precision, scale, sign, and overflow behavior
    matching the COBOL standard.
    """
    digits: int          # integer digit capacity (from PIC 9 count before V)
    scale: int           # decimal places (from PIC 9 count after V)
    signed: bool         # True if PIC has S prefix
    usage: str           # 'DISPLAY', 'COMP', 'COMP-3', 'BINARY'
    on_size_error: str   # 'truncate' (default) or 'raise'
    _value: Decimal      # internal stored value (always within PIC range)

    # Properties
    max_value -> Decimal      # e.g. 99999.99 for PIC 9(5)V99
    min_value -> Decimal      # e.g. -99999.99 for PIC S9(5)V99, 0 for unsigned
    storage_bytes -> int      # byte size based on usage
    value -> Decimal          # current value

    # Mutation
    set(value, rounded=False) -> CobolDecimal   # assign with truncation
    from_display(raw) -> CobolDecimal           # coerce from string/None/SPACES

    # Arithmetic (returns NEW CobolDecimal with intermediate precision)
    add(other) -> CobolDecimal
    subtract(other) -> CobolDecimal
    multiply(other) -> CobolDecimal
    divide(other) -> CobolDecimal

    # Assignment (truncate intermediate to target PIC)
    assign_to(target: CobolDecimal, rounded=False) -> CobolDecimal

    # Python protocol
    __eq__, __lt__, __le__, __gt__, __ge__  # compare on value
    __repr__, __str__
    __add__, __sub__, __mul__, __truediv__  # operator overloads
```

### CobolOverflowError

```python
class CobolOverflowError(ArithmeticError):
    """Raised when on_size_error='raise' and value exceeds PIC capacity."""
    pass
```

---

## Test Strategy

Tests are pure unit tests — no file I/O, no codebase dependency. Each test
constructs `CobolDecimal` instances directly and asserts arithmetic behavior.

Primary test vectors derived from:
- carddemo `CBTRN02C.cbl:403` — balance calculation with three operands
- carddemo `COPAUA0C.cbl:871` — multiplication then addition
- COBOL standard Appendix A — intermediate precision edge cases

Test file: `pipeline/tests/test_cobol_decimal.py`
