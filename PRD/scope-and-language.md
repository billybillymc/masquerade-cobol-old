# Scope and Language

## Confirmed Direction

- Core parser/IR engine: **Java or Kotlin**
- AI pipeline/orchestration: **Python**
- UI/API layer: **TypeScript (React/Next.js)**
- CICS support path: **partial executable support in MVP; full executable support in final version**
- Generated code visibility in MVP UI: **shown only for modules above readiness threshold**

Decision tradeoff summary:
- We gain practical validation depth for transaction-heavy workflows without overloading MVP scope.
- We reduce risk of "trace-only" blind spots in migration readiness assessments.
- We accept additional harness complexity and integration work in early releases.
- We preserve a clear end-state: full executable CICS parity for final/high-assurance deployments.
- We reduce premature trust in low-confidence generations at the cost of reduced early transparency on low-readiness modules.

## Input Support (MVP)

Priority order:
1. IBM Enterprise COBOL source
2. Copybooks
3. JCL linkage and job metadata
4. Embedded DB2 SQL extraction (`EXEC SQL`)
5. CICS references with partial executable harness support

## Output Support (MVP)

Exploration outputs:
- Evidence-backed explanations
- Rule candidates
- Lineage and impact views

Reimplementation outputs:
- Candidate module-level reimplementation in modern language
- Differential test report and confidence score

## Generated Language Default

Recommendation: **Java as default reimplementation target**, Python optional.

Rationale:
- Deterministic numeric behavior with `BigDecimal`
- Better enterprise acceptance for modernization handoff
- Easier long-term maintainability in regulated environments
