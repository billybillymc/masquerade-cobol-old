# Trust and Correctness Questions

Use this document to lock policy choices before customer pilots.

## Locked Decisions

- Most unacceptable error ranking: **missed edge case > false negative dependency > false positive rule**
- Evidence threshold policy: **baseline + stricter critical modules**
- Rejected claims visibility: **yes, visible with explicit rejected labeling**
- Threshold rollout model: **global thresholds in MVP; policy profiles post-MVP with guardrails**

Decision tradeoff summary:
- We prioritize avoidance of rare but catastrophic behavioral misses.
- We bias toward higher recall in dependency and edge-case detection, even if review burden increases.
- We accept more "needs evidence" outcomes to prevent silent overconfidence.
- We allow faster decisions in low-risk areas while enforcing stronger proof for high-stakes domains.
- We increase transparency and reviewer trust by exposing rejection reasons, while requiring strong UX labeling to prevent misinterpretation.
- We keep MVP behavior predictable while preserving enterprise flexibility in later phases.

## Minimum Evidence for "Likely True"

Candidate baseline:
- At least 2 independent source anchors
- Verifier pass with no direct contradiction
- Confidence >= configured threshold

Decision:
- [ ] Adopt this baseline
- [x] Raise threshold for critical modules
- [ ] Alternative (describe)

Locked threshold policy:
- Baseline modules:
  - At least 2 independent evidence anchors
  - Verifier pass with no unresolved contradictions
  - Confidence score >= 0.70
- Critical modules (financial/compliance/safety):
  - At least 3 independent evidence anchors, including one cross-artifact anchor (e.g., code + copybook/JCL/DB2 reference)
  - Verifier pass with contradiction check and reviewer acknowledgement
  - Confidence score >= 0.85

Threshold rollout plan:
- MVP: one global threshold policy for all customers (simple, auditable baseline).
- Post-MVP: policy profiles (`strict`, `standard`, `permissive`) with hard guardrails:
  - Profile changes are audit-logged with actor and reason.
  - Active profile must be visible in UI and exported reports.
  - `migration-ready` actions require `standard` or stricter profile.

## Most Unacceptable Error Type

Rank these by business severity:
1. False positive rule
2. False negative dependency
3. Missed edge case

Your ranking:
- [ ] 1 > 2 > 3
- [ ] 2 > 1 > 3
- [ ] 3 > 1 > 2
- [x] Other
- Locked ranking: **3 > 2 > 1**

Implications:
- Edge-case suites and adversarial tests are mandatory before migration-ready status.
- Dependency recall is favored over precision for blast-radius analysis.
- Reviewer workflows must highlight "coverage gaps" and unknown branches prominently.

## Human Authority Model

Who confirms extracted rules in pilots?
- [ ] Internal modernization lead only
- [ ] Internal lead + customer domain SME
- [x] Internal lead + SME + controls owner

Notes:
- Rejected claims are visible in UI for debugging/audit learning loops.
- Rejected items must be clearly marked non-actionable and excluded from migration-readiness scoring.

