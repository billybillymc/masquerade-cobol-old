# Tasks: Dependency Graph + System Model

**Input**: Design documents from `/specs/002-dependency-graph/`  
**Prerequisites**: plan.md (required), spec.md (required), feature 001 parser output available

**Tests**: TDD enforced. Write failing tests first, then implementation.

**Organization**: Tasks grouped by user story. Tests before implementation within each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[USn]**: User story label (US1–US6)
- Paths: `services/analysis-orchestrator/`, `packages/schemas/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and graph module structure

- [ ] **T001** Create `services/analysis-orchestrator/app/graph/` module with `__init__.py`, `builder.py`, `store.py`
- [ ] **T002** Add graph dependencies to `services/analysis-orchestrator/pyproject.toml` (Neo4j driver or graph library)
- [ ] **T003** [P] Add `packages/schemas/graph-node.schema.json` and `packages/schemas/graph-edge.schema.json` stubs

---

## Phase 2: Foundation (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] **T004** Define `graph-node.schema.json` with node types: Program, Paragraph, Section, Copybook, Field, File, Table; required: id, type, evidence_ref
- [ ] **T005** Define `graph-edge.schema.json` with edge types: CALLS, PERFORMS, USES_COPYBOOK, READS_FIELD, WRITES_FIELD, FEEDS, SCHEDULED_BY; required: source_id, target_id, edge_type, evidence, unresolved
- [ ] **T006** Implement parser output adapter: load parser JSON, map to internal node/span structures in `app/graph/parser_adapter.py`
- [ ] **T007** Implement `GraphBuilder` skeleton in `app/graph/builder.py`: accepts parser output, returns graph JSON; empty graph initially
- [ ] **T008** Add schema validation for graph output in `app/graph/validation.py`
- [ ] **T009** [P] Add CardDemo parser output fixture (or mock) for integration tests in `tests/fixtures/`

**Checkpoint**: Foundation ready — user story implementation can begin

---

## Phase 3: User Story 1 — Extract Program-Call Graph (Priority: P1) 🎯 MVP

**Goal**: Every CALL produces CALLS edge; every PERFORM produces PERFORMS edge; unknown targets surfaced.

**Independent Test**: Run graph extraction on CardDemo; verify every CALL/PERFORM produces edge with evidence.

### Tests for User Story 1

- [ ] **T010** [P] [US1] Unit test: CALL statement produces CALLS edge with evidence (file, line, span) in `tests/unit/test_graph_calls.py`
- [ ] **T011** [P] [US1] Unit test: PERFORM paragraph-name produces PERFORMS edge in `tests/unit/test_graph_performs.py`
- [ ] **T012** [P] [US1] Unit test: CALL to missing program produces unresolved edge with target identifier in `tests/unit/test_graph_unknown_edges.py`
- [ ] **T013** [US1] Integration test: CardDemo extraction — every CALL and PERFORM produces corresponding edge in `tests/integration/test_graph_extraction_carddemo.py`

### Implementation for User Story 1

- [ ] **T014** [US1] Implement `CallsExtractor` in `app/graph/extractors/calls.py`: traverse AST for CALL, emit CALLS edges with evidence
- [ ] **T015** [US1] Implement `PerformsExtractor` in `app/graph/extractors/performs.py`: traverse AST for PERFORM, emit PERFORMS edges; handle PERFORM THRU range
- [ ] **T016** [US1] Wire CALLS and PERFORMS extractors into `GraphBuilder` pipeline
- [ ] **T017** [US1] Add unresolved edge handling: CALL to unknown program, PERFORM to variable target → emit unknown edge with `unresolved: true`, `reason`, `target_identifier`

**Checkpoint**: US1 complete — program-call graph extractable from CardDemo

---

## Phase 4: User Story 2 — Extract Copybook and Data Dependency Links (Priority: P1)

**Goal**: USES_COPYBOOK from COPY; READS_FIELD/WRITES_FIELD from READ/WRITE/MOVE.

**Independent Test**: CardDemo programs with COPY and READ/WRITE produce correct edges.

### Tests for User Story 2

- [ ] **T018** [P] [US2] Unit test: COPY statement produces USES_COPYBOOK edge in `tests/unit/test_graph_copybook.py`
- [ ] **T019** [P] [US2] Unit test: READ/WRITE produce READS_FIELD/WRITES_FIELD edges in `tests/unit/test_graph_io.py`
- [ ] **T020** [P] [US2] Unit test: MOVE with resolvable fields produces data dependency edges in `tests/unit/test_graph_move.py`
- [ ] **T021** [US2] Unit test: COPY to missing copybook produces USES_COPYBOOK edge with unresolved copybook node in `tests/unit/test_graph_unknown_edges.py`

### Implementation for User Story 2

- [ ] **T022** [US2] Implement `CopybookExtractor` in `app/graph/extractors/copybook.py`: from COPY nodes, emit USES_COPYBOOK edges
- [ ] **T023** [US2] Implement `DataDependencyExtractor` in `app/graph/extractors/data_deps.py`: READ/WRITE → READS_FIELD/WRITES_FIELD; MOVE where source/target resolve to symbol table
- [ ] **T024** [US2] Wire extractors into `GraphBuilder`; handle missing copybook → unresolved node, edge still emitted
- [ ] **T025** [US2] Add FD/SD file definitions → File nodes; link READS_FIELD/WRITES_FIELD to file record fields

**Checkpoint**: US2 complete — copybook and data dependency edges extractable

---

## Phase 5: User Story 3 — Cross-Program Dependency Mapping (Priority: P2)

**Goal**: Queries: programs using copybook X, programs called by P, programs touching file F.

**Independent Test**: Graph from CardDemo supports these queries correctly.

### Tests for User Story 3

- [ ] **T026** [P] [US3] Unit test: query "programs using copybook X" returns correct programs in `tests/unit/test_graph_queries.py`
- [ ] **T027** [P] [US3] Unit test: query "programs called by P" returns correct callees in `tests/unit/test_graph_queries.py`
- [ ] **T028** [US3] Integration test: CardDemo graph supports all three query types in `tests/integration/test_graph_queries_carddemo.py`

### Implementation for User Story 3

- [ ] **T029** [US3] Implement query API in `app/graph/queries.py`: `programs_using_copybook`, `programs_called_by`, `programs_touching_file`
- [ ] **T030** [US3] Integrate query API with graph store (in-memory or Neo4j); ensure unresolved edges included in results with `unresolved` flag
- [ ] **T031** [US3] Add query endpoint or function to `GraphBuilder` / orchestrator for programmatic access

**Checkpoint**: US3 complete — cross-program dependency queries work

---

## Phase 6: User Story 4 — Surface Unknown Edges as First-Class Outputs (Priority: P2)

**Goal**: All unknown edges surfaced with explicit labels; never hidden or dropped.

**Independent Test**: Codebase with deliberate unknowns produces surfaced unknown edges.

### Tests for User Story 4

- [ ] **T032** [P] [US4] Unit test: unresolved CALL produces edge with `unresolved: true`, `reason`, `target_identifier` in `tests/unit/test_graph_unknown_edges.py`
- [ ] **T033** [P] [US4] Unit test: unresolved COPY produces USES_COPYBOOK with unresolved copybook node in `tests/unit/test_graph_unknown_edges.py`
- [ ] **T034** [US4] Unit test: graph export includes `unresolved_edges` count and list in `tests/unit/test_graph_export.py`

### Implementation for User Story 4

- [ ] **T035** [US4] Ensure all extractors emit unknown edges with `unresolved`, `reason`, `target_identifier`; never drop
- [ ] **T036** [US4] Add `unresolved_edges` to graph output schema and summary; include in export/report
- [ ] **T037** [US4] Add metadata to each edge: `unresolved` flag for query/export filtering

**Checkpoint**: US4 complete — unknown edges first-class in all outputs

---

## Phase 7: User Story 5 — Produce Graph Overlay Compatible with Canonical IR (Priority: P2)

**Goal**: Stable node IDs, evidence on every edge, structured JSON output.

**Independent Test**: Graph node IDs align with parser IDs; edges have evidence; partial parse → partial graph.

### Tests for User Story 5

- [ ] **T038** [P] [US5] Unit test: node IDs correlate with parser program/paragraph/section IDs in `tests/unit/test_graph_ir_compat.py`
- [ ] **T039** [P] [US5] Unit test: every edge includes evidence (file, line, span or node ID) in `tests/unit/test_graph_ir_compat.py`
- [ ] **T040** [US5] Unit test: partial parser output produces partial graph; no total failure in `tests/unit/test_graph_partial.py`

### Implementation for User Story 5

- [ ] **T041** [US5] Align node IDs with parser output: `program:<name>`, `paragraph:<program>:<name>`, etc.
- [ ] **T042** [US5] Ensure every edge has `evidence: [{ file, line, span_ref }]` or `node_id`
- [ ] **T043** [US5] Implement best-effort: skip failed programs, continue building graph; failed programs as unresolved CALLS targets
- [ ] **T044** [US5] Publish final graph schema; validate output against `graph-node.schema.json` and `graph-edge.schema.json`

**Checkpoint**: US5 complete — canonical IR overlay compatible

---

## Phase 8: User Story 6 — Optional JCL/File/Table Entity Extraction (Priority: P3)

**Goal**: File nodes from FD/SD; Table nodes from EXEC SQL; optional FEEDS/SCHEDULED_BY from JCL.

**Independent Test**: CardDemo FD definitions produce File nodes; absence of JCL does not fail.

### Tests for User Story 6

- [ ] **T045** [P] [US6] Unit test: FD entries produce File nodes; READ/WRITE link via READS_FIELD/WRITES_FIELD in `tests/unit/test_graph_files.py`
- [ ] **T046** [P] [US6] Unit test: EXEC SQL produces Table nodes (or stubs) in `tests/unit/test_graph_tables.py`
- [ ] **T047** [US6] Unit test: absence of JCL does not cause extraction failure in `tests/unit/test_graph_jcl_optional.py`

### Implementation for User Story 6

- [ ] **T048** [US6] Implement `FileExtractor` in `app/graph/extractors/files.py`: FD/SD → File nodes
- [ ] **T049** [US6] Implement `TableExtractor` in `app/graph/extractors/tables.py`: EXEC SQL → Table nodes (stub if needed)
- [ ] **T050** [US6] Optional: JCL adapter for FEEDS/SCHEDULED_BY; no-op when JCL unavailable
- [ ] **T051** [US6] Wire optional extractors; ensure all are additive and non-blocking

**Checkpoint**: US6 complete — optional File/Table/JCL extraction

---

## Phase 9: Polish & Performance

**Purpose**: Cross-cutting concerns

- [ ] **T052** [P] Performance: Graph extraction for CardDemo completes in < 60 seconds; add benchmark test
- [ ] **T053** [P] Add `quickstart.md` or run instructions for graph extraction in `specs/002-dependency-graph/`
- [ ] **T054** Run full CardDemo + taxe-fonciere validation; verify SC-001 through SC-008

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Foundation)**: Depends on Phase 1 — BLOCKS all user stories
- **Phases 3–8 (User Stories)**: All depend on Phase 2
  - US1, US2 can proceed in parallel after Phase 2 (US2 may depend on US1 for shared builder)
  - US3 depends on US1, US2
  - US4 spans all extractors; implement alongside US1–US2
  - US5 is cross-cutting; implement after US1–US2
  - US6 is additive; implement last
- **Phase 9 (Polish)**: After desired user stories complete

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Extractors before pipeline wiring
- Core implementation before integration
