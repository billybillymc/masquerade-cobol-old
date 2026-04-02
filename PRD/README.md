# Masquerade PRD Index

> **Note**: These are historical design documents from Masquerade's development. They capture the reasoning behind architectural decisions and are preserved for contributor context. For current documentation, see the [README](../README.md) and [docs/](../docs/).

This PRD is split into focused documents so decisions can evolve independently.

## Product Direction

Masquerade delivers value in two linked layers:

1. **Exploration-first system of record**
   - RAG chatbot + graph exploration for fast understanding, impact, and ROI visibility
   - Evidence-backed answers with uncertainty labels
2. **Selective reimplementation system**
   - Candidate modern code generation for high-ROI modules
   - Human-in-the-loop (HITL) validation gates before any "equivalent" claim

This avoids forcing migration before trust exists. Exploration builds trust and identifies migration-ready modules.

## How We Encourage Exploration While Enabling Reimplementation

- Default UX is exploration workflows (question answering, lineage, blast-radius, ROI scoring).
- Every module gets an **Equivalence Readiness Score** and **ROI Score**:
  - Readiness = parser coverage + rule confidence + testability + dependency isolation
  - ROI = infra cost pressure + change frequency + defect burden + business criticality
- Reimplementation is available only when readiness and ROI pass configurable thresholds.

## Validation Philosophy

- No module is marked "equivalent" without differential tests and human approval.
- LLM outputs are hypotheses until linked to source evidence and reviewer sign-off.
- "Unknown" is acceptable output; silent certainty is not.

## Document Map

- `locked-decisions.md` (single source of truth snapshot)
- `decision-workshop-questions.md` (remaining unresolved decisions only)
- `product-wedge.md`
- `scope-and-language.md`
- `canonical-ir-choice.md`
- `numeric-semantics-contract.md`
- `evidence-contract.md`
- `eval-dataset-strategy.md`
- `parser-failure-policy.md`
- `security-model.md`
- `incremental-ingest.md`
- `hitl-validation.md`
- `trust-and-correctness.md`
- `infrastructure-and-deployment.md`
- `commercial-framing.md`
