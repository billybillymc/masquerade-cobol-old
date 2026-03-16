# Tasks: Impact Analysis UX + Hardening + Benchmark

**Input**: Design documents from `specs/006-impact-analysis-ux/`  
**Prerequisites**: plan.md (required), spec.md (required), 001–005 implemented

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, schema definitions, demo script

- [ ] T001 Create/verify `services/web-app/` Next.js project with TypeScript, Vitest/Jest
- [ ] T002 [P] Create JSON schema files in `packages/schemas/` for ImpactAnalysisResult, ROIReadiness, BenchmarkReport
- [ ] T003 [P] Create `specs/006-impact-analysis-ux/contracts/` with API contract definitions
- [ ] T004 [P] Write `specs/006-impact-analysis-ux/demo-script.md` with 10-minute demo flow and checkpoints
- [ ] T005 Verify 001–005 services available and integrated
- [ ] T006 Add benchmark runner skeleton in `services/analysis-orchestrator/src/benchmark/`

**Checkpoint**: Project ready; demo script documented.

---

## Phase 2: Foundation — Impact Analysis UX (Priority: P1)

**Purpose**: Implement impact analysis UX as the primary proof point

**⚠️ CRITICAL**: Impact analysis is the flagship capability; builds on 004 blast radius

### Tests for User Story 1 (Impact Analysis)

- [ ] T007 [US1] Write failing test: select copybook field → impact returns ranked affected programs, paragraphs, artifacts — `tests/ImpactAnalysisPanel.test.tsx`
- [ ] T008 [P] [US1] Write failing test: each affected item has evidence anchors and confidence — `tests/ImpactAnalysisPanel.test.tsx`
- [ ] T009 [P] [US1] Write failing test: change to program/paragraph → returns callers, callees, data-dependent artifacts — `tests/ImpactAnalysisPanel.test.tsx`
- [ ] T010 [P] [US1] Write failing test: blast radius presented in clear format (list/graph) — `tests/ImpactAnalysisPanel.test.tsx`
- [ ] T011 [P] [US1] Write failing test: artifact with no downstream dependencies → empty blast radius with clear messaging — `tests/ImpactAnalysisPanel.test.tsx`

### Implementation for User Story 1

- [ ] T012 [US1] Implement `ImpactAnalysisPanel` component — `src/components/ImpactAnalysisPanel.tsx`
- [ ] T013 [US1] Wire ImpactAnalysisPanel to 004 blast radius API — `src/lib/impact-api.ts`
- [ ] T014 [US1] Implement impact accuracy recording (mark correct/incorrect) — `src/lib/accuracy-tracking.ts`
- [ ] T015 [US1] Add impact analysis page — `src/app/impact/page.tsx`
- [ ] T016 [US1] Make all US1 tests pass

**Checkpoint**: Impact analysis UX working. Accuracy recording in place.

---

## Phase 3: User Story 2 — Exploration UI (Priority: P1)

**Goal**: Dependency graph browsing with code+explanation side-by-side; node/edge selection updates views

**Independent Test**: Open exploration UI, select program in graph, verify code and explanation appear side-by-side

### Tests for User Story 2

- [ ] T017 [US2] Write failing test: graph displays programs, copybooks, relationships (CALLS, USES_COPYBOOK, READS_FIELD, WRITES_FIELD) — `tests/DependencyGraph.test.tsx`
- [ ] T018 [P] [US2] Write failing test: node click → code + explanation side-by-side — `tests/DependencyGraph.test.tsx`
- [ ] T019 [P] [US2] Write failing test: edge click → evidence for relationship (source span, file, line) — `tests/DependencyGraph.test.tsx`
- [ ] T020 [P] [US2] Write failing test: navigate to different node → code and explanation update; context preserved — `tests/DependencyGraph.test.tsx`
- [ ] T021 [P] [US2] Write failing test: paragraph with summary → summary displayed with evidence anchors — `tests/DependencyGraph.test.tsx`
- [ ] T022 [P] [US2] Write failing test: large graph → progressive loading or summarization; UI responsive — `tests/DependencyGraph.test.tsx`

### Implementation for User Story 2

- [ ] T023 [US2] Implement `DependencyGraph` component (D3/Cytoscape/React Flow) — `src/components/DependencyGraph.tsx`
- [ ] T024 [US2] Implement progressive loading for large graphs — `src/components/DependencyGraph.tsx`
- [ ] T025 [US2] Implement code+explanation side-by-side view (integrate 004) — `src/app/exploration/code-explanation-view.tsx`
- [ ] T026 [US2] Wire node/edge selection to code and explanation APIs
- [ ] T027 [US2] Add exploration page — `src/app/exploration/page.tsx`
- [ ] T028 [US2] Make all US2 tests pass

**Checkpoint**: Exploration UI working. Graph browse + code + explanation integrated.

---

## Phase 4: User Story 3 & 4 — Conceptual Query + Change Simulation (Priority: P1)

**Goal**: Conceptual query with ranked results; lineage click-through; change simulation with blast radius and ROI/readiness panel

**Independent Test**: Run "Where do we calculate late fees?" → ranked result → lineage → change sim → ROI/readiness

### Tests for User Story 3

- [ ] T029 [US3] Write failing test: conceptual query returns ranked answer with evidence and confidence — `tests/ConceptualQueryInput.test.tsx`
- [ ] T030 [P] [US3] Write failing test: click result → navigate to lineage and impacted code — `tests/ConceptualQueryInput.test.tsx`
- [ ] T031 [P] [US3] Write failing test: result with lineage → change simulation shows blast radius — `tests/ConceptualQueryInput.test.tsx`
- [ ] T032 [P] [US3] Write failing test: no results → "no results found" messaging; no fabrication — `tests/ConceptualQueryInput.test.tsx`

### Tests for User Story 4

- [ ] T033 [US4] Write failing test: change simulation displays blast radius and ROI/readiness panel — `tests/ChangeSimulationPanel.test.tsx`
- [ ] T034 [P] [US4] Write failing test: ROI/readiness includes readiness components (parser coverage, evidence quality, testability, dependency isolation) — `tests/ROIReadinessPanel.test.tsx`
- [ ] T035 [P] [US4] Write failing test: impact accuracy reported where applicable — `tests/ROIReadinessPanel.test.tsx`
- [ ] T036 [P] [US4] Write failing test: blast radius items ranked with evidence; drill-down supported — `tests/ChangeSimulationPanel.test.tsx`

### Implementation for User Stories 3 & 4

- [ ] T037 [US3] Implement `ConceptualQueryInput` component — `src/components/ConceptualQueryInput.tsx`
- [ ] T038 [US3] Wire to 004 RAG API; implement lineage click-through navigation
- [ ] T039 [US4] Implement `ChangeSimulationPanel` — `src/components/ChangeSimulationPanel.tsx`
- [ ] T040 [US4] Implement `ROIReadinessPanel` with readiness score components — `src/components/ROIReadinessPanel.tsx`
- [ ] T041 [US4] Wire change simulation to blast radius and ROI/readiness APIs
- [ ] T042 [US3][US4] Make all US3 and US4 tests pass

**Checkpoint**: Conceptual query and change simulation working. ROI/readiness panel complete.

---

## Phase 5: User Story 7 — Impact Accuracy (Priority: P2)

**Goal**: Compute and report impact accuracy = correct / total reviewed; support recording correct/incorrect

**Independent Test**: Review N impact predictions, mark M correct; verify accuracy = M/N

### Tests for User Story 7

- [ ] T043 [US7] Write failing test: N reviewed, M correct → accuracy = M/N — `tests/impact_accuracy.test.py`
- [ ] T044 [P] [US7] Write failing test: accuracy reported in benchmark report and dashboard — `tests/impact_accuracy.test.py`
- [ ] T045 [P] [US7] Write failing test: mark prediction for review → supports recording correct/incorrect — `tests/impact_accuracy.test.py`

### Implementation for User Story 7

- [ ] T046 [US7] Implement `ImpactAccuracy` computation — `services/analysis-orchestrator/src/accuracy/impact_accuracy.py`
- [ ] T047 [US7] Implement recording API (mark correct/incorrect) — `src/api/` or analysis-orchestrator
- [ ] T048 [US7] Add accuracy to ImpactAnalysisPanel and benchmark report
- [ ] T049 [US7] Make all US7 tests pass

**Checkpoint**: Impact accuracy computed and reported. Primary proof point in place.

---

## Phase 6: User Story 5 — Benchmark Report (Priority: P2)

**Goal**: Run benchmark on 500K LOC corpus; produce report with ingest, refresh, parser coverage, reliability metrics

**Independent Test**: Run benchmark on 500K LOC corpus; verify report includes required metrics and meets SLOs

### Tests for User Story 5

- [ ] T050 [US5] Write failing test: 500K LOC corpus → report with ingest rate, refresh rate, parser coverage, reliability — `tests/test_benchmark_runner.py`
- [ ] T051 [P] [US5] Write failing test: ingest success rate ≥ 99.0% — `tests/test_benchmark_runner.py`
- [ ] T052 [P] [US5] Write failing test: incremental refresh success rate ≥ 99.5% — `tests/test_benchmark_runner.py`
- [ ] T053 [P] [US5] Write failing test: parser coverage meets 90%/95% targets — `tests/test_benchmark_runner.py`
- [ ] T054 [P] [US5] Write failing test: report human-readable and actionable — `tests/test_benchmark_runner.py`
- [ ] T055 [P] [US5] Write failing test: interrupted run → resumability or partial report labeled — `tests/test_benchmark_runner.py`

### Implementation for User Story 5

- [ ] T056 [US5] Implement `BenchmarkRunner` — `services/analysis-orchestrator/src/benchmark/runner.py`
- [ ] T057 [US5] Implement `ReportGenerator` — `services/analysis-orchestrator/src/benchmark/report_generator.py`
- [ ] T058 [US5] Add benchmark page — `src/app/benchmark/page.tsx`
- [ ] T059 [US5] Make all US5 tests pass

**Checkpoint**: Benchmark report working. 500K LOC target supported.

---

## Phase 7: User Story 6 — 10-Minute Demo Flow (Priority: P2)

**Goal**: Execute full demo flow in ~10 minutes; each step completes successfully

**Independent Test**: Run five-step demo on prepared corpus; verify flow coherent and complete

### Tests for User Story 6

- [ ] T060 [US6] Write E2E test: step 1 conceptual query → ranked answer with evidence — `tests/e2e/demo-flow.spec.ts`
- [ ] T061 [P] [US6] Write E2E test: step 2–3 lineage click-through — `tests/e2e/demo-flow.spec.ts`
- [ ] T062 [P] [US6] Write E2E test: step 4 blast radius — `tests/e2e/demo-flow.spec.ts`
- [ ] T063 [P] [US6] Write E2E test: step 5 ROI/readiness panel — `tests/e2e/demo-flow.spec.ts`
- [ ] T064 [US6] Write E2E test: full flow completes in ~10 minutes — `tests/e2e/demo-flow.spec.ts`

### Implementation for User Story 6

- [ ] T065 [US6] Integrate all components into demo flow; tune for timing
- [ ] T066 [US6] Update demo-script.md with final timing and acceptance criteria
- [ ] T067 [US6] Make all demo flow E2E tests pass

**Checkpoint**: 10-minute demo flow achievable. E2E tests green.

---

## Phase 8: User Story 8 — Hardening (Priority: P2)

**Goal**: Meet reliability SLOs; graceful error handling; partial failures do not block pipeline

**Independent Test**: Run pipeline under failure conditions; verify SLOs and graceful degradation

### Tests for User Story 8

- [ ] T068 [US8] Write failing test: batch ingest with some failures → report failures without blocking; success rate computed — `tests/test_hardening.py`
- [ ] T069 [P] [US8] Write failing test: incremental refresh with changes → processes without full re-ingest; refresh rate ≥ 99.5% — `tests/test_hardening.py`
- [ ] T070 [P] [US8] Write failing test: parse failure → error with location and remediation; remaining files continue — `tests/test_hardening.py`
- [ ] T071 [P] [US8] Write failing test: partial pipeline failure → partial results; pipeline does not abort — `tests/test_hardening.py`
- [ ] T072 [P] [US8] Write failing test: unresolved edges in impact analysis with explicit labeling — `tests/test_hardening.py`

### Implementation for User Story 8

- [ ] T073 [US8] Implement graceful degradation in ingest pipeline
- [ ] T074 [US8] Implement incremental refresh without full re-ingest
- [ ] T075 [US8] Implement parse failure handling (location, remediation hint)
- [ ] T076 [US8] Implement partial pipeline failure handling (partial results, surface failure)
- [ ] T077 [US8] Ensure unresolved edges labeled in impact analysis
- [ ] T078 [US8] Make all US8 tests pass

**Checkpoint**: Hardening complete. SLOs met. Graceful degradation verified.

---

## Phase 9: Polish & Cross-Cutting

- [ ] T079 [P] Update `services/web-app/README.md` with exploration and impact UX
- [ ] T080 [P] Verify all JSON output validates against `packages/schemas/`
- [ ] T081 Run full test suite; capture benchmark results
- [ ] T082 Document API usage in `specs/006-impact-analysis-ux/contracts/`
- [ ] T083 Final demo rehearsal; capture timing and screenshots

**Checkpoint**: MVP polish complete. Ready for sign-off.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (US1 Impact)**: Depends on Phase 1; uses 004 blast radius
- **Phase 3 (US2 Exploration)**: Depends on Phase 1; uses 002 graph, 004 code+explanation
- **Phase 4 (US3 & US4)**: Depends on Phase 2, 3; uses 004 RAG, blast radius, ROI/readiness
- **Phase 5 (US7 Accuracy)**: Depends on Phase 2
- **Phase 6 (US5 Benchmark)**: Depends on Phase 1; uses 001–004 pipeline
- **Phase 7 (US6 Demo)**: Depends on Phases 2–4
- **Phase 8 (US8 Hardening)**: Depends on Phases 2–6; cross-cutting
- **Phase 9 (Polish)**: Depends on Phase 8

### Parallel Opportunities

- T002, T003, T004 can run in parallel (Phase 1)
- Phases 2 and 3 can run in parallel after Phase 1
- T079, T080 can run in parallel (Phase 9)
- All tasks marked [P] within a phase can run in parallel
