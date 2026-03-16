# Feature Specification: LLM Semantic Analysis Pipeline

**Feature Branch**: `003-semantic-pipeline`  
**Created**: 2026-03-13  
**Status**: Draft  
**Input**: User description: "LLM semantic analysis pipeline for paragraph/section summaries, candidate business rule extraction, and evidence-backed explanations with source span citations"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Paragraph/Section Plain-English Summaries (Priority: P1)

A modernization architect selects a COBOL paragraph or section and requests a plain-English summary. The system produces a concise explanation of what the procedural unit does, grounded in the AST and dependency graph context. Every summary includes source span citations that link back to the original code. The architect can verify the explanation by clicking through to the cited locations.

**Why this priority**: Summaries are the primary entry point for understanding unfamiliar COBOL. Without them, analysts cannot efficiently triage or prioritize modules. This is the foundation of the semantic layer.

**Independent Test**: Can be fully tested by requesting summaries for paragraphs in the CardDemo codebase and verifying that each summary cites at least one source anchor (file, node/span ID) and that the cited spans correspond to the procedural unit being summarized.

**Acceptance Scenarios**:

1. **Given** a parsed COBOL program with paragraphs and sections, **When** the user requests a summary for a specific paragraph, **Then** the system returns a plain-English summary with evidence anchors (file, node ID, span) linking to the source.
2. **Given** a paragraph that references data definitions and calls other paragraphs, **When** the user requests a summary, **Then** the summary is grounded in the paragraph plus surrounding data definitions and caller/callee context, not raw long-file dumps.
3. **Given** a summary request, **When** the system cannot produce a verifier-passed explanation with sufficient evidence, **Then** the system returns "insufficient evidence" rather than a plausible but uncited answer.

---

### User Story 2 - Candidate Business Rule Extraction in Structured Form (Priority: P1)

A senior COBOL engineer asks the system to extract candidate business rules from a paragraph or section. The system produces structured rule candidates with required fields: claim_id, claim_text, evidence (source anchors with node/span IDs), support_strength (high/medium/low), contradictions, confidence_score (0–1), and review_status. Rules are labeled "likely rule" only when the verifier passes and support is at least medium; otherwise they are labeled "hypothesis."

**Why this priority**: Business rule extraction is the core value proposition for migration planning and impact analysis. Structured output with evidence anchors is mandatory for trust and downstream automation.

**Independent Test**: Can be fully tested by running rule extraction on taxe-fonciere (6 files, 2.3K LOC) and verifying that every returned rule has the required schema fields, that "likely rule" labels appear only when support >= medium and verifier passes, and that rules can be manually verified against the source.

**Acceptance Scenarios**:

1. **Given** a paragraph containing identifiable business logic, **When** the system extracts rules, **Then** each rule includes claim_id, claim_text, evidence (list of source anchors with node/span IDs), support_strength, confidence_score, and review_status.
2. **Given** a rule candidate with verifier pass and support_strength >= medium, **When** displayed, **Then** it is labeled "likely rule."
3. **Given** a rule candidate with low support or contradiction, **When** displayed, **Then** it is labeled "hypothesis" and remains visible but blocked from migration-impacting actions.
4. **Given** a rule candidate that fails the verifier or has insufficient evidence, **When** displayed, **Then** it is labeled rejected, visible for transparency, and blocked from action; any override requires reviewer identity, reason code, and justification note.

---

### User Story 3 - Evidence Thresholds and Critical Module Handling (Priority: P1)

A risk/controls stakeholder needs assurance that high-stakes modules are held to stricter evidence standards. For baseline modules, the system requires at least 2 independent evidence anchors, verifier pass, and confidence >= 0.70 before labeling a claim "likely rule." For critical modules (financial/compliance/safety), the system requires at least 3 independent evidence anchors (including one cross-artifact anchor such as code + copybook/JCL/DB2 reference), verifier pass, and confidence >= 0.85.

**Why this priority**: Trust calibration is non-negotiable for enterprise adoption. Tiered thresholds prevent overconfidence in migration-critical logic while allowing practical discovery in lower-risk areas.

**Independent Test**: Can be fully tested by designating a subset of CardDemo as "critical" and verifying that rules from those modules require 3 anchors and higher confidence before "likely rule" labeling, while baseline modules accept 2 anchors and 0.70.

**Acceptance Scenarios**:

1. **Given** a baseline (non-critical) module, **When** a rule candidate has 2+ anchors, verifier pass, and confidence >= 0.70, **Then** it may be labeled "likely rule" if support_strength >= medium.
2. **Given** a critical module, **When** a rule candidate has fewer than 3 anchors or confidence < 0.85, **Then** it is NOT labeled "likely rule" even if verifier passes.
3. **Given** a critical module, **When** a rule candidate has 3+ anchors (including cross-artifact), verifier pass, and confidence >= 0.85, **Then** it may be labeled "likely rule" if support_strength >= medium.

---

### User Story 4 - Two-Pass Draft-and-Verify Generation (Priority: P2)

The system generates explanations and rules using a two-pass pattern: first a draft explanation or rule candidate, then a verifier pass that checks the draft against the cited source evidence. Outputs that fail the verifier are downgraded or rejected. The verifier does not fabricate; it validates that cited spans support the claim.

**Why this priority**: Two-pass generation reduces hallucination and over-confidence. It is a core mitigation for LLM trust issues and is required by the evidence contract.

**Independent Test**: Can be fully tested by injecting a draft with fabricated citations and verifying that the verifier rejects it, and by providing a draft with valid citations and verifying that the verifier passes it.

**Acceptance Scenarios**:

1. **Given** a draft explanation with citations, **When** the verifier runs, **Then** it checks that each cited span exists and supports the claim; if not, the output is downgraded or rejected.
2. **Given** a draft with citations that do not exist in the codebase, **When** the verifier runs, **Then** the output is rejected and no "likely rule" label is applied.
3. **Given** a draft with valid citations that support the claim, **When** the verifier runs, **Then** the output may receive review_status auto-passed if no contradictions are found.

---

### User Story 5 - Rejected and Low-Support Claim Visibility and Blocking (Priority: P2)

An application support analyst reviews semantic outputs and needs to see all claims—including rejected and low-support ones—for transparency and learning. Rejected and low-support claims remain visible but are blocked from migration-impacting actions by default. Any override requires a mandatory reviewer note (identity, reason code, justification).

**Why this priority**: Visibility prevents hidden blind spots; blocking prevents unsafe automation. The override workflow preserves auditability.

**Independent Test**: Can be fully tested by verifying that rejected claims appear in the UI with explicit labeling, that migration-impact actions are disabled for them, and that override requires the mandatory note fields.

**Acceptance Scenarios**:

1. **Given** a rejected or low-support claim, **When** displayed in the UI, **Then** it is visible with explicit rejected/hypothesis labeling.
2. **Given** a rejected or low-support claim, **When** the user attempts a migration-impacting action (e.g., include in migration scope), **Then** the action is blocked by default.
3. **Given** a user with override authority, **When** they override a blocked claim, **Then** they must provide reviewer identity, reason code, and free-text justification; the override is audit-logged.

---

### User Story 6 - False-Positive Rate Compliance (Priority: P2)

The system must meet maximum acceptable false-positive rates for "likely rule" labels: <= 1% for critical modules and <= 3% for non-critical modules. These rates are measured against a labeled benchmark (e.g., golden_rules.jsonl) and gate production readiness.

**Why this priority**: False positives erode trust and can lead to incorrect migration decisions. The tiered rates balance safety for critical logic with practical throughput elsewhere.

**Independent Test**: Can be fully tested by running the pipeline on a labeled benchmark, comparing "likely rule" outputs to ground truth, and verifying that false-positive rates meet the thresholds.

**Acceptance Scenarios**:

1. **Given** a labeled benchmark of critical modules, **When** the pipeline produces "likely rule" claims, **Then** the false-positive rate is <= 1%.
2. **Given** a labeled benchmark of non-critical modules, **When** the pipeline produces "likely rule" claims, **Then** the false-positive rate is <= 3%.

---

### User Story 7 - RAG-Style Conceptual Query with Citations (Priority: P3)

A modernization architect asks a natural-language question (e.g., "Where do we calculate late fees?") and receives a ranked answer with evidence-backed citations. Each answer includes source anchors and confidence. The system grounds retrieval on paragraph/section units plus surrounding data definitions and caller/callee context, using hybrid retrieval (lexical + embedding + graph-neighbor expansion).

**Why this priority**: Conceptual search accelerates discovery and is a key differentiator. Lower priority than core summarization and rule extraction because it builds on them.

**Independent Test**: Can be fully tested by running conceptual queries against CardDemo and verifying that answers include citations, that retrieval uses AST/graph context (not raw file dumps), and that p95 latency meets the target.

**Acceptance Scenarios**:

1. **Given** a conceptual query, **When** the system responds, **Then** the answer includes ranked results with evidence anchors (file, node/span IDs) and confidence scores.
2. **Given** a conceptual query, **When** the system retrieves context, **Then** retrieval uses paragraph/section + surrounding data definitions + caller/callee context, not raw long-file dumps.
3. **Given** a conceptual query, **When** the system responds, **Then** p95 response time is <= 9.0 seconds for RAG answers with citations.

---

### Edge Cases

- What happens when the AST or graph is incomplete (e.g., parse coverage < 90%)? The system MUST surface parser/analysis gaps as part of results, not hide them. Outputs MUST include uncertainty labels when evidence is incomplete.
- How does the system handle paragraphs with no clear business rule? The system MUST return "insufficient evidence" or "no rule identified" rather than fabricate a plausible rule.
- What happens when a cited span is in a copybook or another artifact? The system MUST support cross-artifact evidence anchors; critical modules require at least one cross-artifact anchor for "likely rule."
- How does the system handle contradictory evidence? The system MUST populate the contradictions field and label the claim as hypothesis or rejected; "likely rule" is never applied when contradictions exist.
- What happens when the verifier cannot access or resolve a cited span? The system MUST reject the claim and set review_status to rejected.
- How does the system handle very long paragraphs that exceed context limits? The system MUST chunk or summarize within retrieval units (paragraph/section + surrounding context) and not silently truncate without signaling.
- What happens when the same rule appears in multiple paragraphs? The system MAY produce multiple rule candidates; each MUST have its own evidence anchors and support assessment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST produce paragraph/section-level plain-English summaries with evidence anchors (file, node ID, span) linking to source.
- **FR-002**: System MUST extract candidate business rules in structured form with required fields: claim_id, claim_text, evidence, support_strength, contradictions, confidence_score, review_status.
- **FR-003**: System MUST ground explanations and rules on AST + graph context, not raw long-file dumps.
- **FR-004**: System MUST use a two-pass pattern: draft explanation/rule followed by verifier pass against cited evidence.
- **FR-005**: System MUST label outputs "likely rule" only when verifier passes, support_strength >= medium, and evidence thresholds are met.
- **FR-006**: System MUST label outputs "hypothesis" when support is low or contradictory.
- **FR-007**: System MUST apply baseline evidence thresholds: at least 2 independent anchors, verifier pass, confidence >= 0.70.
- **FR-008**: System MUST apply stricter thresholds for critical modules: at least 3 independent anchors (including one cross-artifact), verifier pass, confidence >= 0.85.
- **FR-009**: System MUST keep rejected and low-support claims visible with explicit labeling; they MUST be blocked from migration-impacting actions by default.
- **FR-010**: System MUST require reviewer identity, reason code, and justification note for any override of a blocked claim.
- **FR-011**: System MUST return "insufficient evidence" when evidence is incomplete rather than fabricate plausible answers.
- **FR-012**: System MUST use retrieval units of paragraph/section + surrounding data definitions + caller/callee context.
- **FR-013**: System MUST support hybrid retrieval (lexical + embedding + graph-neighbor expansion) for conceptual queries.
- **FR-014**: System MUST output explanations and rules in a structured schema (e.g., JSON) with required citation fields.
- **FR-015**: System MUST surface parser/analysis gaps and uncertainty in outputs when evidence is incomplete.
- **FR-016**: System MUST meet false-positive rate limits: <= 1% for critical modules, <= 3% for non-critical modules, measured against a labeled benchmark.

### Key Entities

- **Summary**: A plain-English explanation of a paragraph or section. Key attributes: text, evidence anchors (file, node ID, span), confidence, review_status.
- **Rule Candidate**: A structured business rule extraction. Key attributes: claim_id, claim_text, evidence (source anchors with node/span IDs), support_strength (high/medium/low), contradictions, confidence_score (0–1), review_status (auto-passed/needs-human/rejected).
- **Evidence Anchor**: A reference to source code. Key attributes: file path, node ID, span (start/end line/column).
- **Verifier Result**: Outcome of the verifier pass. Key attributes: pass/fail, contradiction flags, downgrade reason.
- **Retrieval Unit**: The context passed to the LLM. Key attributes: paragraph/section content, surrounding data definitions, caller/callee context from the graph.
- **Critical Module**: A module designated as financial/compliance/safety-critical, subject to stricter evidence thresholds.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Rule extraction precision >= 0.8 on a labeled benchmark (correct likely-rule claims / total likely-rule claims).
- **SC-002**: RAG answer with citations p95 latency <= 9.0 seconds.
- **SC-003**: False-positive rate for "likely rule" labels <= 1% on critical modules in the benchmark.
- **SC-004**: False-positive rate for "likely rule" labels <= 3% on non-critical modules in the benchmark.
- **SC-005**: Every summary and rule output includes at least one evidence anchor with resolvable source span.
- **SC-006**: Pipeline produces verifier-passed summaries for >= 90% of paragraphs in CardDemo (28 files, 19K LOC) where parse coverage permits.
- **SC-007**: Rule extraction on taxe-fonciere (6 files, 2.3K LOC) produces outputs that can be manually verified against source; no fabricated citations.
- **SC-008**: Rejected and low-support claims are visible in outputs; override workflow captures mandatory reviewer note fields.
