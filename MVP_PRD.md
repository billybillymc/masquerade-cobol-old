# Masquerade COBOL - MVP Product Requirements Document

## 1) Product Summary

Masquerade COBOL is a codebase intelligence platform for legacy COBOL systems. The MVP focuses on making large COBOL systems understandable and safer to change by combining static analysis, dependency graphing, and LLM-assisted semantic interpretation.

The MVP is not a full migration engine. It is a trust-building system that answers:
- What does this COBOL system do?
- Where is a business rule implemented?
- If we change X, what breaks?
- Can we explain and validate candidate modernization outputs?

## 2) Problem Statement

Target users (banks, insurers, government IT teams) face:
- Multi-million line COBOL estates with no reliable docs/tests
- Critical business logic split across COBOL, copybooks, JCL, CICS, DB2, VSAM, flat files
- High operational risk from small changes
- Modernization pressure with low confidence in behavioral equivalence

The core pain is not "translate one file." It is "understand an entire system well enough to change it safely."

## 3) MVP Goals and Non-Goals

### Goals
- Parse and model one primary COBOL dialect end-to-end (IBM Enterprise COBOL target)
- Resolve copybooks and extract cross-program dependencies
- Build an explorable system graph (programs, copybooks, files, tables, jobs)
- Produce paragraph/section-level explanations and inferred business rules
- Provide field-level lineage tracing for a constrained scope
- Offer impact analysis for copybook fields and selected program changes
- Prototype "verified modernization" for a narrow module subset using test-based diffing

### Non-Goals (MVP)
- Full multi-dialect support (Micro Focus/ACUCOBOL parity)
- Full semantic equivalence proofs for arbitrary programs
- Full CICS transaction emulation
- Fully automated production code cutover

## 4) Users and Core Jobs-to-be-Done

- **Modernization Architect**: "Map the system before planning migration waves."
- **Senior COBOL Engineer**: "Find where a rule is implemented and what depends on it."
- **Risk/Controls Stakeholder**: "Get evidence that generated code behaves like legacy logic."
- **Application Support Analyst**: "Trace why an output field changed."

## 5) Functional Scope (MVP)

1. **Ingestion and Parsing**
   - COBOL source ingestion
   - Copybook resolution
   - Optional/partial JCL extraction for batch flow links
   - Partial executable CICS harness support for selected transaction classes
2. **Graph Construction**
   - Program-call graph
   - Data dependency links (copybook fields, file/table touches)
3. **Semantic Layer**
   - Paragraph/section summaries
   - Candidate rule extraction in structured form
4. **Exploration UI**
   - Dependency graph browsing
   - Code + explanation side-by-side
   - Conceptual search ("where do we calculate late fees?")
5. **Impact and Lineage**
   - "If this field changes, show blast radius"
   - Trace field transforms through selected pipeline paths
6. **Modernization Pilot**
   - Generate modern-language candidate for scoped module
   - Auto-generate test vectors
   - Run legacy vs generated implementations and diff outputs

## 6) System Architecture (MVP)

### 6.1 High-Level Components

- **Parser Service**
  - COBOL parser integration/adaptation
  - Copybook resolver with include path management
  - Symbol table and AST extraction
- **Static Analysis Engine**
  - Control-flow and call-graph builder
  - Data-flow extraction (field reads/writes/moves)
- **Graph Store**
  - Property graph (e.g., Neo4j) or relational + graph index hybrid
  - Versioned snapshots per codebase ingest
- **Semantic Pipeline**
  - Chunking + retrieval over AST-linked source units
  - LLM inference for explanations/rules/lineage hints
  - Confidence scoring and provenance tracking
- **Execution/Diff Harness**
  - Runs COBOL baseline (or captured output traces)
  - Runs generated modern code
  - Produces deterministic result comparisons
- **API + UI**
  - Query APIs for graph/search/impact/lineage
  - Web UI for exploration and review workflows

### 6.2 Data Model Essentials

Primary entities:
- Program, Paragraph, Section
- Copybook, Field
- File (VSAM/flat), Table (DB2), JCL Job/Step
- RuleCandidate, Explanation, TraceRun, DiffResult

Key relationships:
- `CALLS`, `PERFORMS`, `USES_COPYBOOK`, `READS_FIELD`, `WRITES_FIELD`, `FEEDS`, `SCHEDULED_BY`

## 7) Technical Challenges You Will Run Into

### 7.1 Parsing and Dialect Drift

What you will hit:
- COBOL syntax/semantics differ by dialect and compiler options
- Copybook expansion creates hidden complexity (redefines, OCCURS DEPENDING ON, packed decimals)
- Preprocessors and site-specific conventions break generic parsers

What to keep in mind:
- Constrain MVP to one dialect and document unsupported constructs up front
- Keep parse output lossless enough to map generated insights back to original lines
- Build parser error taxonomy: recoverable vs blocking; do not silently drop unknown constructs

Mitigation:
- Extend an existing parser, do not build from scratch
- Implement "graceful degradation": partial graph even when parse coverage is incomplete
- Track parse coverage as a KPI by codebase/module

### 7.2 Hidden Control and Data Flow

What you will hit:
- Dynamic calls, paragraph PERFORM patterns, GOTO-heavy logic
- Data movement through shared copybooks and implicit record layouts
- Batch chains through JCL where true flow is orchestration-level

What to keep in mind:
- You need both intra-program and inter-program analysis
- "Unknown edges" are first-class outputs, not errors to hide
- Lineage must include confidence and ambiguity labels

Mitigation:
- Combine static edges + probabilistic edges
- Annotate lineage with evidence pointers (statements, copybook fields, job steps)
- Provide analyst override/confirmation workflow in UI

### 7.3 LLM Hallucination and Over-Confidence

What you will hit:
- Plausible but incorrect business-rule explanations
- Over-generalized summaries missing edge-case branches
- Inconsistent terminology across runs/prompts

What to keep in mind:
- LLM output is a hypothesis layer, not source of truth
- Every claim must map to source spans and graph evidence
- Determinism matters for enterprise trust

Mitigation:
- Structured outputs with required evidence anchors
- Two-pass generation: draft explanation -> verifier pass against citations
- Block unsupported claims in UI (show "insufficient evidence")
- Track precision/recall on rule extraction against hand-labeled benchmark sets

### 7.4 Verified Modernization Is Harder Than Translation

What you will hit:
- Numeric semantics mismatch (COMP-3, rounding, sign handling)
- Date and locale edge cases
- Record I/O and sort semantics mismatch with modern runtime

What to keep in mind:
- Equivalence target should be behavior under representative data, not syntactic similarity
- You need test generation that covers branch boundaries and data-shape extremes
- Diff explainability is as important as pass/fail

Mitigation:
- Start with pure transformation modules (minimal I/O, constrained side effects)
- Build a golden test corpus from production-like traces where possible
- Normalize output formats before diffing to avoid false mismatches

### 7.5 Infra and Operational Realities

What you will hit:
- Large ingest jobs (millions of LOC) stress memory and indexing
- Expensive LLM token consumption for full-estate analysis
- Sensitive code/data constraints (on-prem, audit, retention)

What to keep in mind:
- Pipeline must be resumable/idempotent
- Caching and incremental indexing are mandatory, not optimization
- Security and provenance need to be native features

Mitigation:
- Event-driven pipeline with durable job states
- Content-addressed chunk cache and embedding cache
- Strict data governance: redaction, encryption, access logs, per-tenant isolation

## 8) Model Steering Strategy (Critical)

### 8.1 Prompting Principles

- Ground on AST + graph context, not raw long-file dumps
- Require JSON schema outputs for explanations/rules
- Force citation fields that reference source spans and node IDs
- Use system prompts that explicitly forbid unsupported assertions

### 8.2 Retrieval Strategy

- Retrieval unit: paragraph/section + surrounding data definitions + caller/callee context
- Hybrid retrieval: lexical + embedding + graph-neighbor expansion
- Limit context window to high-signal slices; add provenance headers

### 8.3 Multi-Step Inference Pattern

1. **Extract** candidate facts from code chunks
2. **Assemble** cross-chunk rule candidates
3. **Verify** each rule against source evidence
4. **Score** confidence and expose uncertainty reasons

### 8.4 Guardrails and Eval

- Define task-specific eval sets:
  - Explanation correctness
  - Rule extraction precision
  - Lineage path fidelity
  - Modernization diff pass rate
- Regression-test prompts and model versions
- Reject model updates that degrade benchmark thresholds

## 9) Infrastructure Requirements

### Core Services
- Parsing workers (CPU-bound)
- Analysis workers (CPU/memory-bound)
- LLM orchestration service
- Graph DB + metadata DB
- Search index (for concept + symbol search)
- Object storage for artifacts (AST, traces, diffs)

### Deployment Considerations
- Start with single-tenant deployment model for easier compliance
- External model mode first to leverage frontier-model capability
- Route sensitive/proprietary workloads to local/private mode by policy default
- Include a first-class mode-switch module to switch between external and local inference safely
- Support air-gapped or VPC-isolated inference path where needed
- Introduce queue-based orchestration and backpressure controls

### Reliability/SRE Basics
- Job retries with deduplication keys
- Checkpointed pipelines for long-running ingests
- SLIs: ingest success rate, parse coverage, analysis latency, query latency
- Observability: distributed traces and per-stage failure dashboards

## 10) Security and Governance

- Source code and sampled data may be highly sensitive
- Enforce role-based access, audit logs, and artifact lineage
- Redact PII in prompts and stored traces where possible
- Define retention windows for embeddings, prompts, completions
- Support policy toggles: "no external model calls" mode

## 11) Delivery Plan (6 Weeks)

- **Week 1**: COBOL parser integration + copybook resolution on CardDemo
- **Week 2**: Dependency graph extraction + initial UI graph view
- **Week 3**: LLM explanation/rule pipeline + evidence-linked outputs
- **Week 4**: Field lineage and conceptual search + stress test on larger corpus
- **Week 5**: Modernization pilot module + differential test harness
- **Week 6**: Impact analysis UX, hardening, benchmark report, demo narrative

## 12) Success Metrics (MVP)

- Parse coverage >= 90% on target dialect corpus
- Parse coverage >= 95% for migration-candidate modules
- Graph extraction complete for >= 90% of parsed programs
- Rule extraction precision >= 0.8 on labeled benchmark
- Impact accuracy as primary proof metric (defined below)
- Lineage query response p95 <= 4.0s
- Impact query response p95 <= 6.0s
- RAG answer with citations p95 <= 9.0s
- Modernization pilot diff pass >= 95% on scoped module test suite
- Validated modernization percentage as secondary proof metric (defined below)
- End-user task success: "locate and explain rule" within 10 minutes

### 12.1 Metric Definitions (Locked)

- **Impact accuracy (primary commercial proof metric)**  
  `correct impact predictions / total reviewed impact predictions`  
  where each reviewed prediction is labeled by human reviewers against expected blast-radius truth.

- **Validated modernization percentage (secondary commercial proof metric)**  
  `modules marked migration-ready with passing differential validation / total modules submitted for modernization validation`

- **Rule precision**  
  `correct likely-rule claims / total likely-rule claims`

### 12.2 Readiness Scoring Contract (Locked)

- **Readiness score components** (normalized weighted composite):
  - Parser coverage
  - Evidence strength and verifier outcomes
  - Differential testability and test coverage
  - Dependency isolation and unresolved unknown-edge burden

- **Migration-ready gating**:
  - Readiness threshold satisfied
  - High-assurance full recompute completed
  - Strict numeric emulation requirements satisfied
  - Required HITL approvers sign off
  - Threshold policy profile is standard-or-stricter

- **Sandbox policy**:
  - Bounded-equivalence experiments are allowed only in explicitly marked sandbox mode
  - Sandbox outputs are non-actionable and cannot be labeled `migration-ready`

- **Ownership model**:
  - Scoring implementation owner: platform engineering
  - Threshold policy owner: risk/controls governance
  - Final approval owner per module: modernization engineer + domain SME + risk/controls owner

## 13) MVP vs Post-MVP Boundaries (Locked)

| Topic | MVP | Post-MVP / Final Direction |
|---|---|---|
| Inference rollout | External mode first + local routing for sensitive/proprietary workloads | Policy-driven dual-mode operations with hardened governance |
| CICS support | Partial executable harness support | Full executable CICS support |
| Canonical IR | Strategy A (typed AST + graph overlay) | Strategy B (unified schema/DSL) |
| Threshold model | Global threshold policy | Customer policy profiles with guardrails |
| Performance targets | Reliability-first p95 targets (4s/6s/9s) | Stretch p95 targets (2s/3s/5s) |

## 14) Recommended Skills and Cursor Rules

### 14.1 Skills to Use Immediately

- `python-performance-optimization`
  - Use for analysis pipeline profiling, parser throughput tuning, and memory hotspots
- `find-skills`
  - Use to discover installable skills for graph tooling, eval harnesses, and DevOps automation
- `create-rule`
  - Use to codify project conventions and reduce agent drift across sessions

Optional by stack direction:
- `vercel-react-best-practices` (if UI is React/Next)
- `tailwind-design-system` (if UI systemization becomes a bottleneck)

### 14.2 Rule Suggestions for This Project

Create these in `.cursor/rules/`:

1. `legacy-analysis-safety.mdc` (`alwaysApply: true`)
   - Never present LLM output as fact without source citations
   - Always include uncertainty labels for inferred behavior

2. `cobol-parsing-constraints.mdc` (`globs: **/*.py`, `**/*.java`, `**/*.ts`)
   - Keep dialect assumptions explicit in parser code/comments
   - Preserve source span mappings through all transforms

3. `llm-evidence-contract.mdc` (`alwaysApply: true`)
   - Require structured outputs with node IDs and span references
   - Reject outputs missing evidence anchors

4. `modernization-validation.mdc` (`globs: **/*test*.*`, `**/harness/**`)
   - No modernization claim without differential test results
   - Include edge-case fixtures for numeric/date semantics

5. `infra-job-idempotency.mdc` (`globs: **/workers/**`, `**/pipeline/**`)
   - Long-running jobs must be resumable and idempotent
   - Emit stage-level metrics and retry-safe checkpoints

## 15) Demo Strategy

Primary flow:
- Load manageable "clean demo" corpus (CardDemo) for live walkthrough
- Show one business-question search -> explanation -> lineage -> impact path
- Run modernization pilot for one module and display diff confidence report

Credibility anchor:
- Run offline stress analysis on large corpus (CNAF-scale) and present coverage/latency metrics

## 16) Open Risks and Decisions

- Parser choice and extension strategy (final selection pending benchmark)
- Graph store selection (Neo4j vs relational+index hybrid)
- Execution environment for COBOL baseline comparisons
- On-prem inference path for compliance-sensitive users

These decisions should be finalized before Week 2 architecture lock.
