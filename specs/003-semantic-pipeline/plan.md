# Implementation Plan: LLM Semantic Analysis Pipeline

**Branch**: `003-semantic-pipeline` | **Date**: 2026-03-14 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/003-semantic-pipeline/spec.md`

## Summary

Build an LLM semantic analysis pipeline for paragraph/section summaries, candidate business rule extraction, and evidence-backed explanations with source span citations. The pipeline uses a two-pass draft-and-verify pattern to reduce hallucination. Retrieval is grounded on paragraph/section units plus surrounding data definitions and caller/callee context (not raw file dumps). Evidence thresholds are tiered: baseline (2 anchors, confidence ≥ 0.70) and critical modules (3 anchors including cross-artifact, confidence ≥ 0.85). RAG-style conceptual queries use hybrid retrieval (lexical + embedding + graph-neighbor expansion) with p95 latency ≤ 9.0 seconds.

**Technical approach**: Python pipeline in `analysis-orchestrator` consumes parser output (001) and dependency graph (002). LLM client in external-first mode; embedding model and vector store for retrieval. Two-pass generation: draft explanation/rule → verifier pass against cited evidence. Outputs conform to evidence contract schema (claim_id, claim_text, evidence, support_strength, confidence_score, review_status).

## Technical Context

| Dimension | Value |
|-----------|-------|
| **Language/Version** | Python 3.11+ |
| **Primary Dependencies** | LLM client (external API), embedding model, vector store (Chroma/FAISS or equivalent), FastAPI (existing) |
| **Storage** | Vector store for embeddings; parser output + graph from features 001/002 |
| **Testing** | pytest, eval benchmark suite (golden_rules.jsonl or equivalent) |
| **Target Platform** | Linux server (analysis-orchestrator service) |
| **Project Type** | Backend service / AI pipeline |
| **Performance Goals** | RAG p95 latency ≤ 9.0 seconds; rule extraction on taxe-fonciere (6 files) tractable |
| **Constraints** | Evidence thresholds; false-positive rates ≤ 1% (critical), ≤ 3% (non-critical); "insufficient evidence" over fabrication |
| **Scale/Scope** | CardDemo (28 files, 19K LOC), taxe-fonciere (6 files, 2.3K LOC) |

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Evidence-Grounded Analysis** | ✅ Pass | Every claim has evidence anchors; "insufficient evidence" when incomplete; FR-001, FR-011 |
| **II. Test-First Development** | ✅ Pass | TDD enforced; tests before implementation per tasks |
| **III. Verified Modernization** | N/A | Semantic analysis only; no modernization execution claims |
| **IV. Graceful Degradation** | ✅ Pass | Parser/graph gaps surfaced; uncertainty labels; FR-015 |
| **V. Structured Outputs with Provenance** | ✅ Pass | claim, evidence, confidence, uncertainty, validation_status; two-pass pattern; FR-002, FR-004 |
| **VI. Resumable and Idempotent Pipelines** | ⚠️ Deferred | Embedding ingest may be extended; content-addressed caching for retrieval units |
| **VII. Single Dialect Focus** | ✅ Pass | IBM Enterprise COBOL; parser (001) enforces |

## Project Structure

### Documentation (this feature)

```text
specs/003-semantic-pipeline/
├── plan.md              # This file
├── spec.md              # Feature specification
├── checklists/
│   └── requirements.md
├── contracts/           # (Phase 1) Evidence contract, API schemas
├── data-model.md        # (Phase 1) Summary, RuleCandidate, EvidenceAnchor
└── tasks.md             # Task breakdown
```

### Source Code (repository root)

```text
services/
├── analysis-orchestrator/
│   ├── app/
│   │   ├── main.py
│   │   └── semantic/          # NEW: semantic analysis module
│   │       ├── __init__.py
│   │       ├── summarizer.py  # Paragraph/section summaries
│   │       ├── rule_extractor.py
│   │       ├── verifier.py    # Two-pass verifier
│   │       ├── retrieval.py   # RAG retrieval (hybrid)
│   │       ├── thresholds.py  # Baseline vs critical evidence thresholds
│   │       └── prompts.py    # LLM prompt templates
│   └── tests/
│       ├── unit/
│       │   └── test_semantic_*.py
│       ├── integration/
│       │   └── test_semantic_pipeline_*.py
│       └── eval/
│           └── test_false_positive_benchmark.py
├── parser-ir-service/        # (Feature 001)
└── ...

packages/
├── schemas/
│   ├── claim.schema.json      # Existing; extend for rule extraction
│   └── summary.schema.json    # NEW: summary with evidence
└── ...
```

**Structure Decision**: Semantic pipeline lives in `analysis-orchestrator` as new `semantic` submodule. Consumes parser output and graph from features 001/002. LLM client is external-first (configurable endpoint). Vector store for retrieval; embedding model configurable.

## Phase 0: Research & Prerequisites

- **0.1** Confirm parser output and graph schemas from features 001/002; define retrieval unit format (paragraph + data defs + caller/callee).
- **0.2** Evaluate embedding models and vector stores: latency, quality, deployment (local vs. API).
- **0.3** Define evidence contract schema extensions: claim_id, claim_text, evidence, support_strength, contradictions, confidence_score, review_status.
- **0.4** Design two-pass verifier: input (draft + cited spans), output (pass/fail, downgrade reason).
- **0.5** Identify or create labeled benchmark (golden_rules.jsonl) for false-positive rate validation.

## Phase 1: Design & Contracts

- **1.1** Document data model: Summary, RuleCandidate, EvidenceAnchor, VerifierResult, RetrievalUnit, CriticalModule.
- **1.2** Define `summary.schema.json` with evidence anchors; extend `claim.schema.json` for rule extraction.
- **1.3** Define retrieval unit builder: paragraph/section + surrounding data definitions + caller/callee from graph.
- **1.4** Design hybrid retrieval: lexical (BM25/keyword) + embedding + graph-neighbor expansion.
- **1.5** Document evidence thresholds: baseline (2 anchors, 0.70), critical (3 anchors + cross-artifact, 0.85).
- **1.6** Design verifier prompt/ logic: check cited spans exist and support claim; reject fabricated citations.

## Phase 2: Implementation Roadmap

- **2.1** Phase 2 Foundation: Retrieval unit builder, LLM client adapter, evidence contract validation.
- **2.2** User Story 1 (P1): Paragraph/section summaries with citations.
- **2.3** User Story 2 (P1): Business rule extraction in structured form.
- **2.4** User Story 3 (P1): Evidence thresholds and critical module handling.
- **2.5** User Story 4 (P2): Two-pass draft-and-verify generation.
- **2.6** User Story 5 (P2): Rejected/low-support visibility and blocking.
- **2.7** User Story 6 (P2): False-positive rate compliance.
- **2.8** User Story 7 (P3): RAG-style conceptual query with hybrid retrieval.

## Complexity Tracking

> No constitution violations requiring justification. LLM client external-first supports "no external model calls" policy toggle.
