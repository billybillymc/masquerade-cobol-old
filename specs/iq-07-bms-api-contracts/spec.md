# IQ-07: BMS Screen → API Contract Generation — Design Specification

**Status**: In Progress
**Created**: 2026-03-15

---

## Problem Statement

CICS SEND MAP / RECEIVE MAP define clear request/response contracts, but skeleton
generation replaces them with `# TODO: Replace with API endpoint handler`.
`bms_parser.py` already parses BMS maps into fields with attributes.

### Evidence

COSGN00C sends/receives COSGN0A. BMS parser extracts USERID (input, UNPROT),
PASSWD (input, UNPROT, DRK), ERRMSG (output, ASKIP, BRT), etc.

---

## Design Decisions

### DD-01: RECEIVE MAP fields → request schema (Pydantic model)
Input fields (UNPROT) become request model fields.
Attribute DRK → `write_only=True` (password-like).

### DD-02: SEND MAP fields → response schema (Pydantic model)
Output fields (ASKIP/PROT) become response model fields.
BRT → flagged for display emphasis.

### DD-03: Route stub with typed request/response
CICS programs get a FastAPI route stub with the Pydantic models.

### DD-04: Field attributes → validation annotations
UNPROT+IC → required (initial cursor = primary input).
Length → `max_length` constraint.

---

## New module: `pipeline/api_contract_mapper.py`
## Test file: `pipeline/tests/test_api_contract_mapper.py`
