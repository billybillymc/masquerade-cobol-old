# IQ-10: Symbol Table and Scope Resolution — Design Specification

**Status**: In Progress
**Created**: 2026-03-15

---

## Problem Statement

The parser treats all field names as flat strings. COBOL has hierarchical scope
(`ERRMSGO OF COSGN0AO` qualifies which `ERRMSGO`), and `REDEFINES` creates type
unions over the same memory. Without a symbol table, data flow analysis produces
false edges when two copybooks define fields with the same name.

### Evidence

`TRNNAMEI` appears in 21 copybooks (all BMS-generated). An unqualified reference
in data flow analysis could match any of 21 sources. `ERRMSGO OF COSGN0AO` in
COSGN00C.cbl line 78 needs hierarchical resolution.

---

## Design Decisions

### DD-01: Hierarchical tree from copybook fields + program data items
SymbolNode tree built from COBOL level numbers. Each node has: name, level,
parent, children, picture, usage, section, copybook_origin.

### DD-02: Qualified name resolution (field OF group OF record)
`resolve("ERRMSGO", qualifier="COSGN0AO")` → unique node.
`resolve("ERRMSGO")` without qualifier → ambiguous if multiple exist.

### DD-03: REDEFINES tracked as shared memory offset
REDEFINES nodes point to the same offset as their target. The symbol table
records this as `redefines_target` on the node.

### DD-04: Scope tags — WORKING-STORAGE, LINKAGE, FILE SECTION
Each symbol node carries a `section` tag. LINKAGE fields are flagged as
external interface (parameters from calling programs).

---

## New module: `pipeline/symbol_table.py`
## Test file: `pipeline/tests/test_symbol_table.py`
