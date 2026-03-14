# Evidence Contract

## Purpose

The evidence contract defines when a model output is displayable, reviewable, or actionable.

## Locked Decision

Default strategy for MVP is **Option B: Citation + Verifier Contract**.
Rejected/low-support claims policy is **visible + blocked from action + mandatory reviewer note before any override**.
Maximum acceptable false-positive rate for "likely rule" labels is tiered:
- **Critical modules: <= 1%**
- **Non-critical modules: <= 3%**

Decision tradeoff summary:
- We preserve high trust for high-stakes domains while maintaining practical exploration throughput in lower-risk areas.
- We avoid a single global threshold that is either too strict for discovery or too loose for migration-critical logic.

Long-term target:
- **Option C: Formal Rule-Proof Contract** is the correct end-state for final/high-assurance versions.
- MVP architecture should preserve a clean upgrade path to rule-proof validation.

## Strategy Options

### Option A: Citation-Only Contract

- Each claim must cite source spans.
- No formal verifier stage required.

Pros:
- Faster to implement

Cons:
- Easy to over-trust weak or cherry-picked evidence

### Option B: Citation + Verifier Contract

- Each claim includes citations
- Independent verifier checks support strength and contradiction
- Unsupported claims downgraded or rejected

Pros:
- Better trust calibration
- Stronger enterprise audit posture

Cons:
- Extra latency and complexity

### Option C: Formal Rule-Proof Contract (final target)

- Requires executable rules or symbolic checks for high-stakes claims

Pros:
- Highest assurance

Cons:
- Heavy engineering cost for MVP

## MVP Contract Schema

Required fields per claim:
- `claim_id`
- `claim_text`
- `evidence` (list of source anchors with node/span ids)
- `support_strength` (high/medium/low)
- `contradictions` (optional)
- `confidence_score` (0-1)
- `review_status` (auto-passed/needs-human/rejected)

## Display Policy

- Show "likely rule" only when verifier status is auto-passed and support >= medium.
- Show "hypothesis" when support is low or contradictory.
- Rejected and low-support claims remain visible for transparency and learning loops.
- Rejected and low-support claims are blocked from migration-impacting actions by default.
- Any override requires reviewer identity, reason code, and free-text justification note.
