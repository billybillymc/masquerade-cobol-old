# Implementation Plan: Field Lineage + Conceptual Search

**Branch**: `004-lineage-search` | **Date**: 2026-03-14 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/004-lineage-search/spec.md`

## Summary

Build field lineage tracing, conceptual search (RAG), and blast-radius impact analysis on top of the parser (001), dependency graph (002), and semantic pipeline (003). The system provides hybrid retrieval (lexical + embedding + graph-neighbor expansion), traces field flows through pipeline paths with confidence labels, answers natural-language questions grounded in code evidence, and surfaces unknown edges as first-class outputs. Delivers code + explanation side-by-side in the exploration UI.

## Technical Context

| Dimension | Value |
|-----------|-------|
| **Languages** | Python (analysis-orchestrator), TypeScript (web-app) |
| **Primary Dependencies** | 001 parser IR, 002 graph DB, 003 semantic outputs (summaries, rules), embedding model, LLM for RAG |
| **Retrieval Strategy** | Hybrid: lexical (BM25/keyword), embedding similarity, graph-neighbor expansion |
| **Retrieval Units** | Paragraph/section + surrounding data definitions + caller/callee context |
| **Storage** | Graph DB for lineage/impact queries; vector store for embeddings; content-addressed cache |
| **Testing** | pytest (orchestrator), Vitest/Jest (web-app), integration tests against CardDemo/taxe-fonciere |
| **Latency Targets** | Lineage p95 ≤ 4.0s, impact p95 ≤ 6.0s, RAG p95 ≤ 9.0s |
| **Evidence Thresholds** | Baseline: 2 anchors + confidence ≥ 0.70; Critical: 3 anchors + confidence ≥ 0.85 |
| **Constraints** | Unknown edges first-class; no fabrication; context window limits enforced via high-signal slicing |
| **Scale** | CardDemo/taxe-fonciere for MVP; stress test ~500K LOC |

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Evidence-Grounded Analysis | PASS | All lineage, impact, and RAG outputs require evidence anchors; "insufficient evidence" when thresholds not met |
| II. Test-First Development | PASS | TDD for retrieval, lineage, impact, RAG; characterization tests on CardDemo before changes |
| III. Verified Modernization | N/A | Lineage/search inform modernization; no diff execution in this feature |
| IV. Graceful Degradation | PASS | Unknown edges surfaced as first-class; low-confidence results labeled; partial results on partial graph |
| V. Structured Outputs with Provenance | PASS | LineageTrace, BlastRadius, ConceptualSearchResult use claim/evidence/confidence/uncertainty schema |
| VI. Resumable and Idempotent Pipelines | PASS | Embedding and retrieval use content-addressed caching; lineage/impact queries idempotent |
| VII. Single Dialect Focus | N/A | Inherits from 001–003 |

## Project Structure

### Documentation (this feature)

```text
specs/004-lineage-search/
├── plan.md              # This file
├── tasks.md             # Actionable task breakdown
├── checklists/
│   └── requirements.md
└── contracts/           # API contracts for lineage, impact, RAG endpoints
```

### Source Code (repository root)

```text
services/analysis-orchestrator/
├── src/
│   ├── retrieval/
│   │   ├── hybrid_retriever.py      # Lexical + embedding + graph
│   │   ├── chunk_builder.py         # Paragraph/section + data + caller/callee
│   │   └── provenance_header.py     # Provenance header generation
│   ├── lineage/
│   │   ├── field_lineage.py         # Trace field through pipeline paths
│   │   ├── lineage_trace.py         # LineageTrace model
│   │   └── unknown_edge.py          # UnknownEdge first-class model
│   ├── impact/
│   │   ├── blast_radius.py          # Blast radius computation
│   │   └── blast_radius_model.py    # BlastRadius model
│   ├── rag/
│   │   ├── conceptual_search.py    # RAG for natural-language queries
│   │   └── evidence_threshold.py   # Evidence threshold enforcement
│   └── api/
│       └── lineage_search_api.py   # HTTP endpoints
├── tests/
│   ├── test_hybrid_retriever.py
│   ├── test_field_lineage.py
│   ├── test_blast_radius.py
│   ├── test_conceptual_search.py
│   └── integration/
│       └── test_carddemo_lineage_search.py
├── pyproject.toml
└── README.md

services/web-app/
├── src/
│   ├── app/
│   │   └── exploration/
│   │       ├── page.tsx             # Exploration UI
│   │       ├── code_explanation_view.tsx  # Side-by-side code + explanation
│   │       └── lineage_view.tsx     # Lineage trace display
│   └── components/
│       ├── LineageTracePanel.tsx
│       ├── BlastRadiusPanel.tsx
│       └── ConceptualSearchPanel.tsx
└── ...

packages/schemas/
├── lineage-trace.schema.json
├── blast-radius.schema.json
├── conceptual-search-result.schema.json
└── retrieval-chunk.schema.json
```

## Phase 0: Research

**Duration**: 1 day  
**Output**: `specs/004-lineage-search/research.md` (optional, if needed)

1. **Embedding model selection**: Evaluate embedding models (e.g., sentence-transformers, OpenAI) for code/COBOL chunk similarity; measure retrieval quality on CardDemo paragraphs.
2. **Graph query patterns**: Document graph DB query patterns for lineage (field → READ/WRITE/MOVE chains) and blast radius (field → programs/paragraphs).
3. **Context window strategy**: Define high-signal slice selection (relevance score, graph centrality) and truncation rules for RAG context assembly.
4. **Latency baseline**: Measure current graph query and embedding lookup latency on CardDemo; identify bottlenecks for 4s/6s/9s targets.

## Phase 1: Design

**Duration**: 1–2 days  
**Output**: `contracts/`, schema definitions

1. Define `LineageTrace`, `BlastRadius`, `ConceptualSearchResult`, `RetrievalChunk`, `UnknownEdge` JSON schemas per spec entities.
2. Define hybrid retrieval pipeline: lexical index build, embedding index build, graph-neighbor expansion API.
3. Define lineage query API: input (field ID), output (LineageTrace with steps, confidence, unknown steps).
4. Define impact query API: input (field ID), output (BlastRadius with affected items, evidence, unknown dependencies).
5. Define RAG API: input (natural-language query), output (ranked results with evidence, confidence, provenance).
6. Define code + explanation side-by-side API contract (code region → explanation with citations).
7. Write contract tests that validate schema compliance and latency budgets.

## Phase 2: Implementation

**Duration**: 4–5 days  
**Output**: Working lineage, impact, RAG, and exploration UI

### Step 1: Hybrid Retrieval (TDD)

- Write failing tests: given a query, retrieval returns chunks combining lexical, embedding, and graph-neighbor context.
- Write failing tests: each chunk has provenance header; context is limited to high-signal slices.
- Implement `ChunkBuilder` (paragraph/section + data + caller/callee).
- Implement lexical index (BM25 or keyword) over chunks.
- Implement embedding index and similarity search.
- Implement graph-neighbor expansion.
- Implement `HybridRetriever` that merges and ranks results.
- Make tests green.

### Step 2: Field Lineage (TDD)

- Write failing tests: given a field, lineage returns trace with steps, source spans, confidence, ambiguity labels.
- Write failing tests: unknown/unresolved steps are surfaced as first-class outputs.
- Implement `FieldLineage` using graph READS_FIELD/WRITES_FIELD and MOVE chains.
- Implement confidence and ambiguity labeling.
- Implement `UnknownEdge` handling (dynamic CALL, missing copybook, etc.).
- Make tests green. Verify p95 ≤ 4.0s on CardDemo.

### Step 3: Blast Radius (TDD)

- Write failing tests: given a field, blast radius returns affected programs, paragraphs, evidence.
- Write failing tests: unknown dependencies surfaced with explicit labels.
- Implement `BlastRadius` using graph traversal (field → programs, paragraphs).
- Implement evidence anchors and confidence.
- Make tests green. Verify p95 ≤ 6.0s on CardDemo.

### Step 4: Conceptual Search RAG (TDD)

- Write failing tests: given "where do we calculate late fees?", returns ranked results with evidence, confidence, provenance.
- Write failing tests: no matches → "insufficient evidence" or low-confidence indicators; no fabrication.
- Implement `ConceptualSearch` using hybrid retrieval + LLM generation.
- Implement evidence threshold enforcement (2 anchors + 0.70 baseline; 3 anchors + 0.85 critical).
- Implement two-pass verifier for RAG answers.
- Make tests green. Verify p95 ≤ 9.0s on CardDemo.

### Step 5: Code + Explanation Side-by-Side (TDD)

- Write failing tests: given code region, returns explanation with citations.
- Implement explanation lookup from semantic pipeline outputs.
- Implement side-by-side view in web-app.
- Make tests green.

### Step 6: Exploration UI Integration

- Integrate lineage, blast radius, conceptual search into exploration UI.
- Add LineageTracePanel, BlastRadiusPanel, ConceptualSearchPanel.
- Wire APIs from web-app to analysis-orchestrator.
- End-to-end test: conceptual query → lineage click-through → blast radius.

### Step 7: Stress Test

- Run lineage, impact, RAG against ~500K LOC corpus.
- Verify latency targets and evidence quality maintained.
- Document results in benchmark report.

## Complexity Tracking

No constitution violations. Hybrid retrieval and graph integration follow established patterns. Unknown edges are first-class per spec and constitution.
