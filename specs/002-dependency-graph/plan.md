# Implementation Plan: Dependency Graph + System Model

**Branch**: `002-dependency-graph` | **Date**: 2026-03-14 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/002-dependency-graph/spec.md`

## Summary

Build a dependency graph and system model on top of the COBOL parser output (feature 001). The system extracts program-call graphs (CALL, PERFORM), data dependency links (USES_COPYBOOK, READS_FIELD, WRITES_FIELD), and cross-program dependency mapping. Unknown/unresolved edges are surfaced as first-class outputs. Output conforms to canonical IR Strategy A (typed AST + graph overlay) with stable node IDs and evidence references. Optional JCL/file/table entity extraction is additive.

**Technical approach**: Python graph builder in `analysis-orchestrator` consumes parser JSON output from the Java `parser-ir-service`. Graph is persisted to a property graph store (Neo4j or equivalent). Extraction runs in best-effort mode: partial graph when parsing is incomplete; failed programs appear as unresolved CALLS targets.

## Technical Context

| Dimension | Value |
|-----------|-------|
| **Language/Version** | Python 3.11+ |
| **Primary Dependencies** | Neo4j Python driver (or equivalent), Pydantic, FastAPI (existing) |
| **Storage** | Property graph (Neo4j or equivalent); parser output from `parser-ir-service` |
| **Testing** | pytest |
| **Target Platform** | Linux server (analysis-orchestrator service) |
| **Project Type** | Backend service / pipeline stage |
| **Performance Goals** | Graph extraction for CardDemo (28 files, 19K LOC) in < 60 seconds |
| **Constraints** | Best-effort; partial graph when parse coverage < 100%; unknown edges surfaced |
| **Scale/Scope** | CardDemo (28 files), taxe-fonciere (6 files) as validation targets |

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Evidence-Grounded Analysis** | ✅ Pass | Every edge includes evidence (file, line, span or node ID); FR-012 |
| **II. Test-First Development** | ✅ Pass | TDD enforced; tests before implementation per tasks |
| **III. Verified Modernization** | N/A | Graph extraction only; no modernization claims |
| **IV. Graceful Degradation** | ✅ Pass | Unknown edges first-class; partial graph when parse incomplete; FR-005, FR-008 |
| **V. Structured Outputs with Provenance** | ✅ Pass | JSON schema for nodes/edges; evidence on every edge; FR-009 |
| **VI. Resumable and Idempotent Pipelines** | ⚠️ Deferred | Graph ingest may be extended in later features; not blocking for MVP |
| **VII. Single Dialect Focus** | ✅ Pass | IBM Enterprise COBOL; parser (001) enforces dialect |

## Project Structure

### Documentation (this feature)

```text
specs/002-dependency-graph/
├── plan.md              # This file
├── spec.md              # Feature specification
├── checklists/
│   └── requirements.md
├── contracts/           # (Phase 1) Graph schema, extraction API
├── data-model.md        # (Phase 1) Node/edge schema
└── tasks.md             # Task breakdown
```

### Source Code (repository root)

```text
services/
├── analysis-orchestrator/
│   ├── app/
│   │   ├── main.py
│   │   └── graph/           # NEW: graph extraction module
│   │       ├── __init__.py
│   │       ├── builder.py   # Graph builder from parser output
│   │       ├── extractors/  # CALLS, PERFORMS, USES_COPYBOOK, etc.
│   │       └── store.py    # Graph persistence (Neo4j or equivalent)
│   └── tests/
│       ├── unit/
│       │   └── test_graph_*.py
│       └── integration/
│           └── test_graph_extraction_carddemo.py
├── parser-ir-service/       # (Feature 001) Java/Kotlin parser
└── ...

packages/
├── schemas/
│   ├── graph-node.schema.json   # NEW: node schema
│   └── graph-edge.schema.json    # NEW: edge schema
└── ...
```

**Structure Decision**: Graph extraction lives in `analysis-orchestrator` as a new `graph` submodule. Parser output is consumed via HTTP or file-based contract. Schemas in `packages/schemas` define the canonical IR overlay format.

## Phase 0: Research & Prerequisites

- **0.1** Confirm parser output schema from feature 001 (node IDs, spans, symbol table, COPY resolution).
- **0.2** Evaluate Neo4j vs. in-memory/graph library for MVP: persistence needs, query patterns, deployment constraints.
- **0.3** Define graph node/edge JSON schema aligned with canonical IR Strategy A.
- **0.4** Identify CardDemo and taxe-fonciere fixture paths and parser output format for tests.

## Phase 1: Design & Contracts

- **1.1** Document data model: Program, Paragraph, Section, Copybook, Field, File, Table, Edge, UnknownEdge.
- **1.2** Define `graph-node.schema.json` and `graph-edge.schema.json` in `packages/schemas`.
- **1.3** Define extraction API contract: input (parser output), output (graph JSON), error handling.
- **1.4** Design extractor pipeline: CALLS → PERFORMS → USES_COPYBOOK → READS_FIELD/WRITES_FIELD → optional File/Table/JCL.
- **1.5** Document unknown-edge representation: `unresolved: true`, `reason`, `target_identifier`.

## Phase 2: Implementation Roadmap

- **2.1** Phase 2 Foundation: Graph builder skeleton, schema validation, parser output adapter.
- **2.2** User Story 1 (P1): CALLS and PERFORMS extraction with evidence.
- **2.3** User Story 2 (P1): USES_COPYBOOK, READS_FIELD, WRITES_FIELD extraction.
- **2.4** User Story 3 (P2): Cross-program dependency queries.
- **2.5** User Story 4 (P2): Unknown edges as first-class outputs.
- **2.6** User Story 5 (P2): Canonical IR overlay compatibility.
- **2.7** User Story 6 (P3): Optional File/Table/JCL extraction.

## Complexity Tracking

> No constitution violations requiring justification. Structure aligns with existing `analysis-orchestrator` service.
