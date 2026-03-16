# Feature Specification: Dependency Graph + System Model

**Feature Branch**: `002-dependency-graph`  
**Created**: 2026-03-13  
**Status**: Draft  
**Input**: Build a dependency graph and system model on top of the COBOL parser output (feature 001)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extract Program-Call Graph (Priority: P1)

A modernization architect ingests a codebase that has been parsed by the COBOL parser. The system extracts a program-call graph from CALL statements and PERFORM chains, producing edges between programs and between paragraphs/sections within programs. The architect can see which programs call which, and which paragraphs perform which, with evidence anchored to source spans.

**Why this priority**: The call graph is the backbone of impact analysis and system understanding. Without it, users cannot answer "what breaks if we change X?" or "where does this flow go?" This is the primary deliverable for Week 2.

**Independent Test**: Can be fully tested by running graph extraction on the CardDemo codebase and verifying that every CALL and PERFORM statement produces a corresponding edge with source/target node IDs and evidence references.

**Acceptance Scenarios**:

1. **Given** parsed COBOL programs from CardDemo, **When** graph extraction runs, **Then** every CALL statement produces a CALLS edge from the calling program to the callee program with evidence (file, line, statement span).
2. **Given** parsed COBOL programs with PERFORM paragraph-name and PERFORM section-name, **When** graph extraction runs, **Then** every PERFORM produces a PERFORMS edge from the performing paragraph/section to the target paragraph/section with evidence.
3. **Given** a CALL to a program not present in the parsed corpus, **When** graph extraction runs, **Then** an "unknown" or unresolved edge is produced and surfaced as a first-class output (not hidden or dropped).
4. **Given** a PERFORM to a paragraph/section that cannot be statically resolved (e.g., variable paragraph name), **When** graph extraction runs, **Then** an unknown edge is produced and surfaced with an uncertainty label.

---

### User Story 2 - Extract Copybook and Data Dependency Links (Priority: P1)

A senior COBOL engineer needs to understand which programs use which copybooks and which fields are read or written. The system extracts USES_COPYBOOK edges from COPY statements (already present in parser output) and READS_FIELD / WRITES_FIELD edges from data movement and I/O statements. The engineer can trace which programs touch which shared data structures.

**Why this priority**: Copybook and field dependencies drive blast-radius analysis and lineage. Without them, "if this field changes, what breaks?" cannot be answered. Co-equal with the call graph for system modeling.

**Independent Test**: Can be fully tested by running graph extraction on CardDemo programs that reference copybooks and perform READ/WRITE/MOVE operations, and verifying edges link programs to copybooks and programs/paragraphs to fields.

**Acceptance Scenarios**:

1. **Given** parsed programs with COPY statements, **When** graph extraction runs, **Then** every COPY produces a USES_COPYBOOK edge from the program to the copybook with evidence.
2. **Given** parsed programs with FD/SD file definitions and READ/WRITE statements, **When** graph extraction runs, **Then** READS_FIELD or WRITES_FIELD edges are produced linking the program (or paragraph) to the file/record fields touched.
3. **Given** parsed programs with MOVE statements involving copybook fields, **When** graph extraction runs, **Then** data dependency edges are produced where source and target fields can be resolved to symbol table entries.
4. **Given** a copybook referenced by COPY but not found in the include path, **When** graph extraction runs, **Then** a USES_COPYBOOK edge is still produced (best-effort policy) and the copybook node is marked as unresolved; the edge is surfaced, not hidden.

---

### User Story 3 - Cross-Program Dependency Mapping (Priority: P2)

A modernization architect needs a unified view of how programs relate to each other and to shared artifacts (copybooks, files, tables). The system produces a cross-program dependency map that aggregates CALLS, USES_COPYBOOK, and file/table touches into a single queryable model. The architect can ask "which programs depend on copybook X?" or "which programs does program Y call or call into?"

**Why this priority**: Cross-program mapping enables system-level impact analysis and migration wave planning. It builds on Stories 1 and 2 but adds the aggregation and queryability needed for exploration.

**Independent Test**: Can be fully tested by running graph extraction on the full CardDemo codebase and verifying that the output supports queries such as "all programs that use copybook CARD-RECORD" and "all programs reachable from MAIN-PGM via CALLS".

**Acceptance Scenarios**:

1. **Given** a graph extracted from CardDemo, **When** querying "programs that use copybook X", **Then** all programs with USES_COPYBOOK edges to X are returned.
2. **Given** a graph extracted from CardDemo, **When** querying "programs called by program P", **Then** all programs with incoming CALLS edges from P are returned.
3. **Given** a graph extracted from CardDemo, **When** querying "programs that read or write file F", **Then** all programs with READS_FIELD or WRITES_FIELD edges involving F are returned.
4. **Given** a graph with unresolved edges, **When** querying the dependency map, **Then** unresolved edges are included in results with an explicit "unknown" or "unresolved" flag so users can see what is uncertain.

---

### User Story 4 - Surface Unknown Edges as First-Class Outputs (Priority: P2)

A risk/controls stakeholder reviewing the dependency graph needs to see what the system could not resolve with confidence. The system surfaces all unknown or unresolved edges (dynamic calls, missing copybooks, unresolved PERFORM targets) as first-class outputs with explicit labels. These are not hidden, suppressed, or treated as errors.

**Why this priority**: Per PRD locked decisions, "unknown edges are first-class outputs, not errors to hide." Trust requires transparency about uncertainty. This is a core requirement for enterprise adoption.

**Independent Test**: Can be fully tested by running graph extraction on a codebase with deliberate unknowns (missing copybook, CALL with variable, PERFORM THRU with variable range) and verifying each produces a surfaced unknown edge with an uncertainty label.

**Acceptance Scenarios**:

1. **Given** a CALL to a program not in the parsed corpus, **When** graph extraction runs, **Then** the output includes an edge (or placeholder) with type indicating "unresolved" and the target identifier preserved for manual review.
2. **Given** a COPY referencing a copybook not found, **When** graph extraction runs, **Then** the USES_COPYBOOK edge is produced with the copybook node marked unresolved; the edge is included in the graph output, not dropped.
3. **Given** any unknown edge, **When** the graph is exported or queried, **Then** the edge carries an explicit flag or metadata indicating it is unresolved/uncertain.
4. **Given** a mix of resolved and unresolved edges, **When** a summary or report is generated, **Then** the count and list of unresolved edges are included.

---

### User Story 5 - Produce Graph Overlay Compatible with Canonical IR (Priority: P2)

A pipeline integrator needs the graph output to conform to the canonical IR (Strategy A: typed AST + graph overlay). The system produces a graph overlay with stable node IDs that reference parser-produced entities (programs, paragraphs, sections, copybooks, fields). Every graph node and edge maps back to source spans or parser node IDs.

**Why this priority**: The graph must integrate with downstream features (semantic pipeline, lineage, impact analysis). Strategy A requires the graph as an overlay on the typed AST, not a separate disconnected model.

**Independent Test**: Can be fully tested by verifying that graph node IDs align with parser program/paragraph/section IDs and that every edge includes evidence references (source span or node ID).

**Acceptance Scenarios**:

1. **Given** graph extraction output, **When** inspecting any node, **Then** the node has a stable ID that can be correlated with parser output (e.g., program ID, paragraph ID).
2. **Given** graph extraction output, **When** inspecting any edge, **Then** the edge includes evidence (source file, line, span or statement node ID).
3. **Given** parser output with partial parse (some statements unparsed), **When** graph extraction runs, **Then** a partial graph is produced for the successfully parsed portions (best-effort policy); no graph is not acceptable when any parse succeeded.
4. **Given** graph extraction output, **When** consumed by a downstream component, **Then** the output format is structured and machine-readable (e.g., JSON) with a defined schema for nodes and edges.

---

### User Story 6 - Optional JCL/File/Table Entity Extraction (Priority: P3)

A modernization architect analyzing a batch-oriented system needs to see how programs connect to files, DB2 tables, and JCL jobs. The system optionally extracts File and Table entities from FD/SD/DB2 definitions and FEEDS/SCHEDULED_BY relationships from JCL when JCL extraction is available. This is additive and can be partial.

**Why this priority**: File and table dependencies complete the system model for batch flows. Lower priority because JCL parsing may be partial in MVP and many programs can be analyzed without it.

**Independent Test**: Can be fully tested by running graph extraction on CardDemo (or taxe-fonciere) programs with FD definitions and verifying File nodes and READS_FIELD/WRITES_FIELD edges are produced; JCL extraction is optional and may produce empty results.

**Acceptance Scenarios**:

1. **Given** parsed programs with FD (file description) entries, **When** graph extraction runs, **Then** File nodes are created and linked via READS_FIELD/WRITES_FIELD where READ/WRITE statements are present.
2. **Given** parsed programs with EXEC SQL referencing DB2 tables, **When** graph extraction runs, **Then** Table nodes are created (or stubbed) and linked to programs where SQL access is detected.
3. **Given** JCL job/step definitions (if available from optional JCL extraction), **When** graph extraction runs, **Then** FEEDS and SCHEDULED_BY edges may be produced linking programs to jobs/steps; absence of JCL MUST NOT cause graph extraction to fail.

---

### Edge Cases

- **What happens when a program fails to parse entirely?** The system MUST exclude that program from the graph but continue building the graph for all successfully parsed programs. The failed program MAY appear as a target of CALLS edges from other programs, marked as unresolved.
- **What happens when PERFORM THRU is used with a range of paragraphs?** The system MUST produce PERFORMS edges from the performing location to each paragraph in the range, with evidence. If the range cannot be statically determined, an unknown edge MUST be produced and surfaced.
- **What happens when a CALL uses a variable (dynamic call)?** The system MUST produce an unknown/unresolved CALLS edge with the variable name or pattern preserved; the edge is first-class output, not hidden.
- **What happens when copybooks are mutually recursive (A copies B, B copies A)?** The parser (feature 001) handles this; graph extraction MUST not introduce new failure modes. If the parser produced partial resolution, the graph reflects what was resolved.
- **What happens when the same paragraph name exists in multiple programs?** PERFORMS edges MUST be scoped to the program (intra-program only for PERFORM paragraph-name unless cross-program PERFORM is supported by the dialect). The graph MUST disambiguate by program context.
- **What happens when FD/SD references a copybook for record layout?** The system MUST link the File node to the copybook (or record layout) and produce READS_FIELD/WRITES_FIELD edges that reference the correct record structure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST extract a program-call graph from CALL statements, producing CALLS edges with evidence (source span, file, line).
- **FR-002**: System MUST extract PERFORM chains, producing PERFORMS edges from performing paragraph/section to target paragraph/section with evidence.
- **FR-003**: System MUST extract USES_COPYBOOK edges from COPY statements, linking programs to copybooks.
- **FR-004**: System MUST extract READS_FIELD and WRITES_FIELD edges from file I/O (READ, WRITE) and data movement (MOVE) where source and target can be resolved to symbol table entries.
- **FR-005**: System MUST surface all unknown or unresolved edges as first-class outputs with explicit uncertainty labels; unknown edges MUST NOT be hidden or dropped.
- **FR-006**: System MUST support cross-program dependency queries (programs using copybook X, programs called by P, programs touching file F).
- **FR-007**: System MUST produce a graph overlay compatible with canonical IR Strategy A (typed AST + graph overlay) with stable node IDs and evidence references.
- **FR-008**: System MUST operate in best-effort mode: partial graph when parsing is incomplete; graph extraction MUST NOT fail entirely when some programs fail to parse.
- **FR-009**: System MUST produce structured, machine-readable output (e.g., JSON) with a defined schema for nodes and edges.
- **FR-010**: System MUST optionally extract File and Table entities from FD/SD and EXEC SQL when present; absence of these MUST NOT cause extraction to fail.
- **FR-011**: System MUST optionally support FEEDS and SCHEDULED_BY edges from JCL when JCL extraction is available; absence of JCL MUST NOT cause extraction to fail.
- **FR-012**: System MUST include evidence (source file, line, span or node ID) for every edge to support downstream citation and verification.

### Key Entities

- **Program**: A COBOL compilation unit. Key attributes: name, source file path, parser node ID. Source: parser output.
- **Paragraph**: A named procedural unit in the PROCEDURE DIVISION. Key attributes: name, parent program, source span, parser node ID.
- **Section**: A named section in the PROCEDURE DIVISION. Key attributes: name, parent program, source span, parser node ID.
- **Copybook**: A shared source fragment included via COPY. Key attributes: name, file path (if resolved), parser node ID.
- **Field**: A data item from the symbol table. Key attributes: qualified name, level, PIC, USAGE, parent copybook or program.
- **File**: A file defined by FD or SD. Key attributes: name, record layout reference, access mode.
- **Table**: A DB2 table referenced in EXEC SQL. Key attributes: name, access type (read/write).
- **JCL Job/Step**: (Optional) A batch job or step from JCL. Key attributes: job name, step name.
- **Edge**: A directed relationship between nodes. Key attributes: source node ID, target node ID, edge type, evidence list, unresolved flag.
- **UnknownEdge**: A first-class representation of an unresolved relationship. Key attributes: edge type, source, target identifier (as known), reason (missing program, missing copybook, dynamic call, etc.).

### Key Relationships (Edge Types)

- **CALLS**: Program A calls program B (or paragraph in B).
- **PERFORMS**: Paragraph/section A performs paragraph/section B (intra- or inter-program as supported).
- **USES_COPYBOOK**: Program uses copybook.
- **READS_FIELD**: Program/paragraph reads a field (file record, copybook field).
- **WRITES_FIELD**: Program/paragraph writes a field.
- **FEEDS**: (Optional) Program feeds into a JCL step or data set.
- **SCHEDULED_BY**: (Optional) Program is scheduled by a JCL job/step.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Graph extraction completes for >= 90% of successfully parsed programs in the CardDemo codebase (28 files, 19K LOC).
- **SC-002**: Graph extraction completes for >= 90% of successfully parsed programs in the taxe-fonciere codebase (6 files, 2.3K LOC) as cross-validation.
- **SC-003**: All unknown/unresolved edges are surfaced in the output; zero unknown edges are hidden or dropped.
- **SC-004**: Every CALL and PERFORM statement in CardDemo produces a corresponding edge (resolved or unknown) with evidence.
- **SC-005**: Every COPY statement in CardDemo produces a USES_COPYBOOK edge with evidence.
- **SC-006**: Graph output is consumable by downstream components (structured format, stable IDs, evidence references).
- **SC-007**: Cross-program dependency queries (programs using copybook X, programs called by P) return correct results for CardDemo.
- **SC-008**: When a program fails to parse, the graph for remaining programs is still produced; extraction does not abort.
