<!-- Sync Impact Report
  Version change: 0.0.0 → 1.0.0
  Modified principles: N/A (initial creation)
  Added sections: All (Core Principles I–VII, Security & Governance, Development Workflow, Governance)
  Removed sections: None
  Templates requiring updates: ✅ constitution written
  Follow-up TODOs: None
-->

# Masquerade COBOL Constitution

## Core Principles

### I. Evidence-Grounded Analysis (NON-NEGOTIABLE)

Every semantic claim about COBOL behavior MUST include source references (file, symbol, span). LLM outputs are hypotheses until verified against code evidence. Outputs missing evidence anchors MUST be rejected. When evidence is insufficient, the system MUST state "insufficient evidence" rather than fabricate plausible answers.

### II. Test-First Development (NON-NEGOTIABLE)

TDD is mandatory for all implementation work. Red-Green-Refactor cycle strictly enforced:
- Write a failing test that captures intended behavior
- Write minimum implementation to pass
- Refactor while keeping tests green

Characterization tests MUST be written before modifying any existing behavior. Bug fixes MUST be preceded by a reproducing test.

### III. Verified Modernization

No modernization claim without differential execution evidence. Equivalence target is behavioral under representative data, not syntactic similarity. Edge-case fixtures for numeric semantics (COMP-3, rounding, sign handling), date/locale, and record I/O MUST be included. Diff pass rate and uncovered behaviors MUST be reported before confidence scores.

### IV. Graceful Degradation

Parsers and analysis pipelines MUST produce partial results when full coverage is not achievable. Unknown constructs, unresolvable calls, and ambiguous data flows are first-class outputs — surfaced as "unknown edges" rather than silently dropped. Parse coverage is tracked as a KPI per codebase and module.

### V. Structured Outputs with Provenance

All LLM-derived outputs use JSON schema with required fields: `claim`, `evidence`, `confidence`, `uncertainty`, `validation_status`. Citations reference source spans and graph node IDs. Two-pass generation pattern: draft explanation followed by verifier pass against citations.

### VI. Resumable and Idempotent Pipelines

Long-running jobs (ingest, analysis, embedding) MUST be resumable and idempotent. Content-addressed caching for chunks and embeddings is mandatory. Stage-level metrics and retry-safe checkpoints required for all pipeline workers.

### VII. Single Dialect Focus

MVP targets IBM Enterprise COBOL exclusively. Unsupported constructs MUST be documented upfront. Parser error taxonomy distinguishes recoverable from blocking failures. Dialect assumptions MUST be explicit in parser code.

## Security & Governance

Source code and sampled data may be highly sensitive. Role-based access, audit logs, and artifact lineage are required. PII redaction in prompts and stored traces where possible. Policy toggles support "no external model calls" mode. Retention windows defined for embeddings, prompts, and completions. Per-tenant isolation enforced.

## Development Workflow

- Spec-driven development: specifications define intent before implementation begins
- Feature branches follow `###-feature-name` naming convention
- Every feature goes through: specify → clarify → plan → tasks → analyze → implement
- Integration tests required for: service contracts, schema changes, inter-service communication
- Observability: distributed traces and per-stage failure dashboards
- SLIs tracked: ingest success rate, parse coverage, analysis latency, query latency

## Governance

This constitution supersedes all other development practices for this project. Amendments require:
1. Documentation of the proposed change and rationale
2. Impact assessment on existing specs and implementations
3. Version increment following semantic versioning (MAJOR for principle changes, MINOR for additions, PATCH for clarifications)

All code reviews MUST verify compliance with these principles. Complexity MUST be justified against the Simplicity preference (YAGNI).

**Version**: 1.0.0 | **Ratified**: 2026-03-13 | **Last Amended**: 2026-03-13
