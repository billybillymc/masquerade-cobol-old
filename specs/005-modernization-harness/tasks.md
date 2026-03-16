# Tasks: Modernization Pilot + Differential Test Harness

**Input**: Design documents from `specs/005-modernization-harness/`  
**Prerequisites**: plan.md (required), spec.md (required), 001–004 implemented

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, schema definitions, numeric semantics contract

- [ ] T001 Create/verify `services/validation-harness/` Python project with pytest, pyproject.toml
- [ ] T002 [P] Create JSON schema files in `packages/schemas/` for ScopedModule, ModernCandidate, TestVector, DifferentialRun, Mismatch, ConfidenceScore, Gate
- [ ] T003 [P] Write `specs/005-modernization-harness/numeric-semantics.md` documenting PIC mapping, rounding, overflow, null/blank, comparison
- [ ] T004 [P] Create `specs/005-modernization-harness/contracts/` with API contract definitions for harness and gates
- [ ] T005 Create `generated/java/` and `generated/python/` output directories
- [ ] T006 Add validation-harness HTTP API skeleton with health check
- [ ] T007 Verify CardDemo parsed outputs, graph, and semantic pipeline available from 001–004

**Checkpoint**: Validation harness project ready; numeric semantics contract documented.

---

## Phase 2: Foundation — Numeric Semantics (TDD)

**Purpose**: Implement numeric semantics contract as foundation for test vectors and differential execution

**⚠️ CRITICAL**: Numeric semantics must complete before test vector generation and differential harness

### Tests for Numeric Semantics

- [ ] T008 [US6] Write failing test: PIC 9(5)V99 COMP-3 maps to BigDecimal with correct scale — `tests/test_numeric_semantics.py`
- [ ] T009 [P] [US6] Write failing test: rounding rules per contract — `tests/test_numeric_semantics.py`
- [ ] T010 [P] [US6] Write failing test: overflow policy enforced — `tests/test_numeric_semantics.py`
- [ ] T011 [P] [US6] Write failing test: null/blank coercion rules — `tests/test_numeric_semantics.py`
- [ ] T012 [P] [US6] Write failing test: comparison semantics — `tests/test_numeric_semantics.py`

### Implementation for Numeric Semantics

- [ ] T013 [US6] Implement `NumericSemanticsContract` — `src/numeric/semantics_contract.py`
- [ ] T014 [US6] Implement `BigDecimalEmulation` for Java target — `src/numeric/bigdecimal_emulation.py`
- [ ] T015 [US6] Make all numeric semantics tests pass

**Checkpoint**: Numeric semantics contract implemented. Strict emulation ready.

---

## Phase 3: User Story 5 — HITL Gates Foundation (Priority: P2)

**Goal**: Implement four-gate HITL pipeline with approval store; gates block advancement until approvals

**Note**: Gates are implemented early so candidate generation and differential harness can enforce them

### Tests for HITL Gates

- [ ] T016 [US5] Write failing test: module with insufficient parse coverage blocked at Exploration Gate — `tests/test_hitl_gates.py`
- [ ] T017 [P] [US5] Write failing test: Candidate Generation Gate requires Modernization Engineer approval — `tests/test_hitl_gates.py`
- [ ] T018 [P] [US5] Write failing test: Differential Test Gate requires mismatch review before advancement — `tests/test_hitl_gates.py`
- [ ] T019 [P] [US5] Write failing test: Readiness Gate requires domain owner approval — `tests/test_hitl_gates.py`
- [ ] T020 [P] [US5] Write failing test: approval recorded with role and timestamp — `tests/test_hitl_gates.py`

### Implementation for HITL Gates

- [ ] T021 [US5] Implement `Gate` model and `GateEvaluator` — `src/gates/gate_evaluator.py`
- [ ] T022 [US5] Implement `ExplorationGate` evaluation (parse coverage, evidence quality) — `src/gates/gate_evaluator.py`
- [ ] T023 [US5] Implement `HITLPipeline` with four gates — `src/gates/hitl_pipeline.py`
- [ ] T024 [US5] Implement `ApprovalStore` with audit log — `src/gates/approval_store.py`
- [ ] T025 [US5] Make all HITL gate tests pass

**Checkpoint**: HITL gates implemented. Exploration Gate blocks failed modules.

---

## Phase 4: User Story 1 — Generate Modern Candidate (Priority: P1)

**Goal**: Generate Java (default) or Python candidate for scoped module with evidence anchors; block if Exploration Gate fails

**Independent Test**: Select scoped CardDemo module passing Exploration Gate; verify Java candidate with source-span citations

### Tests for User Story 1

- [ ] T026 [US1] Write failing test: scoped module passing Exploration Gate produces Java candidate with evidence anchors — `tests/test_candidate_generator.py`
- [ ] T027 [P] [US1] Write failing test: Python target produces Python candidate when selected — `tests/test_candidate_generator.py`
- [ ] T028 [P] [US1] Write failing test: module failing Exploration Gate blocked from generation — `tests/test_candidate_generator.py`
- [ ] T029 [P] [US1] Write failing test: semantic mappings (PIC→type, paragraph→method) traceable to source — `tests/test_candidate_generator.py`

### Implementation for User Story 1

- [ ] T030 [US1] Implement `ExplorationGate` integration (call from 004/003) — `src/candidate/exploration_gate.py`
- [ ] T031 [US1] Implement `CandidateGenerator` with LLM + AST/graph context — `src/candidate/generator.py`
- [ ] T032 [US1] Implement `SemanticMapping` with source-span links — `src/candidate/semantic_mapping.py`
- [ ] T033 [US1] Add candidate generation HTTP endpoint — `src/api/harness_api.py`
- [ ] T034 [US1] Make all US1 tests pass

**Checkpoint**: Candidate generation working. Blocked for failed Exploration Gate.

---

## Phase 5: User Story 2 — Auto-Generate Test Vectors (Priority: P1)

**Goal**: Auto-generate test vectors from COBOL logic including golden vectors and optional property-based fuzzing

**Independent Test**: Run test vector generation on CardDemo module with numeric logic; verify vectors for boundary, rounding, comparison

### Tests for User Story 2

- [ ] T035 [US2] Write failing test: module with numeric logic produces golden vectors for edge cases — `tests/test_test_vector_generator.py`
- [ ] T036 [P] [US2] Write failing test: vectors respect PIC mapping and scale rules — `tests/test_test_vector_generator.py`
- [ ] T037 [P] [US2] Write failing test: property-based fuzzing produces vectors in sandbox mode — `tests/test_test_vector_generator.py`
- [ ] T038 [P] [US2] Write failing test: vectors executable against legacy and generated — `tests/test_test_vector_generator.py`

### Implementation for User Story 2

- [ ] T039 [US2] Implement `GoldenVectors` for edge cases (overflow, rounding, null/blank, comparison) — `src/test_vectors/golden_vectors.py`
- [ ] T040 [US2] Implement `TestVectorGenerator` — `src/test_vectors/generator.py`
- [ ] T041 [US2] Implement optional `PropertyFuzz` for sandbox — `src/test_vectors/property_fuzz.py`
- [ ] T042 [US2] Add test vector generation HTTP endpoint — `src/api/harness_api.py`
- [ ] T043 [US2] Make all US2 tests pass

**Checkpoint**: Test vector generation working. Golden vectors cover numeric semantics.

---

## Phase 6: User Story 3 — Differential Harness (Priority: P1)

**Goal**: Run same test vectors against legacy and generated; produce diff report; strict emulation for migration-ready

**Independent Test**: Run harness on CardDemo module; verify matches reported, mismatches surfaced with evidence

### Tests for User Story 3

- [ ] T044 [US3] Write failing test: same vectors run against legacy and generated; outputs compared — `tests/test_differential_harness.py`
- [ ] T045 [P] [US3] Write failing test: match → pass; mismatch → test vector, expected, actual, source evidence — `tests/test_differential_harness.py`
- [ ] T046 [P] [US3] Write failing test: migration-ready uses strict emulation; sandbox may use bounded-equivalence — `tests/test_differential_harness.py`
- [ ] T047 [P] [US3] Write failing test: legacy stub mode when COBOL cannot execute — `tests/test_differential_harness.py`
- [ ] T048 [P] [US3] Write failing test: generated candidate compile failure reported and blocks execution — `tests/test_differential_harness.py`

### Implementation for User Story 3

- [ ] T049 [US3] Implement `LegacyRunner` (COBOL or golden output stub) — `src/differential/legacy_runner.py`
- [ ] T050 [US3] Implement `GeneratedRunner` (Java execution via subprocess) — `src/differential/generated_runner.py`
- [ ] T051 [US3] Implement `DifferentialHarness` — `src/differential/harness.py`
- [ ] T052 [US3] Implement mismatch surfacing with full context — `src/differential/harness.py`
- [ ] T053 [US3] Add differential run HTTP endpoint — `src/api/harness_api.py`
- [ ] T054 [US3] Make all US3 tests pass

**Checkpoint**: Differential harness working. Mismatches surfaced. Strict emulation enforced.

---

## Phase 7: User Story 4 — Confidence Score (Priority: P1)

**Goal**: Produce confidence score from pass rate, evidence quality, numeric coverage; ≥ 95% pass meets gate threshold

**Independent Test**: Run harness on modules with varying pass rates; verify score correlates with pass rate

### Tests for User Story 4

- [ ] T055 [US4] Write failing test: confidence reflects proportion of passed test vectors — `tests/test_confidence_score.py`
- [ ] T056 [P] [US4] Write failing test: ≥ 95% pass → score meets Differential Test Gate threshold — `tests/test_confidence_score.py`
- [ ] T057 [P] [US4] Write failing test: < 95% pass → score does not meet threshold — `tests/test_confidence_score.py`
- [ ] T058 [P] [US4] Write failing test: score includes components (pass rate, evidence quality, numeric coverage) — `tests/test_confidence_score.py`

### Implementation for User Story 4

- [ ] T059 [US4] Implement `ConfidenceScore` computation — `src/differential/confidence_score.py` (or new module)
- [ ] T060 [US4] Wire confidence score into differential run output and gate evaluation
- [ ] T061 [US4] Make all US4 tests pass

**Checkpoint**: Confidence score working. Gate threshold logic correct.

---

## Phase 8: User Story 5 — HITL Integration (Priority: P2)

**Goal**: Wire Candidate Generation Gate, Differential Test Gate, Readiness Gate into pipeline; require approvers

### Tests for HITL Integration

- [ ] T062 [US5] Write failing test: Candidate Generation Gate blocks until Modernization Engineer approves — `tests/test_hitl_gates.py`
- [ ] T063 [P] [US5] Write failing test: Differential Test Gate blocks until mismatches reviewed — `tests/test_hitl_gates.py`
- [ ] T064 [P] [US5] Write failing test: Readiness Gate requires domain owner approval for migration-ready — `tests/test_hitl_gates.py`
- [ ] T065 [P] [US5] Write failing test: modules cannot bypass gates — `tests/test_hitl_gates.py`

### Implementation for HITL Integration

- [ ] T066 [US5] Wire Candidate Generation Gate into candidate generation flow
- [ ] T067 [US5] Wire Differential Test Gate into differential run flow (≥ 95% pass + approval)
- [ ] T068 [US5] Wire Readiness Gate; require Modernization Engineer + Domain SME + Risk/Controls Owner
- [ ] T069 [US5] Add gate HTTP endpoints — `src/api/harness_api.py`
- [ ] T070 [US5] Make all US5 integration tests pass

**Checkpoint**: Full HITL pipeline working. All four gates enforced.

---

## Phase 9: User Story 7 — Validated Modernization Percentage (Priority: P3)

**Goal**: Compute and report validated modernization percentage = migration-ready with passing diff / total submitted

### Tests for User Story 7

- [ ] T071 [US7] Write failing test: N modules submitted, M migration-ready → percentage = M/N — `tests/test_validated_percentage.py`
- [ ] T072 [P] [US7] Write failing test: metric distinguishes in-progress from migration-ready — `tests/test_validated_percentage.py`
- [ ] T073 [P] [US7] Write failing test: failed differential validation excluded from numerator — `tests/test_validated_percentage.py`

### Implementation for User Story 7

- [ ] T074 [US7] Implement validated modernization percentage computation
- [ ] T075 [US7] Add metric to harness API and reporting
- [ ] T076 [US7] Make all US7 tests pass

**Checkpoint**: Validated modernization percentage reportable.

---

## Phase 10: Integration & Edge Cases

**Purpose**: End-to-end validation, edge case handling, polish

- [ ] T077 Implement legacy stub/golden output mode when COBOL cannot execute
- [ ] T078 Handle non-deterministic vectors (flag and exclude from strict pass/fail)
- [ ] T079 Handle external dependency stubbing; surface limitations in confidence score
- [ ] T080 Write integration test: full pipeline on CardDemo module — `tests/integration/test_carddemo_harness.py`
- [ ] T081 [P] Update `services/validation-harness/README.md` with architecture and usage
- [ ] T082 [P] Verify all JSON output validates against `packages/schemas/`

**Checkpoint**: Full modernization pilot working on CardDemo. Edge cases handled.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Numeric Semantics)**: Depends on Phase 1
- **Phase 3 (HITL Gates)**: Depends on Phase 1
- **Phase 4 (US1 Candidate)**: Depends on Phase 3 (Exploration Gate)
- **Phase 5 (US2 Test Vectors)**: Depends on Phase 2 (numeric semantics)
- **Phase 6 (US3 Differential)**: Depends on Phase 2, 4, 5
- **Phase 7 (US4 Confidence)**: Depends on Phase 6
- **Phase 8 (US5 HITL Integration)**: Depends on Phase 3, 4, 6, 7
- **Phase 9 (US7 Percentage)**: Depends on Phase 8
- **Phase 10 (Integration)**: Depends on Phase 9

### Parallel Opportunities

- T002, T003, T004 can run in parallel (Phase 1)
- Phase 4 and Phase 5 can start in parallel after Phase 2 (Phase 4 also needs Phase 3)
- T081, T082 can run in parallel (Phase 10)
- All tasks marked [P] within a phase can run in parallel
