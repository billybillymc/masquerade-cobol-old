# Feature Specification: Modernization Pilot + Differential Test Harness

**Feature Branch**: `005-modernization-harness`  
**Created**: 2026-03-13  
**Status**: Draft  
**Input**: PRD Section 5.6 "Modernization Pilot" — generate modern-language candidates for scoped modules, auto-generate test vectors, run differential tests, produce confidence scores.

**Context**: Week 5 of 6-week MVP. Prerequisites: 001 (parser), 002 (graph), 003 (semantic pipeline), 004 (lineage). IBM Enterprise COBOL target.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate Modern-Language Candidate for Scoped Module (Priority: P1)

A modernization engineer selects a COBOL module that has passed the Exploration Gate (sufficient parse coverage and evidence quality). The system generates a modern-language candidate for the scoped module, with Java as the default target and Python as an optional target. The candidate preserves semantic intent and maps COBOL constructs to equivalent modern constructs with evidence anchors linking back to source spans.

**Why this priority**: Candidate generation is the core output of the modernization pilot. Without it, differential testing and confidence scoring cannot proceed. This is the primary deliverable for Week 5.

**Independent Test**: Can be fully tested by selecting a scoped CardDemo module that meets readiness thresholds and verifying that a Java (or Python) candidate is produced with source-span citations for key mappings.

**Acceptance Scenarios**:

1. **Given** a scoped COBOL module that has passed the Exploration Gate, **When** the user requests candidate generation with Java as target, **Then** the system produces a Java candidate with evidence anchors linking key constructs to source spans.
2. **Given** a scoped module with Python as optional target, **When** the user requests candidate generation, **Then** the system produces a Python candidate when that target is selected.
3. **Given** a module that has not passed the Exploration Gate, **When** the user requests candidate generation, **Then** the system blocks generation and surfaces the gate failure reason.
4. **Given** a generated candidate, **When** the user inspects it, **Then** semantic mappings (e.g., PIC to type, paragraph to method) are traceable to source evidence.

---

### User Story 2 - Auto-Generate Test Vectors from COBOL Logic (Priority: P1)

A modernization engineer needs executable test inputs to validate that the generated candidate behaves equivalently to the legacy COBOL. The system auto-generates test vectors from the COBOL logic—including golden vectors for known edge cases and property-based numeric fuzzing where applicable. Vectors cover data type boundaries, rounding/scale rules, and comparison semantics per the numeric semantics contract.

**Why this priority**: Without test vectors, differential testing cannot run. Auto-generation reduces manual effort and ensures coverage of numeric semantics edge cases that are critical for migration correctness.

**Independent Test**: Can be fully tested by running test vector generation on a CardDemo module with numeric logic and verifying that vectors are produced for boundary conditions, rounding, and comparison cases defined in the numeric semantics contract.

**Acceptance Scenarios**:

1. **Given** a scoped COBOL module with numeric logic, **When** test vector generation runs, **Then** the system produces a golden vector suite covering edge cases (overflow, rounding, null/blank coercion, comparison semantics).
2. **Given** a module with PIC clauses and USAGE declarations, **When** test vector generation runs, **Then** vectors respect data type mapping (PIC to runtime type) and scale rules from the numeric semantics contract.
3. **Given** a module suitable for property-based fuzzing, **When** test vector generation runs, **Then** property-based numeric fuzzing vectors may be produced for sandbox/bounded-equivalence scenarios.
4. **Given** generated test vectors, **When** consumed by the differential harness, **Then** they are executable against both legacy and generated implementations.

---

### User Story 3 - Run Legacy vs Generated and Diff Outputs (Priority: P1)

A modernization engineer runs the differential test harness: the same test vectors are executed against the legacy COBOL implementation and the generated modern implementation. The system compares outputs and produces a diff report showing matches and mismatches. For migration-ready modules, numeric semantics use strict emulation; bounded-equivalence is permitted only in sandbox mode.

**Why this priority**: Differential testing is the primary validation mechanism. It answers "does the generated code produce the same results as the legacy?" and gates the 95% diff pass requirement for modernization pilot success.

**Independent Test**: Can be fully tested by running the harness on a CardDemo module with known-good legacy behavior and verifying that matches are reported correctly and mismatches are surfaced with evidence (test vector, expected vs actual, source location).

**Acceptance Scenarios**:

1. **Given** a scoped module with generated candidate and test vectors, **When** the differential harness runs, **Then** the same vectors execute against legacy and generated implementations and outputs are compared.
2. **Given** outputs that match for a test vector, **When** the harness completes, **Then** the result is recorded as a pass with no diff.
3. **Given** outputs that differ for a test vector, **When** the harness completes, **Then** the mismatch is surfaced with the test vector, expected output, actual output, and evidence linking to source.
4. **Given** a module in migration-ready mode, **When** the harness runs, **Then** numeric semantics use strict emulation; bounded-equivalence is not applied.
5. **Given** a module in sandbox mode, **When** the harness runs, **Then** bounded-equivalence may be used for numeric semantics where configured.

---

### User Story 4 - Produce Confidence Score (Priority: P1)

A risk/controls stakeholder reviewing modernization candidates needs a quantitative confidence score. The system produces a confidence score based on differential test pass rate, evidence quality, and numeric semantics coverage. The score supports the decision to advance a module to the Differential Test Gate for human review.

**Why this priority**: Confidence scores enable gating and prioritization. Per PRD, the modernization pilot diff pass must be >= 95% on the scoped module test suite; the confidence score reflects progress toward that threshold.

**Independent Test**: Can be fully tested by running the harness on modules with varying diff pass rates and verifying that the confidence score correlates with pass rate and evidence quality.

**Acceptance Scenarios**:

1. **Given** a completed differential test run, **When** the confidence score is computed, **Then** it reflects the proportion of test vectors that passed (diff match).
2. **Given** a module with >= 95% diff pass on its test suite, **When** the confidence score is computed, **Then** the score meets the threshold for advancement to the Differential Test Gate.
3. **Given** a module with < 95% diff pass, **When** the confidence score is computed, **Then** the score does not meet the gate threshold and the module is not advanced without human review of mismatches.
4. **Given** a confidence score, **When** displayed, **Then** it includes the components (pass rate, evidence quality, numeric semantics coverage) that contributed to it.

---

### User Story 5 - HITL Validation Pipeline Gates (Priority: P2)

A domain owner and risk/controls stakeholder need a structured human-in-the-loop (HITL) validation pipeline. The system enforces four gates: (1) Exploration Gate—sufficient parse coverage and evidence quality; (2) Candidate Generation Gate—human reviews semantic mapping before generation; (3) Differential Test Gate—human reviews mismatches before approving; (4) Readiness Gate—domain owner approves "migration-ready." Minimum approvers: Modernization Engineer + Domain SME + Risk/Controls Owner.

**Why this priority**: HITL gates ensure accountability and reduce risk. Modules enter modernization only when readiness >= threshold, ROI >= threshold, and named reviewers are assigned. This is a locked PRD decision.

**Independent Test**: Can be fully tested by simulating gate transitions and verifying that each gate requires the appropriate approvals and that modules cannot bypass gates.

**Acceptance Scenarios**:

1. **Given** a module with insufficient parse coverage or evidence quality, **When** the Exploration Gate is evaluated, **Then** the module is blocked from candidate generation.
2. **Given** a module that passes the Exploration Gate, **When** the Candidate Generation Gate is reached, **Then** a human reviewer (Modernization Engineer or equivalent) must approve the semantic mapping before generation proceeds.
3. **Given** a module with differential test mismatches, **When** the Differential Test Gate is reached, **Then** a human reviewer must review mismatches and either approve (with justification) or reject before advancement.
4. **Given** a module that passes the Differential Test Gate with >= 95% diff pass, **When** the Readiness Gate is reached, **Then** the domain owner must approve "migration-ready" for the module to be marked as such.
5. **Given** any gate transition, **When** approval is recorded, **Then** the approver role (Modernization Engineer, Domain SME, Risk/Controls Owner) is captured and audit-logged.

---

### User Story 6 - Numeric Semantics Contract and Golden Vectors (Priority: P2)

A modernization engineer needs assurance that numeric behavior is correctly preserved. The system implements the numeric semantics contract: data type mapping (PIC to runtime type), rounding/scale rules, overflow policy, null/blank coercion, and comparison semantics. A golden vector suite covers edge cases; property-based numeric fuzzing is available for sandbox validation.

**Why this priority**: Numeric semantics are a major source of migration defects. The contract and golden vectors reduce risk and support the "strict emulation for migration-ready" policy.

**Independent Test**: Can be fully tested by running the golden vector suite against modules with known numeric behavior and verifying that strict emulation produces correct results, and that bounded-equivalence (in sandbox) is clearly distinguished.

**Acceptance Scenarios**:

1. **Given** a COBOL data item with PIC 9(5)V99 COMP-3, **When** the numeric semantics contract is applied, **Then** the mapping to runtime type, rounding, and scale rules are documented and enforced in test vectors.
2. **Given** the golden vector suite, **When** run against a migration-ready candidate, **Then** strict emulation is used; no bounded-equivalence shortcuts.
3. **Given** a sandbox validation scenario, **When** property-based numeric fuzzing runs, **Then** bounded-equivalence may be used and results are labeled as such.
4. **Given** overflow, null, or blank coercion scenarios, **When** test vectors are generated, **Then** they cover the overflow policy and null/blank coercion rules from the contract.

---

### User Story 7 - Validated Modernization Percentage Metric (Priority: P3)

A program manager needs to track modernization progress. The system computes validated modernization percentage = modules marked migration-ready with passing differential validation / total submitted. This metric is reportable and supports portfolio-level visibility.

**Why this priority**: Portfolio visibility enables prioritization and stakeholder reporting. Lower priority than core pilot functionality but required for program governance.

**Independent Test**: Can be fully tested by submitting a set of modules, advancing some through the full pipeline to migration-ready, and verifying the percentage is computed correctly.

**Acceptance Scenarios**:

1. **Given** N modules submitted for modernization, **When** M modules are marked migration-ready with passing differential validation, **Then** validated modernization percentage = M / N.
2. **Given** the metric, **When** reported, **Then** it distinguishes modules in progress from those migration-ready.
3. **Given** a module that fails differential validation, **When** counted, **Then** it is not included in the migration-ready numerator.

---

### Edge Cases

- **What happens when the legacy COBOL cannot be executed (e.g., no mainframe runtime)?** The system MUST support a "legacy stub" or "golden output" mode where pre-recorded legacy outputs are used for comparison; the mode MUST be explicitly labeled and not used for migration-ready validation without human approval.
- **What happens when a test vector produces different results on repeated runs (non-determinism)?** The system MUST flag non-deterministic vectors and exclude them from strict pass/fail counts until resolved; they MAY be reported separately.
- **What happens when the generated candidate fails to compile?** The system MUST report compilation failure with error details and block differential test execution; the confidence score MUST reflect the failure.
- **What happens when PIC/COMP-3 or other numeric types have no direct modern equivalent?** The system MUST document the mapping choice and any approximation; strict emulation requires a compatible runtime representation or explicit "unsupported" with evidence.
- **What happens when a module has external dependencies (CALL, file I/O) that cannot be stubbed?** The system MUST support dependency stubbing or mocking for differential test isolation; unstubbed dependencies MUST be surfaced as limitations in the confidence score.
- **What happens when HITL approvers are not assigned?** The system MUST block advancement past gates that require named reviewers; modules cannot enter modernization without assigned Modernization Engineer, Domain SME, and Risk/Controls Owner.
- **What happens when ROI or readiness is below threshold?** The system MUST block modules from entering modernization; the thresholds are configurable policy inputs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST generate modern-language candidates for scoped modules with Java as default target and Python as optional target.
- **FR-002**: System MUST block candidate generation for modules that have not passed the Exploration Gate (sufficient parse coverage and evidence quality).
- **FR-003**: System MUST auto-generate test vectors from COBOL logic, including golden vectors for edge cases and optional property-based numeric fuzzing.
- **FR-004**: System MUST implement the numeric semantics contract: data type mapping (PIC to runtime type), rounding/scale rules, overflow policy, null/blank coercion, comparison semantics.
- **FR-005**: System MUST use strict numeric emulation for migration-ready modules; bounded-equivalence is permitted only in sandbox mode and MUST be explicitly labeled.
- **FR-006**: System MUST run the same test vectors against legacy and generated implementations and produce a diff report (matches and mismatches).
- **FR-007**: System MUST surface mismatches with test vector, expected output, actual output, and evidence linking to source.
- **FR-008**: System MUST produce a confidence score reflecting differential test pass rate, evidence quality, and numeric semantics coverage.
- **FR-009**: System MUST require >= 95% diff pass on the scoped module test suite for modernization pilot success (advancement to Differential Test Gate).
- **FR-010**: System MUST enforce the HITL validation pipeline: Exploration Gate, Candidate Generation Gate, Differential Test Gate, Readiness Gate.
- **FR-011**: System MUST require minimum approvers: Modernization Engineer + Domain SME + Risk/Controls Owner for gate transitions.
- **FR-012**: System MUST block modules from entering modernization when readiness < threshold, ROI < threshold, or named reviewers are not assigned.
- **FR-013**: System MUST compute validated modernization percentage = modules marked migration-ready with passing differential validation / total submitted.
- **FR-014**: System MUST support legacy stub or golden output mode when legacy cannot be executed; the mode MUST be explicitly labeled.
- **FR-015**: System MUST link generated candidate constructs to source spans (evidence anchors) for traceability.
- **FR-016**: System MUST audit-log gate approvals with approver role and timestamp.

### Key Entities

- **Scoped Module**: A COBOL program or procedural unit selected for modernization. Key attributes: name, source path, parse coverage, evidence quality, readiness score, ROI estimate.
- **Modern Candidate**: Generated modern-language code (Java or Python). Key attributes: target language, source mappings (evidence anchors), semantic mapping summary.
- **Test Vector**: An executable input set for differential testing. Key attributes: inputs, expected output (from legacy or golden), data types, edge case category.
- **Differential Test Run**: Execution of test vectors against legacy and generated implementations. Key attributes: pass count, fail count, mismatch details, confidence score.
- **Mismatch**: A test vector for which legacy and generated outputs differ. Key attributes: test vector ID, expected output, actual output, source evidence.
- **Confidence Score**: Quantitative measure of modernization readiness. Key attributes: pass rate, evidence quality component, numeric semantics coverage, gate eligibility.
- **Gate**: A validation checkpoint in the HITL pipeline. Key attributes: gate type (Exploration, Candidate Generation, Differential Test, Readiness), status (passed/blocked), approver roles, timestamp.
- **Numeric Semantics Contract**: Specification of PIC-to-runtime mapping, rounding, overflow, null/blank, comparison. Key attributes: data type rules, golden vector coverage, strict vs bounded-equivalence policy.
- **Migration-Ready Module**: A module approved at the Readiness Gate with >= 95% differential test pass. Key attributes: module ID, approval timestamp, approver identities.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Modernization pilot diff pass >= 95% on scoped module test suite for modules advanced to Differential Test Gate.
- **SC-002**: Validated modernization percentage is correctly computed (migration-ready with passing differential / total submitted).
- **SC-003**: Golden vector suite covers edge cases for PIC types, rounding, overflow, null/blank coercion, and comparison semantics.
- **SC-004**: Confidence score correlates with differential test pass rate; modules with >= 95% pass receive score meeting gate threshold.
- **SC-005**: All four HITL gates (Exploration, Candidate Generation, Differential Test, Readiness) are enforced with required approver roles.
- **SC-006**: Modules below readiness or ROI threshold are blocked from entering modernization.
- **SC-007**: Generated candidates include evidence anchors linking key constructs to source spans; 100% of semantic mappings are traceable.
- **SC-008**: Strict numeric emulation is used for migration-ready modules; bounded-equivalence is never applied without explicit sandbox labeling.
- **SC-009**: Mismatches are surfaced with full context (test vector, expected, actual, source evidence) for human review.
