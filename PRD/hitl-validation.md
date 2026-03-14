# HITL Validation for Reimplementation

## Objective

Enable reimplementation without pretending full automation. Humans approve progression at explicit gates.

## Locked Decision

Minimum approver set for `migration-ready` is:
- **Modernization Engineer + Domain SME + Risk/Controls Owner**

Decision tradeoff summary:
- We gain stronger trust, governance alignment, and audit defensibility.
- We reduce risk of technically-correct but business-incorrect migrations.
- We accept slower cycle time and higher coordination overhead in approval workflows.

## Pipeline

1. **Exploration Gate**
   - Module has sufficient parse coverage and evidence quality
   - Human confirms module boundaries and business purpose
2. **Candidate Generation Gate**
   - System generates modern implementation candidate + mapping report
   - Human reviews semantic mapping and excluded behaviors
3. **Differential Test Gate**
   - Run legacy and candidate against shared vectors
   - Human reviews mismatches and classifies acceptable vs blocking
4. **Readiness Gate**
   - Equivalence confidence score + unresolved risks presented
   - Domain owner approves "migration-ready" label

## Roles

- **Domain SME**: validates business rule interpretations
- **Modernization Engineer**: reviews generated code quality
- **Risk/Controls Owner**: signs off equivalence claim thresholds

## Concrete Validation Artifacts

- Rule trace matrix (claim -> evidence -> reviewer decision)
- Transformation map (COBOL construct -> generated construct)
- Differential report with mismatch taxonomy
- Final risk ledger for unresolved edge cases

## UX Recommendations

- Show "Approve / Reject / Needs Evidence" per rule and per diff cluster
- Require reason codes for overrides
- Record reviewer identity and timestamps for auditability

## Open Questions

- Do you want one global threshold or domain-specific thresholds by module type?
