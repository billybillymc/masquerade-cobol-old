# Tasks: LLM Semantic Analysis Pipeline

**Input**: Design documents from `/specs/003-semantic-pipeline/`  
**Prerequisites**: plan.md (required), spec.md (required), features 001 (parser) and 002 (graph) available

**Tests**: TDD enforced. Write failing tests first, then implementation.

**Organization**: Tasks grouped by user story. Tests before implementation within each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[USn]**: User story label (US1–US7)
- Paths: `services/analysis-orchestrator/`, `packages/schemas/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and semantic module structure

- [ ] **T001** Create `services/analysis-orchestrator/app/semantic/` module with `__init__.py`, `summarizer.py`, `rule_extractor.py`, `verifier.py`, `retrieval.py`, `thresholds.py`, `prompts.py`
- [ ] **T002** Add semantic dependencies to `services/analysis-orchestrator/pyproject.toml` (LLM client, embedding lib, vector store)
- [ ] **T003** [P] Add `packages/schemas/summary.schema.json` with text, evidence anchors, confidence, review_status
- [ ] **T004** [P] Extend `packages/schemas/claim.schema.json` for rule extraction: contradictions, support_strength; ensure evidence minItems and structure

---

## Phase 2: Foundation (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] **T005** Implement `RetrievalUnitBuilder` in `app/semantic/retrieval.py`: paragraph/section + surrounding data definitions + caller/callee from graph; NOT raw file dumps
- [ ] **T006** Implement LLM client adapter in `app/semantic/llm_client.py`: external-first mode, configurable endpoint, structured output support
- [ ] **T007** Implement evidence contract validation: required fields (claim_id, claim_text, evidence, support_strength, confidence_score, review_status)
- [ ] **T008** Implement `EvidenceThresholds` in `app/semantic/thresholds.py`: baseline (2 anchors, 0.70), critical (3 anchors + cross-artifact, 0.85)
- [ ] **T009** [P] Add CardDemo and taxe-fonciere fixtures for parser + graph output in `tests/fixtures/`

**Checkpoint**: Foundation ready — user story implementation can begin

---

## Phase 3: User Story 1 — Paragraph/Section Plain-English Summaries (Priority: P1) 🎯 MVP

**Goal**: Summary with evidence anchors; grounded in AST + graph context; "insufficient evidence" when verifier fails.

**Independent Test**: Request summary for CardDemo paragraph; verify at least one source anchor; cited spans correspond to unit.

### Tests for User Story 1

- [ ] **T010** [P] [US1] Unit test: summary request returns plain-English text with evidence anchors (file, node ID, span) in `tests/unit/test_semantic_summarizer.py`
- [ ] **T011** [P] [US1] Unit test: summary uses retrieval unit (paragraph + data defs + caller/callee), not raw file in `tests/unit/test_semantic_retrieval.py`
- [ ] **T012** [US1] Unit test: insufficient evidence returns "insufficient evidence" rather than fabricated answer in `tests/unit/test_semantic_summarizer.py`
- [ ] **T013** [US1] Integration test: CardDemo paragraph summary includes resolvable evidence anchors in `tests/integration/test_semantic_summary_carddemo.py`

### Implementation for User Story 1

- [ ] **T014** [US1] Implement summary prompt template in `app/semantic/prompts.py`: request plain-English explanation with citation requirements
- [ ] **T015** [US1] Implement `Summarizer` in `app/semantic/summarizer.py`: build retrieval unit, call LLM, parse response for evidence anchors
- [ ] **T016** [US1] Wire summarizer to return structured output (text, evidence, confidence, review_status) per `summary.schema.json`
- [ ] **T017** [US1] Add "insufficient evidence" path when verifier fails or evidence too weak

**Checkpoint**: US1 complete — paragraph summaries with citations

---

## Phase 4: User Story 2 — Candidate Business Rule Extraction (Priority: P1)

**Goal**: Structured rule candidates with claim_id, claim_text, evidence, support_strength, confidence_score, review_status; "likely rule" vs "hypothesis" labeling.

**Independent Test**: Rule extraction on taxe-fonciere; every rule has required schema; "likely rule" only when support ≥ medium and verifier passes.

### Tests for User Story 2

- [ ] **T018** [P] [US2] Unit test: rule candidate includes claim_id, claim_text, evidence, support_strength, confidence_score, review_status in `tests/unit/test_semantic_rule_extractor.py`
- [ ] **T019** [P] [US2] Unit test: verifier pass + support ≥ medium → "likely rule" label in `tests/unit/test_semantic_rule_extractor.py`
- [ ] **T020** [P] [US2] Unit test: low support or contradiction → "hypothesis" label in `tests/unit/test_semantic_rule_extractor.py`
- [ ] **T021** [US2] Unit test: verifier fail or insufficient evidence → "rejected" label in `tests/unit/test_semantic_rule_extractor.py`
- [ ] **T022** [US2] Integration test: taxe-fonciere rule extraction produces verifiable outputs in `tests/integration/test_semantic_rules_taxe_fonciere.py`

### Implementation for User Story 2

- [ ] **T023** [US2] Implement rule extraction prompt in `app/semantic/prompts.py`: extract candidate rules with evidence anchors
- [ ] **T024** [US2] Implement `RuleExtractor` in `app/semantic/rule_extractor.py`: build retrieval unit, call LLM, parse structured output
- [ ] **T025** [US2] Implement labeling logic: "likely rule" when verifier pass + support ≥ medium + thresholds met; "hypothesis" when low/contradiction; "rejected" otherwise
- [ ] **T026** [US2] Validate output against `claim.schema.json`; ensure evidence list with source_id, span_ref

**Checkpoint**: US2 complete — business rule extraction in structured form

---

## Phase 5: User Story 3 — Evidence Thresholds and Critical Module Handling (Priority: P1)

**Goal**: Baseline: 2 anchors, 0.70; critical: 3 anchors + cross-artifact, 0.85.

**Independent Test**: Designate subset of CardDemo as critical; rules from critical require 3 anchors and 0.85.

### Tests for User Story 3

- [ ] **T027** [P] [US3] Unit test: baseline module with 2+ anchors, verifier pass, confidence ≥ 0.70 → may be "likely rule" in `tests/unit/test_semantic_thresholds.py`
- [ ] **T028** [P] [US3] Unit test: critical module with < 3 anchors or confidence < 0.85 → NOT "likely rule" in `tests/unit/test_semantic_thresholds.py`
- [ ] **T029** [P] [US3] Unit test: critical module with 3+ anchors (including cross-artifact), verifier pass, confidence ≥ 0.85 → may be "likely rule" in `tests/unit/test_semantic_thresholds.py`
- [ ] **T030** [US3] Integration test: CardDemo critical subset enforces stricter thresholds in `tests/integration/test_semantic_thresholds_carddemo.py`

### Implementation for User Story 3

- [ ] **T031** [US3] Implement `EvidenceThresholds.check_baseline`: 2 anchors, confidence ≥ 0.70
- [ ] **T032** [US3] Implement `EvidenceThresholds.check_critical`: 3 anchors, at least one cross-artifact, confidence ≥ 0.85
- [ ] **T033** [US3] Add critical module designation input (policy/config); apply correct threshold per module
- [ ] **T034** [US3] Wire thresholds into rule extractor labeling; block "likely rule" when thresholds not met

**Checkpoint**: US3 complete — tiered evidence thresholds enforced

---

## Phase 6: User Story 4 — Two-Pass Draft-and-Verify Generation (Priority: P2)

**Goal**: Draft → verifier checks cited spans; fabricated citations rejected.

**Independent Test**: Draft with fake citations rejected; draft with valid citations passes.

### Tests for User Story 4

- [ ] **T035** [P] [US4] Unit test: verifier checks each cited span exists and supports claim in `tests/unit/test_semantic_verifier.py`
- [ ] **T036** [P] [US4] Unit test: draft with non-existent citations → rejected in `tests/unit/test_semantic_verifier.py`
- [ ] **T037** [P] [US4] Unit test: draft with valid supporting citations → review_status auto-passed in `tests/unit/test_semantic_verifier.py`
- [ ] **T038** [US4] Integration test: end-to-end two-pass flow for summary and rule in `tests/integration/test_semantic_two_pass.py`

### Implementation for User Story 4

- [ ] **T039** [US4] Implement `Verifier` in `app/semantic/verifier.py`: input draft + cited spans; resolve spans from parser/graph; check support
- [ ] **T040** [US4] Verifier logic: if span missing or does not support claim → reject; if all support → pass
- [ ] **T041** [US4] Wire verifier into summarizer and rule extractor: draft → verifier → downgrade or accept
- [ ] **T042** [US4] Verifier does not fabricate; only validates cited evidence

**Checkpoint**: US4 complete — two-pass draft-and-verify operational

---

## Phase 7: User Story 5 — Rejected and Low-Support Claim Visibility and Blocking (Priority: P2)

**Goal**: Rejected/hypothesis claims visible; blocked from migration-impact actions; override requires reviewer note.

**Independent Test**: Rejected claims visible in output; migration actions blocked; override captures identity, reason, justification.

### Tests for User Story 5

- [ ] **T043** [P] [US5] Unit test: rejected claim has explicit label in output in `tests/unit/test_semantic_visibility.py`
- [ ] **T044** [P] [US5] Unit test: migration-impact action blocked for rejected/hypothesis claim in `tests/unit/test_semantic_visibility.py`
- [ ] **T045** [US5] Unit test: override requires reviewer identity, reason code, justification; audit-logged in `tests/unit/test_semantic_visibility.py`

### Implementation for User Story 5

- [ ] **T046** [US5] Ensure all claims (including rejected/hypothesis) included in output with explicit labels
- [ ] **T047** [US5] Add `blocked_from_actions` or equivalent flag to claim schema for UI consumption
- [ ] **T048** [US5] Implement override workflow: reviewer_identity, reason_code, justification; persist and audit-log
- [ ] **T049** [US5] Expose override API or data model for web-app integration (004/006)

**Checkpoint**: US5 complete — visibility and blocking policy enforced

---

## Phase 8: User Story 6 — False-Positive Rate Compliance (Priority: P2)

**Goal**: ≤ 1% critical, ≤ 3% non-critical on labeled benchmark.

**Independent Test**: Run pipeline on benchmark; compare "likely rule" to ground truth; verify rates.

### Tests for User Story 6

- [ ] **T050** [P] [US6] Create or adopt labeled benchmark (golden_rules.jsonl) in `tests/eval/fixtures/`
- [ ] **T051** [US6] Eval test: critical modules false-positive rate ≤ 1% in `tests/eval/test_false_positive_benchmark.py`
- [ ] **T052** [US6] Eval test: non-critical modules false-positive rate ≤ 3% in `tests/eval/test_false_positive_benchmark.py`

### Implementation for User Story 6

- [ ] **T053** [US6] Implement benchmark runner: run pipeline on golden set, compare outputs to labels
- [ ] **T054** [US6] Compute false-positive rate: (incorrect "likely rule" claims) / (total "likely rule" claims)
- [ ] **T055** [US6] Gate or report: fail CI if rates exceed thresholds; document in eval README

**Checkpoint**: US6 complete — false-positive rates validated

---

## Phase 9: User Story 7 — RAG-Style Conceptual Query (Priority: P3)

**Goal**: Natural-language query → ranked answers with citations; hybrid retrieval; p95 ≤ 9.0s.

**Independent Test**: Conceptual query against CardDemo; answers have citations; retrieval uses paragraph + context; latency meets target.

### Tests for User Story 7

- [ ] **T056** [P] [US7] Unit test: conceptual query returns ranked results with evidence anchors and confidence in `tests/unit/test_semantic_rag.py`
- [ ] **T057** [P] [US7] Unit test: retrieval uses paragraph/section + data defs + caller/callee, not raw files in `tests/unit/test_semantic_retrieval.py`
- [ ] **T058** [US7] Performance test: RAG p95 latency ≤ 9.0 seconds in `tests/integration/test_semantic_rag_latency.py`

### Implementation for User Story 7

- [ ] **T059** [US7] Implement hybrid retrieval: lexical (BM25/keyword) + embedding + graph-neighbor expansion in `app/semantic/retrieval.py`
- [ ] **T060** [US7] Implement embedding pipeline: chunk retrieval units, embed, index in vector store
- [ ] **T061** [US7] Implement conceptual query flow: query → hybrid retrieval → LLM generation → citations
- [ ] **T062** [US7] Add latency instrumentation; optimize if p95 exceeds 9.0s (caching, batch, model choice)

**Checkpoint**: US7 complete — RAG conceptual query with citations

---

## Phase 10: Polish & Cross-Cutting

**Purpose**: Final validation and documentation

- [ ] **T063** [P] Add parser/graph gap surfacing: outputs include uncertainty labels when evidence incomplete
- [ ] **T064** [P] Add contradictions field population when contradictory evidence found
- [ ] **T065** Run full CardDemo + taxe-fonciere validation; verify SC-001 through SC-008
- [ ] **T066** Document quickstart or run instructions in `specs/003-semantic-pipeline/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Foundation)**: Depends on Phase 1 — BLOCKS all user stories
- **Phases 3–9 (User Stories)**: All depend on Phase 2
  - US1 (summaries) can start after Phase 2
  - US2 (rules) depends on US1 for retrieval/verifier patterns
  - US3 (thresholds) depends on US2
  - US4 (two-pass) spans US1 and US2; implement verifier early
  - US5 (visibility) depends on US2 output shape
  - US6 (false-positive) depends on US2, US3, US4
  - US7 (RAG) depends on retrieval foundation; can parallel with US2
- **Phase 10 (Polish)**: After desired user stories complete

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Prompts before extractors; verifier before full pipeline
- Core implementation before integration
