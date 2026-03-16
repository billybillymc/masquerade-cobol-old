# Feature Specification: COBOL Parser + Copybook Resolution

**Feature Branch**: `001-cobol-parser`  
**Created**: 2026-03-13  
**Status**: Draft  
**Input**: User description: "COBOL parser integration with copybook resolution for IBM Enterprise COBOL"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Parse a COBOL Program and Produce an AST (Priority: P1)

A modernization architect uploads or points the system at a directory of IBM Enterprise COBOL source files. The system parses each file and produces a typed AST with stable node IDs, preserving lossless links back to original source line/column spans. The architect can see which files parsed successfully, which had recoverable issues, and which failed outright.

**Why this priority**: Without a working parser that produces a navigable AST, no downstream analysis (graph, explanation, lineage, or modernization) is possible. This is the foundation of the entire platform.

**Independent Test**: Can be fully tested by pointing the parser at the CardDemo test codebase (28 files, 19K LOC) and verifying that all `.cbl` files produce a typed AST with program, section, paragraph, and data-division nodes.

**Acceptance Scenarios**:

1. **Given** a valid IBM Enterprise COBOL source file from CardDemo, **When** the parser processes it, **Then** a typed AST is produced with stable node IDs and every node maps back to a source span (file, start line/col, end line/col).
2. **Given** a COBOL source file with a recoverable syntax issue (e.g., non-standard comment), **When** the parser processes it, **Then** a partial AST is produced with an error annotation at the unrecognized location and overall parse coverage is reported.
3. **Given** a COBOL source file with a blocking parse failure (e.g., completely unsupported dialect extension), **When** the parser processes it, **Then** the file is marked as failed with error class, source location, and suggested remediation, without halting processing of remaining files.

---

### User Story 2 - Resolve Copybooks During Parsing (Priority: P1)

A senior COBOL engineer points the system at a codebase that uses COPY statements to include shared data definitions. The system resolves copybook references using configured include paths, expands them inline, and produces a complete AST with data division fields fully resolved — including REDEFINES and OCCURS clauses from copybooks.

**Why this priority**: Copybooks define shared data structures used across programs. Without resolving them, the data division is incomplete and field-level analysis is impossible. This is co-equal with basic parsing.

**Independent Test**: Can be fully tested by parsing CardDemo COBOL files that reference copybooks in the `cpy` directory and verifying that COPY statements are expanded, fields from copybooks appear in the AST, and source spans correctly reference the originating copybook file.

**Acceptance Scenarios**:

1. **Given** a COBOL program with `COPY` statements referencing copybooks in a configured include path, **When** the parser processes it, **Then** the AST contains all fields from the expanded copybook with source spans pointing to the copybook file.
2. **Given** a COBOL program with a `COPY ... REPLACING` statement, **When** the parser processes it, **Then** the AST reflects the replaced identifiers while preserving a link to the original copybook source.
3. **Given** a COBOL program referencing a copybook that cannot be found in any configured include path, **When** the parser processes it, **Then** the system reports a recoverable error with the missing copybook name and continues parsing the rest of the program.

---

### User Story 3 - Extract Symbol Table and Data Division Model (Priority: P2)

An application support analyst needs to understand the data layout of a COBOL program. The system extracts a symbol table from the parsed AST that catalogs all data items with their level numbers, PIC clauses, USAGE declarations (COMP, COMP-3, DISPLAY, etc.), and hierarchical group/elementary relationships.

**Why this priority**: The symbol table is the foundation for field-level lineage, impact analysis, and numeric semantics validation in later features. It must be correct and complete for the parser to be useful.

**Independent Test**: Can be fully tested by parsing a CardDemo program with complex data definitions and verifying the symbol table includes every data item with correct level, PIC, USAGE, REDEFINES, and OCCURS attributes.

**Acceptance Scenarios**:

1. **Given** a parsed COBOL program with WORKING-STORAGE and LINKAGE SECTION definitions, **When** the symbol table is extracted, **Then** every data item appears with level number, PIC clause, USAGE, and group hierarchy.
2. **Given** a data definition with REDEFINES, **When** the symbol table is extracted, **Then** the redefined and redefining entries are linked and both are queryable.
3. **Given** a data definition with OCCURS DEPENDING ON, **When** the symbol table is extracted, **Then** the variable-length array is represented with its controlling field reference.

---

### User Story 4 - Report Parse Coverage Metrics (Priority: P2)

A modernization architect wants to know how much of a codebase the parser can handle before committing to deeper analysis. The system produces a parse coverage report that shows per-file and aggregate metrics: percentage of statements successfully parsed, count of recoverable vs. blocking errors, and a list of unsupported constructs encountered.

**Why this priority**: Parse coverage is a gating KPI for all downstream features and for the "migration-ready" readiness score. Without it, users cannot assess whether the parser is trustworthy enough for their codebase.

**Independent Test**: Can be fully tested by running the parser against both CardDemo (expected high coverage) and a deliberately messy synthetic file (expected lower coverage) and verifying the coverage report distinguishes them accurately.

**Acceptance Scenarios**:

1. **Given** a codebase of N files processed by the parser, **When** the coverage report is generated, **Then** it shows per-file parse success percentage, total statements parsed vs. total statements, and aggregate coverage.
2. **Given** files with mixed parse results, **When** the coverage report is generated, **Then** each error is classified (recoverable/unsupported/blocking) with machine-readable error codes and source locations.
3. **Given** the parser processes the full CardDemo codebase, **When** the coverage report is generated, **Then** aggregate parse coverage is >= 90%.

---

### User Story 5 - Extract Embedded SQL Statements (Priority: P3)

A senior COBOL engineer examining a program that accesses DB2 needs the system to recognize `EXEC SQL ... END-EXEC` blocks, preserve the SQL text, and link host variables back to COBOL data items in the symbol table.

**Why this priority**: DB2 access is common in enterprise COBOL. Extracting SQL enables later features (dependency graph, lineage) to trace data through database interactions. Lower priority than core parsing and copybooks because it is additive.

**Independent Test**: Can be fully tested by parsing CardDemo files containing EXEC SQL blocks and verifying SQL text is captured and host variable references resolve to symbol table entries.

**Acceptance Scenarios**:

1. **Given** a COBOL program with `EXEC SQL SELECT ... INTO :HOST-VAR ... END-EXEC`, **When** parsed, **Then** the AST contains an SQL node with the query text and the host variable `:HOST-VAR` is linked to the corresponding symbol table entry.
2. **Given** a COBOL program with `EXEC SQL INCLUDE` for a SQL copybook, **When** parsed, **Then** the included SQL definitions are resolved similarly to COBOL COPY statements.

---

### Edge Cases

- What happens when a copybook recursively includes another copybook? The system MUST detect and handle transitive COPY resolution up to a configurable depth limit, and report circular references as errors.
- How does the system handle COBOL programs with mixed CICS and batch constructs? CICS `EXEC CICS ... END-EXEC` blocks MUST be recognized and preserved as opaque nodes in the AST (detailed CICS parsing is out of scope for this feature).
- What happens when a file uses compiler directives (CBL, PROCESS) or dialect-specific extensions? The parser MUST skip unrecognized directives with a recoverable warning rather than aborting.
- How does the system handle fixed-format vs. free-format source? MVP targets fixed-format (columns 7-72) only; free-format files MUST be reported as unsupported.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST parse IBM Enterprise COBOL source files and produce a typed AST with stable, deterministic node IDs.
- **FR-002**: System MUST preserve lossless source span mappings (file, start line/col, end line/col) for every AST node.
- **FR-003**: System MUST resolve COPY statements using configurable include paths, including transitive copybook resolution.
- **FR-004**: System MUST handle COPY ... REPLACING by applying text replacements and preserving links to original copybook source.
- **FR-005**: System MUST extract a symbol table from the DATA DIVISION with level numbers, PIC clauses, USAGE, REDEFINES, and OCCURS attributes.
- **FR-006**: System MUST classify parse errors into recoverable, unsupported-construct, and blocking categories with machine-readable error codes.
- **FR-007**: System MUST continue processing remaining files in a batch when one file encounters a blocking failure (best-effort policy).
- **FR-008**: System MUST produce a parse coverage report with per-file and aggregate metrics.
- **FR-009**: System MUST recognize EXEC SQL ... END-EXEC blocks and link host variables to symbol table entries.
- **FR-010**: System MUST recognize EXEC CICS ... END-EXEC blocks as opaque AST nodes without deep parsing.
- **FR-011**: System MUST target fixed-format COBOL (columns 7-72) and report free-format source as unsupported.
- **FR-012**: System MUST expose parse results as structured JSON for downstream consumption by graph, analysis, and LLM pipelines.

### Key Entities

- **Program**: A single COBOL compilation unit. Key attributes: name, source file path, identification division metadata.
- **Copybook**: A shared source fragment included via COPY. Key attributes: name, file path, dependent programs.
- **Section**: A named section within a COBOL division (e.g., WORKING-STORAGE SECTION). Key attributes: name, parent division.
- **Paragraph**: A named procedural unit in the PROCEDURE DIVISION. Key attributes: name, parent section, source span.
- **Field (Data Item)**: A data definition in the DATA DIVISION. Key attributes: level number, PIC clause, USAGE, REDEFINES target, OCCURS count, group parent.
- **ParseError**: An error encountered during parsing. Key attributes: error class, error code, source location, message, remediation hint.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Parser achieves >= 90% statement-level parse coverage on the CardDemo codebase (28 files, 19K LOC).
- **SC-002**: Parser achieves >= 95% parse coverage on migration-candidate modules within CardDemo.
- **SC-003**: All copybook references in CardDemo are resolved without manual intervention when include paths are configured correctly.
- **SC-004**: Symbol table extraction captures 100% of data items (elementary and group) from successfully parsed programs.
- **SC-005**: Parse coverage report is generated within 30 seconds for the full CardDemo codebase.
- **SC-006**: Every AST node is traceable back to its source span with exact line/column accuracy.
- **SC-007**: Parser processes the taxe-fonciere codebase (6 files, 2.3K LOC) with >= 85% coverage as a cross-validation check.
