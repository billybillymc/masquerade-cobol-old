# Feature Specification: Field Lineage + Conceptual Search

**Feature Branch**: `004-lineage-search`  
**Created**: 2026-03-13  
**Status**: Draft  
**Input**: Field lineage tracing and conceptual search for IBM Enterprise COBOL codebases (Week 4 of 6-week MVP)

## Dependencies

- **001-cobol-parser**: Typed AST, symbol table, copybook resolution
- **002-dependency-graph**: Program-call graph, data dependency links (READS_FIELD, WRITES_FIELD, USES_COPYBOOK)
- **003-semantic-pipeline**: Paragraph/section summaries, rule extraction, evidence-linked outputs

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conceptual Search by Business Concept (Priority: P1)

A modernization architect asks a natural-language question such as "Where do we calculate late fees?" The system returns ranked answers grounded in code evidence, with each answer including source spans, confidence scores, and provenance. The architect can locate business rules by meaning, not by code symbol names.

**Why this priority**: This is the lead-in to the 10-minute wow demo and the primary discovery wedge. Users do not know COBOL field names; they know business concepts. Without conceptual search, the platform cannot deliver "locate and explain rule within 10 minutes."

**Independent Test**: Can be fully tested by running conceptual search against CardDemo (or taxe-fonciere) with queries such as "where do we calculate late fees?" and verifying ranked results with evidence spans, confidence scores, and provenance headers.

**Acceptance Scenarios**:

1. **Given** a codebase with parsed programs and semantic pipeline outputs, **When** the user asks "Where do we calculate late fees?", **Then** the system returns ranked answers with at least one result that includes evidence spans (file, line, symbol) and a confidence score.
2. **Given** a conceptual search query, **When** results are returned, **Then** each result includes provenance headers indicating the source of the match (e.g., paragraph, section, copybook).
3. **Given** a conceptual search query, **When** results are returned, **Then** results meet the evidence threshold: baseline modules require at least 2 anchors and confidence >= 0.70; critical modules require at least 3 anchors and confidence >= 0.85.
4. **Given** a query that yields no high-confidence matches, **When** results are returned, **Then** the system surfaces "insufficient evidence" or low-confidence indicators rather than fabricating answers.
5. **Given** a conceptual search query, **When** the response is delivered, **Then** the p95 latency for RAG answer with citations is <= 9.0 seconds.

---

### User Story 2 - Trace Field Lineage Through Pipeline Paths (Priority: P1)

A senior COBOL engineer selects a field (e.g., a copybook field or output amount) and requests its lineage. The system traces how that field flows through selected pipeline paths—from input sources through transforms to outputs—with each step anchored to source spans. The engineer can click through the lineage from input to output and see confidence and ambiguity labels at each step.

**Why this priority**: Field lineage is the core of "trace why an output field changed" and enables the demo flow "click through lineage of fee amount from input to output." Without it, impact analysis and rule explanation lack traceability.

**Independent Test**: Can be fully tested by selecting a known field in CardDemo (e.g., a fee or amount field) and verifying that lineage traces from input to output with evidence at each step, confidence scores, and explicit ambiguity labels where resolution is uncertain.

**Acceptance Scenarios**:

1. **Given** a selected field (copybook or program data item), **When** the user requests lineage, **Then** the system returns a trace showing how the field flows through pipeline paths with each step linked to source spans (file, line, statement).
2. **Given** a lineage trace, **When** the user inspects it, **Then** each step includes a confidence score and, where applicable, an ambiguity label (e.g., "inferred from MOVE", "unresolved PERFORM target").
3. **Given** a lineage trace, **When** the trace includes uncertain or unresolved steps, **Then** those steps are surfaced as first-class outputs with explicit "unknown" or "uncertain" labels—not hidden or dropped.
4. **Given** a lineage query, **When** the response is delivered, **Then** the p95 latency for lineage query is <= 4.0 seconds.
5. **Given** a lineage trace spanning multiple programs or copybooks, **When** the trace is displayed, **Then** provenance headers indicate which program, paragraph, or copybook each step belongs to.

---

### User Story 3 - Blast Radius: "If This Field Changes, What Breaks?" (Priority: P1)

A risk/controls stakeholder selects a copybook field (or program data item) and asks for impact analysis: "If this field changes, what breaks?" The system returns the blast radius—programs, paragraphs, files, and downstream consumers that depend on that field—with evidence anchors and confidence. The stakeholder can assess change risk before making modifications.

**Why this priority**: This is the first-buyer wedge per product strategy. "Faster impact assessments" is the primary 90-day KPI. Blast radius answers the most urgent operational question: "What will break if we change X?"

**Independent Test**: Can be fully tested by selecting a copybook field in CardDemo that is used by multiple programs and verifying that the blast radius includes all dependent programs/paragraphs with evidence, and that unknown dependencies are surfaced explicitly.

**Acceptance Scenarios**:

1. **Given** a selected copybook field (or program data item), **When** the user requests impact analysis, **Then** the system returns a blast radius listing programs, paragraphs, and downstream consumers that depend on that field.
2. **Given** an impact analysis result, **When** the user inspects it, **Then** each affected item includes evidence anchors (source file, line, span or node ID).
3. **Given** an impact analysis result, **When** there are unresolved or uncertain dependencies, **Then** those are surfaced as first-class outputs with explicit "unknown" labels.
4. **Given** an impact query, **When** the response is delivered, **Then** the p95 latency for impact query is <= 6.0 seconds.
5. **Given** a blast radius result, **When** the user reviews it, **Then** results meet evidence thresholds: baseline modules 2 anchors + confidence >= 0.70; critical modules 3 anchors + confidence >= 0.85.

---

### User Story 4 - Code + Explanation Side-by-Side (Priority: P2)

An application support analyst views a code region (paragraph, section, or field definition) and sees an explanation of what it does, displayed side-by-side with the source code. The explanation is grounded in semantic pipeline outputs and includes evidence citations. The analyst can quickly understand unfamiliar code without switching contexts.

**Why this priority**: Side-by-side presentation reduces cognitive load and supports the "locate and explain rule" task. It builds on semantic pipeline outputs and makes them actionable in the exploration UI.

**Independent Test**: Can be fully tested by navigating to a paragraph or section in CardDemo and verifying that an explanation appears alongside the code with citations to source spans.

**Acceptance Scenarios**:

1. **Given** a selected code region (paragraph, section, or field), **When** the user views it in the exploration UI, **Then** an explanation is displayed side-by-side with the source code.
2. **Given** an explanation, **When** the user inspects it, **Then** it includes evidence citations (source spans, node IDs) that link to the code.
3. **Given** a code region with low-confidence or insufficient evidence, **When** the explanation is displayed, **Then** it is labeled as hypothesis or "insufficient evidence" rather than presented as fact.
4. **Given** a code region, **When** the explanation is displayed, **Then** it is limited to high-signal slices with provenance headers to avoid context overload.

---

### User Story 5 - Hybrid Retrieval Over Graph and Semantic Context (Priority: P2)

A pipeline integrator needs conceptual search and lineage to use a hybrid retrieval strategy: lexical matching, embedding similarity, and graph-neighbor expansion. Retrieval units are paragraph/section plus surrounding data definitions and caller/callee context. Context is limited to high-signal slices with provenance headers to stay within context window limits.

**Why this priority**: Per PRD Section 8.2, hybrid retrieval is the locked retrieval strategy. It ensures conceptual search and lineage are grounded in both semantic similarity and structural graph relationships. This is a capability requirement that enables Stories 1–3.

**Independent Test**: Can be fully tested by verifying that conceptual search and lineage queries return results that combine lexical, embedding, and graph-derived context, and that each result includes provenance headers.

**Acceptance Scenarios**:

1. **Given** a conceptual search or lineage query, **When** retrieval runs, **Then** the system uses a combination of lexical matching, embedding similarity, and graph-neighbor expansion to gather context.
2. **Given** retrieval results, **When** they are assembled for inference, **Then** each chunk includes a provenance header indicating its source (program, paragraph, copybook, etc.).
3. **Given** retrieval results, **When** they are assembled, **Then** the total context is limited to high-signal slices to fit within context window constraints; low-signal or redundant context is excluded.
4. **Given** a query that touches multiple programs or copybooks, **When** retrieval runs, **Then** graph-neighbor expansion includes relevant caller/callee and data-definition context.

---

### User Story 6 - Stress Test on Larger Corpus (Priority: P3)

A modernization architect runs lineage and conceptual search against a larger corpus (beyond CardDemo and taxe-fonciere) to validate performance and scalability. The system completes queries within latency targets and maintains evidence quality. This validates the feature for production-scale codebases.

**Why this priority**: Week 4 delivery plan includes "stress test on larger corpus." This ensures the feature meets latency and quality targets at scale before Week 5–6 hardening.

**Independent Test**: Can be fully tested by running lineage and conceptual search against a corpus of ~500K LOC (per MVP benchmark scale) and verifying p95 latency and evidence quality.

**Acceptance Scenarios**:

1. **Given** a codebase of ~500K LOC (or larger), **When** lineage and conceptual search queries are run, **Then** lineage p95 <= 4.0s, impact p95 <= 6.0s, RAG answer p95 <= 9.0s.
2. **Given** a larger corpus, **When** conceptual search returns results, **Then** evidence thresholds and provenance are maintained; no degradation in evidence quality.
3. **Given** a larger corpus, **When** lineage traces span many programs, **Then** unknown edges and ambiguous steps remain surfaced as first-class outputs.

---

### Edge Cases

- **What happens when a field has no lineage (e.g., input-only, never written)?** The system MUST return a trace indicating that the field is an input/source with no downstream transforms, or a clear "no downstream lineage found" result—not an empty or error state.
- **What happens when lineage crosses unresolved or unknown edges (e.g., dynamic CALL, missing copybook)?** The system MUST include those steps in the lineage with explicit "unknown" or "unresolved" labels and preserve the target identifier for manual review.
- **What happens when conceptual search returns no matches?** The system MUST return "no results" or "insufficient evidence" rather than fabricating an answer. Low-confidence hypotheses MAY be shown with explicit uncertainty labels.
- **What happens when retrieval returns too many chunks for the context window?** The system MUST prioritize high-signal slices (e.g., by relevance score, graph centrality) and truncate or summarize lower-priority context; provenance headers MUST be preserved.
- **What happens when a user asks a conceptual question that spans multiple business domains?** The system MUST return ranked results that may span multiple programs/paragraphs; each result MUST have its own evidence and confidence.
- **What happens when blast radius includes programs that failed to parse?** The system MUST include those programs in the blast radius (if reachable via graph edges) and mark them as "parse failed" or "unresolved"—not omit them.
- **What happens when evidence thresholds are not met for a result?** The system MUST downgrade the result (e.g., show as "hypothesis" or "needs review") and block it from migration-impacting actions per evidence contract; override requires reviewer note.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support conceptual search: natural-language queries that return ranked answers grounded in code evidence with source spans, confidence scores, and provenance headers.
- **FR-002**: System MUST support field lineage: tracing a selected field through pipeline paths from input to output, with each step anchored to source spans.
- **FR-003**: System MUST support blast-radius impact analysis: given a field, return programs, paragraphs, and downstream consumers that depend on it, with evidence anchors.
- **FR-004**: System MUST include confidence scores and ambiguity labels in all lineage and impact outputs; lineage MUST NOT omit uncertainty.
- **FR-005**: System MUST surface unknown or unresolved edges as first-class outputs with explicit labels; unknown edges MUST NOT be hidden or dropped.
- **FR-006**: System MUST enforce evidence thresholds: baseline modules 2 anchors + confidence >= 0.70; critical modules 3 anchors + confidence >= 0.85.
- **FR-007**: System MUST use hybrid retrieval (lexical + embedding + graph-neighbor expansion) for conceptual search and lineage context gathering.
- **FR-008**: System MUST limit retrieval context to high-signal slices with provenance headers; low-signal or redundant context MUST be excluded or summarized.
- **FR-009**: System MUST display code and explanation side-by-side in the exploration UI, with explanations grounded in semantic pipeline outputs and evidence citations.
- **FR-010**: System MUST label low-confidence or insufficient-evidence results as "hypothesis" or "insufficient evidence" rather than presenting them as fact.
- **FR-011**: System MUST meet latency targets: lineage query p95 <= 4.0s, impact query p95 <= 6.0s, RAG answer with citations p95 <= 9.0s.
- **FR-012**: System MUST support retrieval units of paragraph/section plus surrounding data definitions and caller/callee context.
- **FR-013**: System MUST block unsupported or low-evidence claims from migration-impacting actions; override requires reviewer identity, reason code, and justification note per evidence contract.

### Key Entities

- **LineageTrace**: A path showing how a field flows through pipeline steps. Key attributes: source field, steps (each with source span, confidence, ambiguity label), target field(s), unknown steps (first-class).
- **BlastRadius**: The set of programs, paragraphs, and consumers affected if a field changes. Key attributes: source field, affected items (each with evidence anchors, confidence), unknown dependencies (first-class).
- **ConceptualSearchResult**: A ranked answer to a natural-language query. Key attributes: query, ranked results (each with evidence spans, confidence, provenance headers), evidence threshold status.
- **RetrievalChunk**: A unit of context used for search/lineage. Key attributes: content, provenance header (program, paragraph, copybook), relevance score, source span.
- **EvidenceAnchor**: A reference to source code. Key attributes: file, line, span or node ID, anchor type (direct extraction vs. inferred).
- **UnknownEdge**: A first-class representation of an unresolved dependency or lineage step. Key attributes: edge type, source, target identifier (as known), reason (missing program, dynamic call, etc.).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Lineage query response p95 <= 4.0 seconds on CardDemo and taxe-fonciere.
- **SC-002**: Impact query response p95 <= 6.0 seconds on CardDemo and taxe-fonciere.
- **SC-003**: RAG answer with citations p95 <= 9.0 seconds on CardDemo and taxe-fonciere.
- **SC-004**: End-user task success: a user can "locate and explain rule" (e.g., "where do we calculate late fees?") within 10 minutes on CardDemo.
- **SC-005**: All lineage and impact outputs include confidence and ambiguity labels; zero unknown edges are hidden or dropped.
- **SC-006**: Conceptual search returns ranked results with evidence spans and provenance headers for queries on CardDemo and taxe-fonciere.
- **SC-007**: Blast-radius results include evidence anchors for each affected item; unresolved dependencies are surfaced with explicit labels.
- **SC-008**: Stress test on larger corpus (~500K LOC): lineage p95 <= 4.0s, impact p95 <= 6.0s, RAG p95 <= 9.0s with no degradation in evidence quality.
- **SC-009**: Results meet evidence thresholds (2 anchors + confidence >= 0.70 baseline; 3 anchors + confidence >= 0.85 critical) where applicable.
- **SC-010**: 10-minute wow demo flow is achievable: ask "Where do we calculate late fees?" → show ranked answer with evidence → click through lineage of fee amount → change simulation "If copybook field X changes, what breaks?" → display results.
