# Engineering Architecture (MVP Execution)

## 1. System Boundary

MVP delivers:
- exploration workflows (RAG + graph + impact/lineage),
- constrained reimplementation pilot,
- governance-first migration readiness gates.

Non-goals remain:
- full multi-dialect support,
- full CICS parity,
- fully automated production cutover.

## 2. Service Topology

## 2.1 `parser-ir-service` (Java/Kotlin)

Responsibilities:
- COBOL parsing (IBM Enterprise COBOL target),
- copybook resolution,
- AST generation with stable IDs,
- graph overlay extraction (`CALLS`, `PERFORMS`, `READS_FIELD`, `WRITES_FIELD`, etc.),
- parser diagnostics and coverage metrics.

Outputs:
- AST artifacts (versioned),
- graph nodes/edges payload,
- parse diagnostics and coverage report.

## 2.2 `analysis-orchestrator` (Python)

Responsibilities:
- pipeline orchestration,
- retrieval chunk assembly (AST + graph-aware),
- LLM request flow (external-first, local-route for sensitive workloads),
- verifier pass and confidence scoring,
- impact and lineage query jobs,
- readiness score computation.

Outputs:
- rule candidates with evidence,
- explanation artifacts,
- lineage and impact result artifacts,
- readiness score snapshots.

## 2.3 `validation-harness` (Python/Java hybrid)

Responsibilities:
- candidate reimplementation test harness,
- differential execution and mismatch classification,
- strict numeric emulation checks for migration-ready gates,
- sandbox-mode bounded-equivalence experiments (non-actionable).

Outputs:
- diff reports,
- mismatch taxonomy,
- migration-readiness gate signals.

## 2.4 `policy-gateway` (TypeScript or Python edge service)

Responsibilities:
- enforce inference routing policy:
  - external-first default,
  - force local for sensitive/proprietary workload tags,
- mode-switch module (policy templates + audit logs),
- request-level policy tracing.

Outputs:
- policy decision logs,
- routing audit artifacts.

## 2.5 `web-app` (TypeScript / Next.js)

Responsibilities:
- exploration UI (questioning, graph browse, lineage, impact),
- evidence-first rendering with uncertainty and rejected-claim labels,
- HITL review workflow and approval actions,
- migration readiness dashboard.

## 3. Storage and Data Contracts

## 3.1 Storage

- Graph DB: program/copybook/file/table/job dependencies.
- Metadata DB: runs, scores, approvals, policy events.
- Object store: AST snapshots, chunk artifacts, diff outputs, eval runs.
- Search index/vector index: hybrid retrieval.

## 3.2 Core IDs

All services must preserve stable IDs:
- `program_id`, `section_id`, `paragraph_id`, `field_id`, `statement_id`,
- `artifact_version_id`,
- `claim_id`, `run_id`, `approval_id`.

## 4. Critical Runtime Policies

- Migration-ready requires:
  - readiness threshold pass,
  - high-assurance recompute pass,
  - strict numeric emulation pass,
  - 3-party HITL approval.
- Sandbox artifacts cannot be actioned into migration-ready.
- Rejected/low-support claims are visible but blocked by default.

## 5. Initial Performance and Reliability Targets

- p95 lineage <= 4.0s
- p95 impact <= 6.0s
- p95 RAG+citation <= 9.0s
- ingest success >= 99.0%
- incremental refresh success >= 99.5%
- parse coverage >= 90% overall, >= 95% migration-candidate modules

## 6. Engineering Risks To Manage Early

- parser coverage volatility due to dialect edge cases,
- policy drift between orchestrator and UI behavior,
- confidence score calibration mismatch with reviewer expectations,
- reviewer throughput bottlenecks in 3-party gate model.
