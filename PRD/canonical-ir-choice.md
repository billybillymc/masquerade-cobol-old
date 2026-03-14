# Canonical IR Choice

## Locked Decision

- MVP: **Strategy A (Typed AST + Graph Overlay)**
- Final target: **Strategy B (Unified Intermediate DSL/Schema)**

Decision tradeoff summary:
- We gain faster MVP delivery and better parser-debuggability by preserving parser-native structures.
- We reduce near-term risk of semantic loss during early normalization.
- We accept interim model complexity (dual-layer AST + graph synchronization).
- We preserve long-term convergence to a cleaner universal IR once behavior is well characterized.

## What "Canonical IR" Means

Canonical IR is the common representation all components use after parsing:
- parser
- static analyzer
- graph extractor
- RAG indexer
- explanation/rule generation
- reimplementation generator
- diff/validation harness

Without a canonical IR, each stage invents its own model and drifts.

## Required IR Properties

- Lossless links back to source spans
- Stable IDs for programs, sections, paragraphs, fields, and statements
- Explicit typing for data definitions and storage format hints
- Control-flow edges (`PERFORM`, `CALL`, branch edges)
- Data-flow edges (read/write/move/transform)
- Extensibility for dialect-specific nodes

## Two Viable Strategies

### Strategy A: Typed AST + Graph Overlay (recommended for MVP)

- Keep parser-native AST (typed classes)
- Build normalized graph overlay with stable node IDs
- Keep direct source references in both layers

Pros:
- Fastest path from parser integration to usable analysis
- Easier debugging with parser-native structures
- Good fit for evidence-backed UX

Cons:
- More moving parts to keep in sync

### Strategy B: Unified Intermediate DSL/Schema

- Transform parsed code into one universal schema immediately
- All downstream systems consume schema only

Pros:
- Cleaner abstraction boundaries
- Easier multi-language/multi-dialect evolution later

Cons:
- Large upfront design burden
- Risk of losing edge-case semantics early

## Recommendation

Start with **Strategy A** for MVP, while designing graph IDs and metadata so migration to Strategy B is deliberate and low-friction.

## Open Questions

- Which node granularity is needed for first-class UX: paragraph-level or statement-level?
- Which IR fields are mandatory for modernization readiness scoring?
