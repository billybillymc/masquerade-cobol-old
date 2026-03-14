# Eval Dataset Strategy

## Goal

Build a durable benchmark suite that measures trustworthiness and migration readiness, not just model fluency.

## Locked Decision

Default strategy is **Option C: Hybrid**.

Reason:
- It balances semantic quality (human judgment), realistic coverage (trace-derived behavior), and robustness (synthetic edge-case stress tests).
- It avoids overfitting to either expensive but narrow expert labels or broad but shallow execution traces.

## What to Evaluate

1. Explanation correctness
2. Rule extraction precision/recall
3. Lineage path fidelity
4. Impact analysis accuracy
5. Differential equivalence pass rate for reimplementation candidates

## Dataset Sources

- Hand-labeled subsets from representative COBOL programs
- Curated "known behavior" scenarios from SMEs
- Legacy production-like input/output traces (sanitized)
- Synthetic edge-case generators for numeric/date/control-flow boundaries

## Dataset Structure

- `golden_rules.jsonl` (claim + accepted evidence spans)
- `lineage_gold.jsonl` (field path expectations)
- `impact_gold.jsonl` (change -> expected blast radius)
- `equivalence_vectors.jsonl` (inputs + expected outputs/tolerances)

## Strategy Options

### Option A: Human-Labeled Heavy

- Strengths:
  - Highest semantic precision for business-rule truth and explanation quality.
  - Best for nuanced intent that traces do not encode (policy rationale, legal interpretation).
  - Strongest audit story when claims are challenged by domain reviewers.
- Weaknesses:
  - Slow and expensive to scale; expert labeling becomes the bottleneck.
  - Can be biased toward the specific SMEs and code slices selected.
  - Risks stale coverage if codebase evolves faster than labels are maintained.
- Best use:
  - Gold anchor sets for critical modules and high-stakes rule categories.

### Option B: Trace-Derived Heavy

- Strengths:
  - Scales quickly with production-like traffic and historical runs.
  - Captures real behavior distributions, including operational edge patterns.
  - Useful for validating differential behavior and regression detection.
- Weaknesses:
  - Weak on intent-level correctness ("why" the rule exists).
  - Limited by what was historically exercised; rare but critical branches may be absent.
  - Can encode legacy bugs as "ground truth" if not curated.
- Best use:
  - Expansion layer for breadth and real-world behavior coverage.

### Option C: Hybrid (recommended)

- Composition:
  - Human-labeled anchor set for semantic truth
  - Trace-derived expansion for scale and realism
  - Synthetic generators for boundary and adversarial cases
- Why this is the best default:
  - Preserves trust where it matters while still giving broad, repeatable coverage.
  - Reduces blind spots from both expert-only and trace-only approaches.
  - Creates a defensible path from MVP validation to enterprise-grade assurance.
- Operational note:
  - Treat anchor sets as immutable references; rotate trace and synthetic expansions on a schedule.

## Governance

- Version datasets and labeler guidelines
- Track inter-annotator agreement
- Gate prompt/model changes on benchmark thresholds
- Preserve historical runs for regression visibility

## Open Questions

- Who will serve as labeling authority (internal SME vs partner domain expert)?
- What minimum benchmark size is acceptable before customer pilots?
