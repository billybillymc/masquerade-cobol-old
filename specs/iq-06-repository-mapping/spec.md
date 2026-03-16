# IQ-06: File I/O → Repository Pattern Mapping — Design Specification

**Status**: In Progress
**Created**: 2026-03-15
**Prerequisites**: IQ-02 (typed copybook fields for record types)

---

## Problem Statement

Every file operation becomes `# TODO: Replace with database operation`. The parser
captures `FileControl` (SELECT/ASSIGN) and CICS file ops (READ/WRITE/DELETE with
DATASET). This is enough to generate typed repository interfaces.

### Evidence

COSGN00C does `EXEC CICS READ DATASET(WS-USRSEC-FILE) INTO(SEC-USER-DATA)
RIDFLD(WS-USER-ID)`. This should produce
`UserSecurityRepository.find_by_id(user_id: str) -> SecUserData`.

Source: `COSGN00C.cbl` lines 211–219.

---

## Design Decisions

### DD-01: One repository per dataset, methods from operations

| CICS Op | Method | Signature |
|---------|--------|-----------|
| READ + RIDFLD | `find_by_id` | `(key: KeyType) -> RecordType` |
| WRITE | `save` | `(record: RecordType) -> None` |
| REWRITE | `update` | `(record: RecordType) -> None` |
| DELETE | `delete` | `(key: KeyType) -> None` |
| STARTBR+READNEXT+ENDBR | `browse` | `(start_key) -> Iterator[RecordType]` |

### DD-02: Sequential files → context manager readers/writers

### DD-03: Extract RIDFLD/INTO by scanning paragraph source lines

### DD-04: Repository classes replace TODO comments in skeletons

### DD-05: INTO target resolved to copybook record type via 01-level name match

---

## New module: `pipeline/repository_mapper.py`
## Test file: `pipeline/tests/test_repository_mapper.py`
