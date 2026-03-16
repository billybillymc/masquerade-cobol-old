# IQ-02: Wire Copybook Fields into Skeletons — Design Specification

**Status**: In Progress
**Created**: 2026-03-15
**Prerequisite**: IQ-01 (complete)
**Prerequisite for**: IQ-03 (CobolDecimal consumes field metadata), IQ-05 (typed fixtures), IQ-06 (repository record types)

---

## Problem Statement

`skeleton_generator._generate_dataclass_for_copybook()` produces empty dataclasses
with `pass` bodies and a `TODO` comment. Meanwhile, `copybook_dict.py` already
parses `.cpy` files into fully typed field catalogs (`CopybookField` with PIC,
USAGE, OCCURS, REDEFINES, level-88 conditions). These two modules are not
connected.

### Evidence

Skeleton `cosgn00c.py` has 8 copybook dataclasses, all containing only `pass`:
```python
@dataclass
class Csusr01y:
    """Data structure from COBOL copybook CSUSR01Y.

    TODO: Map fields from copybook definition.
    """
    pass
```

Source: `test-codebases/carddemo/_analysis/skeletons/cosgn00c.py` lines 67–72.

`CSUSR01Y.cpy` defines 6 fields under `SEC-USER-DATA` (PIC X(08), X(20), X(20),
X(08), X(01), X(23)). `copybook_dict.parse_copybook()` already parses all of them.

Source: `test-codebases/carddemo/app/cpy/CSUSR01Y.cpy` lines 17–23.

---

## Design Decisions

### DD-01: Nested dataclasses for group hierarchy

**Choice**: COBOL group items (fields with no PIC that have children at higher
level numbers) become nested `@dataclass` types. The parent dataclass has a field
typed as the nested class.

**Alternatives considered**:
- *Flat fields*: All elementary items at top level. Loses group structure, risks
  name collisions, and doesn't support qualified references (IQ-10).

**Reasoning**: COBOL groups are sub-records with semantic meaning. `COCOM01Y` has
`CDEMO-GENERAL-INFO` (level 05) containing `CDEMO-FROM-TRANID` (level 10). The
group boundary matters: the commarea is passed between programs, and groups within
it are independently meaningful. Nested dataclasses preserve this and map cleanly
to IQ-10's symbol table.

**Intended outcome**: `COCOM01Y` generates:
```python
@dataclass
class CdemoGeneralInfo:
    cdemo_from_tranid: str = ''  # PIC X(04)
    ...

@dataclass
class CarddemoCommarea:
    cdemo_general_info: CdemoGeneralInfo = field(default_factory=CdemoGeneralInfo)
    cdemo_customer_info: CdemoCustomerInfo = field(default_factory=CdemoCustomerInfo)
    ...
```

**Source evidence**: `COCOM01Y.cpy` lines 19–44 show 01 → 05 → 10 → 88 hierarchy.

---

### DD-02: REDEFINES as Optional field with comment

**Choice**: Generate both the original field and the redefining field. The
redefining field gets `Optional[T] = None` and a `# REDEFINES <original>` comment.

**Alternatives considered**:
- *Union type*: `field: str | WsDateParts` — misleading since both coexist in COBOL.
- *Skip redefining field*: Loses information the reimplementer needs.

**Reasoning**: In COBOL, REDEFINES creates two views over the same memory. In
Python, they must be separate fields since there's no memory overlay. Making the
redefining field Optional with None default means the dataclass is instantiable
with just the original, and the reimplementer can see both views.

**Intended outcome**:
```python
ws_date_field: str = ''             # PIC X(08)
ws_date_parts: Optional[WsDateParts] = None  # REDEFINES WS-DATE-FIELD
```

---

### DD-03: Level-88 conditions as class constants

**Choice**: Level-88 conditions become class-level constants on the dataclass that
owns the parent field: `CDEMO_USRTYP_ADMIN: str = 'A'`.

**Alternatives considered**:
- *Enum type*: Over-engineers single-condition cases; considered for future
  enhancement when 2+ conditions exist on a field.
- *Validator/property*: `is_admin()` properties. Matches COBOL usage patterns but
  adds method overhead for a simple value check.

**Reasoning**: Class constants are the simplest representation that is discoverable,
grep-able, and usable in comparisons. They appear at class scope so they're
obviously constants, not instance fields. The constant name includes the original
COBOL name for traceability.

**Intended outcome**:
```python
@dataclass
class CdemoGeneralInfo:
    CDEMO_USRTYP_ADMIN: ClassVar[str] = 'A'
    CDEMO_USRTYP_USER: ClassVar[str] = 'U'
    ...
    cdemo_user_type: str = ''  # PIC X(01)
```

---

### DD-04: OCCURS as pre-populated list[T]

**Choice**: OCCURS N generates `list[T]` with `field(default_factory=lambda: [T() for _ in range(N)])`. A metadata entry `occurs=N` records the COBOL array size.

**Alternatives considered**:
- *Empty list*: `list[T] = field(default_factory=list)`. Loses the fixed-size
  semantics that COBOL enforces.
- *tuple[T, ...]*: Immutable, but COBOL arrays are mutable.

**Reasoning**: COBOL OCCURS defines a fixed-size array. Pre-populating preserves
this contract and prevents index-out-of-range on first access. The metadata
`occurs=N` allows validators or IQ-03 to enforce the size constraint.

**Intended outcome**:
```python
ws_entry: list[WsEntry] = field(
    default_factory=lambda: [WsEntry() for _ in range(10)],
    metadata={'occurs': 10}
)
```

---

### DD-05: FILLER fields skipped with record-size comment

**Choice**: Fields named `FILLER` are omitted from the generated dataclass. A
comment on the class docstring notes the total COBOL record size in bytes.

**Reasoning**: FILLER exists for byte-level layout alignment, which has no meaning
in Python dataclasses. Including them adds noise without value. The total record
size comment gives the reimplementer enough context to verify layout fidelity.

---

### DD-06: Copybook resolution via optional CopybookDictionary parameter

**Choice**: `_generate_dataclass_for_copybook()` gains an optional
`copybook_dict: CopybookDictionary | None` parameter. When provided, it looks up
the copybook and generates typed fields. When `None`, it falls back to the current
`pass` stub.

**Reasoning**: Backward compatibility. Existing tests and callers that don't have
a codebase directory continue to work. The `generate_all_skeletons()` function
already has `codebase_dir` and can instantiate the dictionary.

---

### DD-07: Enforced type metadata via dataclass field metadata

**Choice**: Every generated field carries `metadata={}` with machine-readable
COBOL type constraints:

| PIC Pattern | Python Type | Metadata |
|---|---|---|
| `X(n)` / `A(n)` | `str` | `{'pic': 'X(08)', 'max_length': 8}` |
| `9(n)` | `int` | `{'pic': '9(05)', 'max_digits': 5}` |
| `S9(n)` | `int` | `{'pic': 'S9(07)', 'max_digits': 7, 'signed': True}` |
| `9(n)V9(m)` | `Decimal` | `{'pic': '9(05)V99', 'max_digits': 5, 'scale': 2}` |
| `S9(n)V9(m)` | `Decimal` | `{'pic': 'S9(07)V99', 'max_digits': 7, 'scale': 2, 'signed': True}` |
| any + `COMP` | (as above) | adds `'usage': 'COMP'` |
| any + `COMP-3` | (as above) | adds `'usage': 'COMP-3'` |

**Reasoning**: Comments are not enforceable. `field(metadata={...})` is introspectable
at runtime via `dataclasses.fields()`, enabling IQ-03 (CobolDecimal) to read the
constraints and enforce them, IQ-05 to generate boundary test values, and IQ-09
to compare field-level precision. This gives the same type safety that COBOL
enforces at the data definition level.

**Intended outcome**: A reimplementer or downstream tool can do:
```python
from dataclasses import fields
for f in fields(SecUserData):
    meta = f.metadata
    if 'max_length' in meta:
        assert len(getattr(record, f.name)) <= meta['max_length']
```

---

## Implementation Plan

### Changes to `skeleton_generator.py`

1. Add `_generate_dataclass_for_copybook(copybook_name, copybook_dict=None)` —
   when `copybook_dict` is provided, look up the `CopybookRecord` and generate
   typed fields instead of `pass`.

2. Add helper `_generate_fields_for_record(fields, level_filter)` — recursive
   function that walks the field list, tracks level hierarchy, and emits:
   - Elementary fields (has PIC) as typed dataclass fields with metadata
   - Group fields (no PIC, has children) as nested dataclass references
   - REDEFINES as Optional fields
   - OCCURS as list fields
   - Level-88 as ClassVar constants
   - FILLER as skipped

3. Add helper `_pic_to_field_metadata(pic, usage)` — returns the metadata dict
   for a given PIC/USAGE combination.

4. Modify `generate_skeleton()` to accept optional `copybook_dict` and pass it
   through to `_generate_dataclass_for_copybook()`.

5. Modify `generate_all_skeletons()` to instantiate `CopybookDictionary` from
   `codebase_dir` and pass it to `generate_skeleton()`.

### Changes to `copybook_dict.py`

None anticipated. The existing `CopybookRecord` and `CopybookField` have all
needed attributes (level, picture, usage, occurs, redefines, condition_values).

---

## Test Strategy

Tests use real `.cpy` files from `test-codebases/carddemo/app/cpy/` and synthetic
copybooks via `tmp_path`. Each test:
1. Parses a copybook or builds a ProgramSpec with a known copybook
2. Generates the skeleton
3. Asserts specific field names, types, metadata, and structure

Primary test copybooks:
- `CSUSR01Y.cpy` — flat structure, all PIC X fields (simple case)
- `COCOM01Y.cpy` — nested groups (05 → 10), level-88 conditions
- `CVACT01Y.cpy` — mixed PIC X and PIC S9(n)V99 (decimal fields)
- Synthetic copybooks for OCCURS, REDEFINES edge cases

Test file: `pipeline/tests/test_skeleton_generator.py` (extend existing)
