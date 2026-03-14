# Incremental Ingest Strategy

## Locked Decision

Users must manually trigger a **high-assurance full recompute** before any module can be marked `migration-ready`.

Decision tradeoff summary:
- We gain stronger confidence that readiness decisions are based on globally consistent, fresh analysis state.
- We reduce risk from stale caches, partial invalidation misses, or hidden dependency drift.
- We accept longer pre-approval cycle times and higher compute cost at migration decision points.

## Why It Matters

Full re-ingest of million-line estates is too slow and expensive for iterative use.

## Core Principles

- Content-addressed artifacts (hash-based identity)
- Dependency-aware invalidation
- Stage-level caching (parse, graph, embeddings, eval artifacts)
- Idempotent job execution with checkpoints

## Recommended Flow

1. Detect changed files/copybooks/JCL
2. Re-parse only changed units
3. Recompute dependent graph neighborhoods
4. Re-index only affected retrieval chunks
5. Re-score impacted readiness/ROI metrics
6. Preserve historical snapshots for comparison and rollback

## Change Propagation Rules

- Copybook changes trigger fan-out to all dependent programs
- Interface signature changes trigger impact recomputation
- Non-semantic diffs (comments/whitespace) skip deep recompute

## SLO Targets (Initial)

- Small change (<10 files): refresh in <5 minutes
- Medium change (~100 files): refresh in <20 minutes
- Large change (>1000 files): async batch with progress checkpoints

## Open Questions

- What maximum staleness is acceptable for exploration answers?
