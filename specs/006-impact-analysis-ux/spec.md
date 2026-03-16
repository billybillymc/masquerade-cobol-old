# Feature Specification: Impact Analysis UX + Hardening + Benchmark

**Feature Branch**: `006-impact-analysis-ux`  
**Created**: 2026-03-13  
**Status**: Draft  
**Input**: Week 6 polish/demo/hardening — impact analysis UX, exploration UI, benchmark report, 10-minute wow demo flow.

**Context**: Week 6 (final week) of 6-week MVP. All previous features (001–005) are prerequisites. This is the polish, demo, and hardening week.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Impact Analysis: "If I Change This Copybook Field, What Breaks?" (Priority: P1)

A senior COBOL engineer selects a copybook field (or program, paragraph, or data item) and asks the system to show the blast radius of a hypothetical change. The system returns all programs, paragraphs, and downstream artifacts that would be affected, with evidence anchors and confidence. The engineer can assess risk before making changes.

**Why this priority**: Impact analysis is the primary proof point per PRD. "What breaks if I change X?" is the core question the platform answers. This is the flagship capability for the 10-minute demo.

**Independent Test**: Can be fully tested by selecting a copybook field in CardDemo, requesting impact analysis, and verifying that all programs that reference the field (directly or via copybook) are returned with evidence.

**Acceptance Scenarios**:

1. **Given** a copybook field selected by the user, **When** the user requests impact analysis, **Then** the system returns a ranked list of affected programs, paragraphs, and artifacts with evidence anchors (file, node ID, span).
2. **Given** an impact analysis result, **When** the user inspects it, **Then** each affected item includes a confidence score and the evidence supporting the impact claim.
3. **Given** a change to a program or paragraph, **When** the user requests impact analysis, **Then** the system returns callers, callees, and data-dependent artifacts that would be affected.
4. **Given** impact analysis results, **When** the user requests a change simulation, **Then** the blast radius is presented in a clear, actionable format (e.g., list, graph, or both).

---

### User Story 2 - Exploration UI: Dependency Graph Browsing and Code+Explanation Side-by-Side (Priority: P1)

A modernization architect explores the codebase by browsing the dependency graph. The UI shows programs, copybooks, and their relationships. When the user selects a node or edge, the corresponding code and explanation (summary, rule, or lineage) appear side-by-side. The architect can navigate from graph to code to explanation without losing context.

**Why this priority**: Exploration is the primary discovery path. Graph browsing + code + explanation side-by-side enables efficient triage and understanding. This supports the demo narrative and daily use.

**Independent Test**: Can be fully tested by opening the exploration UI, selecting a program in the graph, and verifying that code and explanation appear side-by-side with correct linkage.

**Acceptance Scenarios**:

1. **Given** the exploration UI, **When** the user opens it, **Then** the dependency graph is displayed with programs, copybooks, and their relationships (CALLS, USES_COPYBOOK, READS_FIELD, WRITES_FIELD).
2. **Given** a node selected in the graph, **When** the user clicks it, **Then** the corresponding code and explanation (summary, rule, or lineage) appear side-by-side.
3. **Given** an edge selected in the graph, **When** the user clicks it, **Then** the evidence for that relationship (source span, file, line) is shown with the linked code.
4. **Given** the side-by-side view, **When** the user navigates to a different node, **Then** the code and explanation update to reflect the new selection; context is preserved.
5. **Given** a paragraph that has been summarized, **When** the user selects it in the graph, **Then** the summary is displayed with evidence anchors that link to the source.

---

### User Story 3 - Conceptual Query: "Where Do We Calculate Late Fees?" (Priority: P1)

A business analyst asks a natural-language question such as "Where do we calculate late fees?" The system returns a ranked answer with evidence and confidence. The user can click through to lineage, view the impacted code, and see the blast radius of a hypothetical change. This is the opening question of the 10-minute demo.

**Why this priority**: Conceptual search is the entry point for the demo wedge. It demonstrates the platform's ability to answer business questions with code evidence. Per PRD locked decisions, this is step 1 of the 10-minute demo flow.

**Independent Test**: Can be fully tested by running the query against CardDemo (or a corpus with known late-fee logic) and verifying that ranked results include evidence-backed citations and confidence scores.

**Acceptance Scenarios**:

1. **Given** a conceptual query, **When** the user submits it, **Then** the system returns a ranked answer with evidence and confidence.
2. **Given** a ranked result, **When** the user clicks it, **Then** the user can navigate to lineage and view the impacted code.
3. **Given** a result with lineage, **When** the user requests change simulation, **Then** the blast radius is presented in the ROI/readiness panel.

---

### User Story 4 - Change Simulation Blast Radius and ROI/Readiness Panel (Priority: P1)

A modernization architect simulates a change to a selected artifact (field, program, paragraph). The system shows the blast radius—all affected programs and artifacts—and presents an ROI/readiness panel. The panel shows readiness score (parser coverage + evidence quality + testability + dependency isolation), impact accuracy, and migration considerations.

**Why this priority**: Change simulation and ROI/readiness complete the demo flow (steps 4–5 of the 10-minute demo). They enable stakeholders to assess migration effort and risk before committing.

**Independent Test**: Can be fully tested by simulating a change to a CardDemo field and verifying that the blast radius and ROI/readiness panel are populated correctly.

**Acceptance Scenarios**:

1. **Given** a selected artifact (field, program, paragraph), **When** the user requests change simulation, **Then** the system displays the blast radius and ROI/readiness panel.
2. **Given** the ROI/readiness panel, **When** displayed, **Then** it includes readiness score components: parser coverage, evidence/verifier quality, testability, dependency isolation.
3. **Given** impact analysis results, **When** the user reviews them, **Then** impact accuracy (correct impact predictions / total reviewed impact predictions) is reported where applicable.
4. **Given** the blast radius, **When** displayed, **Then** affected items are ranked and include evidence; the user can drill into each affected artifact.

---

### User Story 5 - Benchmark Report on 500K LOC Corpus (Priority: P2)

A program manager needs to validate the platform at scale. The system runs a benchmark on a corpus of 500K LOC (MVP target) and produces a report. The report includes ingest success rate, incremental refresh rate, parser coverage, and reliability metrics. It demonstrates that the platform meets production-scale expectations.

**Why this priority**: The 500K LOC benchmark is the MVP proof point for scale. Per PRD locked decisions, MVP benchmark scale is 500K LOC. Reliability SLOs: ingest 99.0%, incremental refresh 99.5%, parser coverage 90%/95%.

**Independent Test**: Can be fully tested by running the benchmark on a 500K LOC corpus and verifying that the report includes the required metrics and meets SLO thresholds.

**Acceptance Scenarios**:

1. **Given** a corpus of 500K LOC, **When** the benchmark runs, **Then** the system produces a report with ingest success rate, incremental refresh rate, parser coverage, and reliability metrics.
2. **Given** the benchmark report, **When** evaluated, **Then** ingest success rate >= 99.0%.

3. **Given** the benchmark report, **When** evaluated, **Then** incremental refresh success rate >= 99.5%.
4. **Given** the benchmark report, **When** evaluated, **Then** parser coverage meets 90% (baseline) or 95% (migration-candidate) targets where applicable.
5. **Given** the benchmark report, **When** displayed, **Then** it is human-readable and actionable for stakeholder review.

---

### User Story 6 - The 10-Minute Wow Demo Flow (Priority: P2)

A sales or stakeholder demo follows a prescribed narrative: (1) Ask "Where do we calculate late fees?"; (2) Receive ranked answer with evidence and confidence; (3) Lineage click-through; (4) Change simulation blast radius; (5) ROI/readiness panel. The flow can be completed in approximately 10 minutes and demonstrates the full value proposition.

**Why this priority**: The 10-minute demo is the product wedge. It proves the platform's value in a single, repeatable flow. This is the polish deliverable for Week 6.

**Independent Test**: Can be fully tested by executing the five steps in sequence on a prepared corpus and verifying that each step completes successfully and the flow is coherent.

**Acceptance Scenarios**:

1. **Given** a prepared corpus (e.g., CardDemo or demo dataset), **When** the demo flow is executed, **Then** step 1 (conceptual query) returns a ranked answer with evidence and confidence.
2. **Given** a result from step 1, **When** the user clicks through lineage, **Then** step 3 (lineage click-through) navigates to the relevant code and dependencies.
3. **Given** lineage context, **When** the user requests change simulation, **Then** step 4 (blast radius) displays affected artifacts.
4. **Given** the blast radius, **When** the user views the ROI/readiness panel, **Then** step 5 (ROI/readiness panel) shows readiness score and migration considerations.
5. **Given** the full flow, **When** executed by a trained user, **Then** the demo completes in approximately 10 minutes.

---

### User Story 7 - Impact Accuracy as Primary Proof Point (Priority: P2)

A risk/controls stakeholder needs assurance that impact predictions are correct. The system tracks impact accuracy = correct impact predictions / total reviewed impact predictions. This metric is the primary proof point per PRD and is reported in the benchmark and dashboard.

**Why this priority**: Impact accuracy is the primary proof point. Without it, stakeholders cannot trust the platform for migration decisions. It must be measurable and reportable.

**Independent Test**: Can be fully tested by reviewing a set of impact predictions against ground truth (manual verification) and verifying that the accuracy metric is computed correctly.

**Acceptance Scenarios**:

1. **Given** N impact predictions that have been reviewed by a human, **When** M are confirmed correct, **Then** impact accuracy = M / N.
2. **Given** the impact accuracy metric, **When** reported, **Then** it is included in the benchmark report and dashboard.
3. **Given** an impact prediction, **When** the user marks it for review, **Then** the system supports recording correct/incorrect for accuracy calculation.

---

### User Story 8 - Hardening: Reliability SLOs and Error Handling (Priority: P2)

An operations engineer needs the platform to meet reliability SLOs. The system achieves ingest 99.0%, incremental refresh 99.5%, and parser coverage 90%/95%. Errors are surfaced clearly; partial failures do not block the entire pipeline. The system degrades gracefully.

**Why this priority**: Hardening is critical for production readiness. Week 6 is the hardening week; SLOs must be met for MVP sign-off.

**Independent Test**: Can be fully tested by running the pipeline under failure conditions and verifying that SLOs are met and errors are handled gracefully.

**Acceptance Scenarios**:

1. **Given** a batch of files to ingest, **When** some fail, **Then** the system reports failures without blocking successful ingest; ingest success rate is computed and meets 99.0% for valid inputs.
2. **Given** an incremental refresh, **When** some files change, **Then** the system processes changes without full re-ingest; incremental refresh success rate meets 99.5%.
3. **Given** a parse failure, **When** it occurs, **Then** the error is surfaced with location and remediation hint; remaining files continue processing.
4. **Given** partial pipeline failure (e.g., graph build fails for one program), **When** it occurs, **Then** the system produces partial results and surfaces the failure; the pipeline does not abort entirely.

---

### Edge Cases

- **What happens when the dependency graph is incomplete (e.g., unresolved edges)?** The system MUST include unresolved edges in impact analysis with explicit labeling; impact accuracy MUST account for uncertainty.

- **What happens when a conceptual query returns no results?** The system MUST return "no results found" with clear messaging rather than fabricate or return low-confidence results without evidence.

- **What happens when the corpus exceeds 500K LOC?** The benchmark MUST support scaling; the 500K target is the MVP minimum; larger corpora may require pagination or sampling for the report.

- **What happens when the user selects an artifact that has no downstream dependencies?** The system MUST return an empty blast radius with clear messaging; this is a valid outcome.

- **What happens when evidence quality is low for an impact prediction?** The system MUST surface low confidence and include the prediction in the "reviewed" set for accuracy calculation with appropriate uncertainty labeling.

- **What happens when the exploration UI loads a very large graph?** The system MUST support progressive loading or summarization; the UI MUST remain responsive.

- **What happens when a benchmark run is interrupted?** The system MUST support resumability or partial report; partial results MUST be clearly labeled.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support impact analysis: "if I change this copybook field (or program, paragraph, data item), what breaks?"
- **FR-002**: System MUST return impact analysis results with ranked affected artifacts, evidence anchors, and confidence scores.
- **FR-003**: System MUST provide an exploration UI with dependency graph browsing and code+explanation side-by-side.
- **FR-004**: System MUST support conceptual query (e.g., "Where do we calculate late fees?") with ranked answers, evidence, and confidence.
- **FR-005**: System MUST support lineage click-through from query results to code and dependencies.
- **FR-006**: System MUST support change simulation with blast radius and ROI/readiness panel.
- **FR-007**: System MUST display readiness score with components: parser coverage, evidence/verifier quality, testability, dependency isolation.
- **FR-008**: System MUST compute and report impact accuracy = correct impact predictions / total reviewed impact predictions.
- **FR-009**: System MUST produce a benchmark report on 500K LOC corpus with ingest rate, incremental refresh rate, parser coverage, and reliability metrics.
- **FR-010**: System MUST meet reliability SLOs: ingest 99.0%, incremental refresh 99.5%, parser coverage 90%/95%.
- **FR-011**: System MUST support the 10-minute demo flow: conceptual query → ranked answer → lineage click-through → change simulation → ROI/readiness panel.
- **FR-012**: System MUST surface errors with location and remediation; partial failures MUST NOT block the entire pipeline.
- **FR-013**: System MUST include unresolved edges in impact analysis with explicit uncertainty labeling.
- **FR-014**: System MUST return "no results found" for conceptual queries with no matches rather than fabricate.
- **FR-015**: System MUST support recording correct/incorrect for impact predictions to compute impact accuracy.

### Key Entities

- **Impact Analysis Request**: A user request for blast radius of a hypothetical change. Key attributes: artifact (field, program, paragraph), scope, filters.
- **Impact Analysis Result**: The set of affected artifacts. Key attributes: ranked list, evidence per item, confidence scores, blast radius summary.
- **Exploration View**: The UI state for graph browsing. Key attributes: selected node, selected edge, code view, explanation view.
- **Conceptual Query**: A natural-language question. Key attributes: query text, corpus scope.
- **Query Result**: Ranked answer with evidence. Key attributes: rank, evidence anchors, confidence, lineage link.
- **Blast Radius**: The set of artifacts affected by a change. Key attributes: affected programs, paragraphs, copybooks, files.
- **ROI/Readiness Panel**: Summary of migration readiness. Key attributes: readiness score, components (parser coverage, evidence quality, testability, dependency isolation), impact accuracy.
- **Benchmark Report**: Report from corpus run. Key attributes: corpus size, ingest rate, incremental refresh rate, parser coverage, reliability metrics, impact accuracy.
- **Impact Accuracy**: Metric = correct impact predictions / total reviewed. Key attributes: numerator, denominator, review status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Impact accuracy is correctly computed and reported (correct impact predictions / total reviewed impact predictions).
- **SC-002**: Benchmark report is produced for 500K LOC corpus with ingest >= 99.0%, incremental refresh >= 99.5%.
- **SC-003**: Parser coverage meets 90% (baseline) or 95% (migration-candidate) targets in the benchmark.
- **SC-004**: The 10-minute demo flow completes successfully: conceptual query → ranked answer → lineage click-through → change simulation → ROI/readiness panel.
- **SC-005**: Impact analysis returns all affected artifacts with evidence for a selected copybook field in the test corpus.
- **SC-006**: Exploration UI displays dependency graph with code+explanation side-by-side; selection updates views correctly.
- **SC-007**: Conceptual query returns ranked results with evidence and confidence; no fabricated results when no evidence exists.
- **SC-008**: Partial pipeline failures do not block the entire pipeline; errors are surfaced with location and remediation.
- **SC-009**: Readiness score components (parser coverage, evidence quality, testability, dependency isolation) are displayed in the ROI/readiness panel.
- **SC-010**: Unresolved edges are included in impact analysis with explicit uncertainty labeling.
