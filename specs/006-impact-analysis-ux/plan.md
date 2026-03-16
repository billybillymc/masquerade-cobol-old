# Implementation Plan: Impact Analysis UX + Hardening + Benchmark

**Branch**: `006-impact-analysis-ux` | **Date**: 2026-03-14 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/006-impact-analysis-ux/spec.md`

## Summary

Polish and harden the Masquerade COBOL platform for Week 6 (final MVP week). Delivers impact analysis UX ("if I change this, what breaks?"), exploration UI with dependency graph browsing and code+explanation side-by-side, conceptual query flow, change simulation with blast radius and ROI/readiness panel, 500K LOC benchmark, and the 10-minute wow demo. Primary proof point: impact accuracy (correct predictions / total reviewed). Reliability SLOs: ingest 99.0%, incremental refresh 99.5%, parser coverage 90%/95%.

## Technical Context

| Dimension | Value |
|-----------|-------|
| **Languages** | TypeScript/React/Next.js (web-app); Python (orchestrator for backend APIs) |
| **Primary Dependencies** | 001–005 (parser, graph, semantic pipeline, lineage, modernization harness) |
| **Primary Proof Point** | Impact accuracy = correct impact predictions / total reviewed impact predictions |
| **Benchmark Scale** | 500K LOC |
| **Reliability SLOs** | Ingest 99.0%, incremental refresh 99.5%, parser coverage 90%/95% |
| **Demo Flow** | Conceptual query → ranked answer → lineage click-through → change simulation → ROI/readiness panel |
| **Testing** | Vitest/Jest (web-app), pytest (orchestrator), E2E for demo flow |
| **Constraints** | Unresolved edges in impact with explicit labeling; no fabrication for conceptual query; partial failures do not block pipeline |
| **Scale** | 500K LOC benchmark; progressive loading for large graphs |

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Evidence-Grounded Analysis | PASS | Impact results include evidence anchors; low evidence surfaced with uncertainty |
| II. Test-First Development | PASS | TDD for impact accuracy metric, benchmark, hardening; E2E for demo flow |
| III. Verified Modernization | N/A | UX and hardening; verification in 005 |
| IV. Graceful Degradation | PASS | Unresolved edges labeled; partial failures produce partial results; errors surfaced with remediation |
| V. Structured Outputs with Provenance | PASS | Impact results, ROI/readiness include evidence and confidence |
| VI. Resumable and Idempotent Pipelines | PASS | Incremental refresh idempotent; benchmark supports resumability |
| VII. Single Dialect Focus | N/A | Inherits from 001 |

## Project Structure

### Documentation (this feature)

```text
specs/006-impact-analysis-ux/
├── plan.md              # This file
├── tasks.md             # Actionable task breakdown
├── checklists/
│   └── requirements.md
├── contracts/           # API contracts for impact, exploration, benchmark
└── demo-script.md       # 10-minute demo script
```

### Source Code (repository root)

```text
services/web-app/
├── src/
│   ├── app/
│   │   ├── exploration/
│   │   │   ├── page.tsx             # Exploration UI entry
│   │   │   ├── graph-view.tsx       # Dependency graph browser
│   │   │   └── code-explanation-view.tsx  # Side-by-side
│   │   ├── impact/
│   │   │   └── page.tsx             # Impact analysis entry
│   │   └── benchmark/
│   │       └── page.tsx             # Benchmark report
│   ├── components/
│   │   ├── DependencyGraph.tsx      # Graph visualization (D3, Cytoscape, or similar)
│   │   ├── ImpactAnalysisPanel.tsx  # Blast radius + impact accuracy
│   │   ├── ROIReadinessPanel.tsx    # Readiness score components
│   │   ├── ConceptualQueryInput.tsx # Natural-language query
│   │   └── ChangeSimulationPanel.tsx # Change sim + blast radius
│   └── lib/
│       ├── impact-api.ts            # Impact analysis API client
│       └── accuracy-tracking.ts     # Impact accuracy recording
├── tests/
│   ├── ImpactAnalysisPanel.test.tsx
│   ├── ROIReadinessPanel.test.tsx
│   ├── DependencyGraph.test.tsx
│   └── e2e/
│       └── demo-flow.spec.ts        # 10-minute demo E2E
└── ...

services/analysis-orchestrator/
├── src/
│   ├── benchmark/
│   │   ├── runner.py               # 500K LOC benchmark runner
│   │   └── report_generator.py     # Benchmark report
│   └── accuracy/
│       └── impact_accuracy.py      # Impact accuracy computation
└── ...

packages/schemas/
├── impact-analysis-result.schema.json
├── roi-readiness.schema.json
└── benchmark-report.schema.json
```

## Phase 0: Research

**Duration**: 0.5–1 day  
**Output**: `specs/006-impact-analysis-ux/research.md` (optional)

1. **Graph visualization**: Evaluate D3, Cytoscape.js, or React Flow for dependency graph at 500K LOC scale; progressive loading strategy.
2. **Impact accuracy workflow**: Define UX for "mark correct/incorrect" on impact predictions; storage and reporting.
3. **Benchmark corpus**: Identify or prepare 500K LOC corpus; define ingest and incremental refresh test scenarios.
4. **Demo script**: Draft 10-minute demo narrative with timing checkpoints.

## Phase 1: Design

**Duration**: 1 day  
**Output**: `contracts/`, `demo-script.md`, schema definitions

1. Define ImpactAnalysisResult, ROIReadiness, BenchmarkReport schemas.
2. Define impact accuracy API: record correct/incorrect, compute M/N, report.
3. Define exploration UI state: selected node, selected edge, code view, explanation view.
4. Define change simulation API: artifact → blast radius + ROI/readiness.
5. Define benchmark API: corpus path → report (ingest rate, refresh rate, parser coverage, reliability).
6. Write 10-minute demo script with step-by-step flow and acceptance checkpoints.
7. Write contract tests for schema compliance and SLO thresholds.

## Phase 2: Implementation

**Duration**: 4–5 days  
**Output**: Polished UX, benchmark report, 10-minute demo flow

### Step 1: Impact Analysis UX (TDD)

- Write failing tests: select copybook field → impact returns ranked affected artifacts with evidence.
- Write failing tests: each item has confidence and evidence; unresolved edges labeled.
- Implement ImpactAnalysisPanel; wire to 004 blast radius API.
- Implement impact accuracy recording (mark correct/incorrect).
- Make tests green.

### Step 2: Exploration UI (TDD)

- Write failing tests: graph displays programs, copybooks, relationships (CALLS, USES_COPYBOOK, etc.).
- Write failing tests: node click → code + explanation side-by-side.
- Write failing tests: edge click → evidence for relationship.
- Implement DependencyGraph with progressive loading for large graphs.
- Implement code+explanation view integration (from 004).
- Make tests green.

### Step 3: Conceptual Query and Change Simulation (TDD)

- Write failing tests: conceptual query returns ranked results; lineage click-through works.
- Write failing tests: change simulation shows blast radius and ROI/readiness panel.
- Implement ConceptualQueryInput; wire to 004 RAG API.
- Implement ChangeSimulationPanel; wire to blast radius and ROI/readiness APIs.
- Implement ROIReadinessPanel with readiness components (parser coverage, evidence quality, testability, dependency isolation).
- Make tests green.

### Step 4: Impact Accuracy (TDD)

- Write failing tests: N reviewed, M correct → accuracy = M/N.
- Write failing tests: accuracy reported in benchmark and dashboard.
- Implement impact accuracy computation and storage.
- Wire into ImpactAnalysisPanel and benchmark report.
- Make tests green.

### Step 5: Benchmark Runner (TDD)

- Write failing tests: 500K LOC corpus → report with ingest rate, refresh rate, parser coverage.
- Write failing tests: ingest ≥ 99.0%, refresh ≥ 99.5%, parser coverage 90%/95%.
- Implement benchmark runner and report generator.
- Make tests green.

### Step 6: Hardening (TDD)

- Write failing tests: batch ingest with some failures → report failures without blocking; success rate computed.
- Write failing tests: incremental refresh with some changes → processes without full re-ingest.
- Write failing tests: parse failure → error surfaced with location and remediation; remaining files continue.
- Write failing tests: partial pipeline failure → partial results; pipeline does not abort.
- Implement graceful degradation in ingest, refresh, and pipeline stages.
- Make tests green.

### Step 7: 10-Minute Demo Flow

- Execute demo script end-to-end on prepared corpus.
- Verify each step completes; tune for ~10-minute duration.
- Document demo script with timing and acceptance criteria.
- E2E test for demo flow.

## Complexity Tracking

No constitution violations. Impact accuracy is the primary proof point per PRD. Hardening aligns with graceful degradation (Constitution IV).
