# Tasks: Field Lineage + Conceptual Search

**Input**: Design documents from `specs/004-lineage-search/`  
**Prerequisites**: plan.md (required), spec.md (required), 001/002/003 implemented

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, schema definitions, and test codebase preparation

- [ ] T001 Create/verify `services/analysis-orchestrator/` Python project with pytest, pyproject.toml
- [ ] T002 [P] Create JSON schema files in `packages/schemas/` for LineageTrace, BlastRadius, ConceptualSearchResult, RetrievalChunk, UnknownEdge
- [ ] T003 [P] Verify CardDemo and taxe-fonciere parsed outputs and graph are available from 001/002/003
- [ ] T004 [P] Create `specs/004-lineage-search/contracts/` with API contract definitions for lineage, impact, RAG
- [ ] T005 Configure embedding model and vector store (or mock) for retrieval tests
- [ ] T006 Add analysis-orchestrator HTTP API skeleton (FastAPI or Flask) with health check

**Checkpoint**: Analysis orchestrator project ready; schemas and contracts defined.

---

## Phase 2: Foundation — Hybrid Retrieval

**Purpose**: Implement hybrid retrieval (lexical + embedding + graph-neighbor) as the foundation for lineage and RAG

**⚠️ CRITICAL**: Hybrid retrieval must complete before US1 (conceptual search) and US2 (lineage) implementation

### Tests for Hybrid Retrieval

- [ ] T007 [US5] Write failing test: given a conceptual query, retrieval returns chunks from lexical + embedding + graph-neighbor — `tests/test_hybrid_retriever.py`
- [ ] T008 [P] [US5] Write failing test: each retrieval chunk has provenance header (program, paragraph, copybook) — `tests/test_hybrid_retriever.py`
- [ ] T009 [P] [US5] Write failing test: context is limited to high-signal slices; low-signal excluded — `tests/test_hybrid_retriever.py`
- [ ] T010 [P] [US5] Write failing test: graph-neighbor expansion includes caller/callee and data-definition context — `tests/test_hybrid_retriever.py`

### Implementation for Hybrid Retrieval

- [ ] T011 [US5] Implement `ChunkBuilder` — paragraph/section + surrounding data definitions + caller/callee — `src/retrieval/chunk_builder.py`
- [ ] T012 [US5] Implement lexical index (BM25 or keyword) over chunks — `src/retrieval/hybrid_retriever.py`
- [ ] T013 [US5] Implement embedding index and similarity search — `src/retrieval/hybrid_retriever.py`
- [ ] T014 [US5] Implement graph-neighbor expansion — `src/retrieval/hybrid_retriever.py`
- [ ] T015 [US5] Implement `HybridRetriever` merge and rank logic — `src/retrieval/hybrid_retriever.py`
- [ ] T016 [US5] Implement provenance header generation — `src/retrieval/provenance_header.py`
- [ ] T017 [US5] Make all hybrid retrieval tests pass

**Checkpoint**: Hybrid retrieval working. Chunks have provenance; high-signal slicing applied.

---

## Phase 3: User Story 2 — Trace Field Lineage (Priority: P1)

**Goal**: Trace a selected field through pipeline paths with confidence labels and unknown edges as first-class outputs

**Independent Test**: Select a known field in CardDemo, request lineage, verify trace from input to output with evidence at each step

### Tests for User Story 2

- [ ] T018 [US2] Write failing test: given a selected field, lineage returns trace with steps linked to source spans — `tests/test_field_lineage.py`
- [ ] T019 [P] [US2] Write failing test: each step includes confidence score and ambiguity label where applicable — `tests/test_field_lineage.py`
- [ ] T020 [P] [US2] Write failing test: uncertain/unresolved steps surfaced with "unknown" or "uncertain" labels — `tests/test_field_lineage.py`
- [ ] T021 [P] [US2] Write failing test: field with no downstream lineage returns trace indicating input/source only — `tests/test_field_lineage.py`
- [ ] T022 [P] [US2] Write failing test: lineage across unresolved edge (dynamic CALL, missing copybook) includes step with explicit label — `tests/test_field_lineage.py`

### Implementation for User Story 2

- [ ] T023 [US2] Implement `LineageTrace` and `UnknownEdge` models — `src/lineage/lineage_trace.py`, `src/lineage/unknown_edge.py`
- [ ] T024 [US2] Implement `FieldLineage` using graph READS_FIELD/WRITES_FIELD and MOVE chains — `src/lineage/field_lineage.py`
- [ ] T025 [US2] Implement confidence and ambiguity labeling — `src/lineage/field_lineage.py`
- [ ] T026 [US2] Implement unknown edge handling (dynamic CALL, missing copybook) — `src/lineage/field_lineage.py`
- [ ] T027 [US2] Add lineage HTTP endpoint — `src/api/lineage_search_api.py`
- [ ] T028 [US2] Make all US2 tests pass; verify lineage p95 ≤ 4.0s on CardDemo

**Checkpoint**: Field lineage working. Unknown edges surfaced. Latency target met.

---

## Phase 4: User Story 3 — Blast Radius Impact Analysis (Priority: P1)

**Goal**: Return programs, paragraphs, and downstream consumers that depend on a field, with evidence and unknown dependencies surfaced

**Independent Test**: Select a copybook field in CardDemo used by multiple programs; verify blast radius includes all dependents with evidence

### Tests for User Story 3

- [ ] T029 [US3] Write failing test: given a copybook field, blast radius returns affected programs, paragraphs, consumers — `tests/test_blast_radius.py`
- [ ] T030 [P] [US3] Write failing test: each affected item has evidence anchors (file, line, span) — `tests/test_blast_radius.py`
- [ ] T031 [P] [US3] Write failing test: unresolved dependencies surfaced with explicit "unknown" labels — `tests/test_blast_radius.py`
- [ ] T032 [P] [US3] Write failing test: programs that failed to parse are included in blast radius with "parse failed" label — `tests/test_blast_radius.py`

### Implementation for User Story 3

- [ ] T033 [US3] Implement `BlastRadius` model — `src/impact/blast_radius_model.py`
- [ ] T034 [US3] Implement `BlastRadius` computation via graph traversal — `src/impact/blast_radius.py`
- [ ] T035 [US3] Implement evidence anchors and confidence per affected item — `src/impact/blast_radius.py`
- [ ] T036 [US3] Implement unknown dependency handling — `src/impact/blast_radius.py`
- [ ] T037 [US3] Add impact HTTP endpoint — `src/api/lineage_search_api.py`
- [ ] T038 [US3] Make all US3 tests pass; verify impact p95 ≤ 6.0s on CardDemo

**Checkpoint**: Blast radius working. Unknown dependencies surfaced. Latency target met.

---

## Phase 5: User Story 1 — Conceptual Search (Priority: P1)

**Goal**: Natural-language queries return ranked answers grounded in code evidence with source spans, confidence, provenance

**Independent Test**: Query "Where do we calculate late fees?" against CardDemo; verify ranked results with evidence, confidence, provenance

### Tests for User Story 1

- [ ] T039 [US1] Write failing test: given "where do we calculate late fees?", returns ranked answers with evidence spans and confidence — `tests/test_conceptual_search.py`
- [ ] T040 [P] [US1] Write failing test: each result has provenance headers — `tests/test_conceptual_search.py`
- [ ] T041 [P] [US1] Write failing test: results meet evidence threshold (2 anchors + 0.70 baseline; 3 anchors + 0.85 critical) — `tests/test_conceptual_search.py`
- [ ] T042 [P] [US1] Write failing test: no high-confidence matches → "insufficient evidence" or low-confidence indicators; no fabrication — `tests/test_conceptual_search.py`
- [ ] T043 [P] [US1] Write failing test: RAG p95 latency ≤ 9.0s — `tests/test_conceptual_search.py`

### Implementation for User Story 1

- [ ] T044 [US1] Implement `ConceptualSearch` using hybrid retrieval + LLM — `src/rag/conceptual_search.py`
- [ ] T045 [US1] Implement evidence threshold enforcement — `src/rag/evidence_threshold.py`
- [ ] T046 [US1] Implement two-pass verifier for RAG answers — `src/rag/conceptual_search.py`
- [ ] T047 [US1] Add RAG HTTP endpoint — `src/api/lineage_search_api.py`
- [ ] T048 [US1] Make all US1 tests pass; verify RAG p95 ≤ 9.0s on CardDemo

**Checkpoint**: Conceptual search working. Evidence thresholds enforced. No fabrication.

---

## Phase 6: User Story 4 — Code + Explanation Side-by-Side (Priority: P2)

**Goal**: Display explanation side-by-side with source code, grounded in semantic pipeline outputs with evidence citations

**Independent Test**: Navigate to a paragraph in CardDemo; verify explanation appears alongside code with citations

### Tests for User Story 4

- [ ] T049 [US4] Write failing test: given code region, returns explanation with evidence citations — `tests/test_code_explanation.py`
- [ ] T050 [P] [US4] Write failing test: low-confidence/insufficient evidence → "hypothesis" or "insufficient evidence" label — `tests/test_code_explanation.py`
- [ ] T051 [P] [US4] Write failing test: explanation limited to high-signal slices with provenance headers — `tests/test_code_explanation.py`

### Implementation for User Story 4

- [ ] T052 [US4] Implement explanation lookup from semantic pipeline (003) outputs — `src/rag/code_explanation.py`
- [ ] T053 [US4] Add explanation HTTP endpoint — `src/api/lineage_search_api.py`
- [ ] T054 [US4] Implement `CodeExplanationView` side-by-side component in web-app — `services/web-app/src/components/CodeExplanationView.tsx`
- [ ] T055 [US4] Make all US4 tests pass

**Checkpoint**: Code + explanation side-by-side working.

---

## Phase 7: Web-App Integration

**Purpose**: Integrate lineage, blast radius, conceptual search, and code+explanation into exploration UI

- [ ] T056 [P] Implement `LineageTracePanel` component — `services/web-app/src/components/LineageTracePanel.tsx`
- [ ] T057 [P] Implement `BlastRadiusPanel` component — `services/web-app/src/components/BlastRadiusPanel.tsx`
- [ ] T058 [P] Implement `ConceptualSearchPanel` component — `services/web-app/src/components/ConceptualSearchPanel.tsx`
- [ ] T059 Wire lineage, impact, RAG, explanation APIs from web-app to analysis-orchestrator
- [ ] T060 Write integration test: conceptual query → ranked result → lineage click-through → blast radius — `tests/integration/test_carddemo_lineage_search.py`
- [ ] T061 End-to-end manual test: 10-minute demo flow on CardDemo

**Checkpoint**: Full exploration UI integrated. Demo flow achievable.

---

## Phase 8: User Story 6 — Stress Test (Priority: P3)

**Goal**: Validate performance and evidence quality on ~500K LOC corpus

- [ ] T062 [US6] Run lineage and conceptual search against ~500K LOC corpus
- [ ] T063 [US6] Verify lineage p95 ≤ 4.0s, impact p95 ≤ 6.0s, RAG p95 ≤ 9.0s
- [ ] T064 [US6] Verify evidence thresholds and provenance maintained; no degradation
- [ ] T065 [US6] Verify unknown edges remain surfaced as first-class at scale
- [ ] T066 Document stress test results in benchmark report

**Checkpoint**: Stress test passed. Latency and quality targets met at scale.

---

## Phase 9: Polish & Cross-Cutting

- [ ] T067 [P] Update `services/analysis-orchestrator/README.md` with lineage, impact, RAG architecture
- [ ] T068 [P] Verify all JSON output validates against `packages/schemas/` definitions
- [ ] T069 Run full test suite against CardDemo and taxe-fonciere; capture results
- [ ] T070 Document API usage in `specs/004-lineage-search/contracts/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies (001/002/003 assumed available)
- **Phase 2 (Hybrid Retrieval)**: Depends on Phase 1
- **Phase 3 (US2 Lineage)**: Depends on Phase 2 (retrieval); uses graph from 002
- **Phase 4 (US3 Blast Radius)**: Depends on Phase 2; uses graph from 002
- **Phase 5 (US1 Conceptual Search)**: Depends on Phase 2 (retrieval) and 003 (semantic)
- **Phase 6 (US4 Code+Explanation)**: Depends on Phase 2 and 003
- **Phase 7 (Web-App)**: Depends on Phases 3–6
- **Phase 8 (US6 Stress Test)**: Depends on Phase 7
- **Phase 9 (Polish)**: Depends on Phase 8

### Parallel Opportunities

- T002, T003, T004, T005 can run in parallel (Phase 1)
- Phases 3 and 4 can run in parallel after Phase 2
- T056, T057, T058 can run in parallel (Phase 7)
- All tasks marked [P] within a phase can run in parallel
