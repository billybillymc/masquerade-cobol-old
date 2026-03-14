# Locked Decisions (Single Source of Truth)

This file captures the currently locked strategic/product decisions across the PRD set.

## Product Strategy

- Workflow order: **impact analysis -> discovery/exploration -> migration pilot**
- KPI model: **composite scorecard**
- Primary 90-day KPI: **faster impact assessments**
- Product motion: **hybrid packaging** (exploration-first entry, migration upsell)

## Scope and Language

- Core stack: **Java/Kotlin parser+IR**, **Python AI pipeline**, **TypeScript UI/API**
- CICS support: **partial executable in MVP**, **full executable in final**
- Generated code visibility: **only for modules above readiness threshold**
- Generated target language default: **Java** (Python optional)

## Trust and Validation

- Numeric semantics policy:
  - **Migration-ready: strict emulation required**
  - **Sandbox/exploration: bounded-equivalence allowed (non-production, non-actionable)**
- Evidence contract (MVP): **citation + verifier**
- Evidence contract (final): **formal rule-proof target**
- Rejected/low-support claims: **visible + blocked + mandatory reviewer-note override**
- Error severity ranking: **missed edge case > false negative dependency > false positive rule**
- Evidence thresholds:
  - Baseline modules: **2 anchors + verifier pass + confidence >= 0.70**
  - Critical modules: **3 anchors (including cross-artifact) + stronger verifier/reviewer check + confidence >= 0.85**
- Threshold rollout model:
  - MVP: **global thresholds**
  - Post-MVP: **policy profiles (strict/standard/permissive) with audit + visibility guardrails**
  - Migration gating: **`migration-ready` requires standard-or-stricter profile**
- Maximum acceptable false-positive rate for "likely rule" labels:
  - Critical modules: **<= 1%**
  - Non-critical modules: **<= 3%**
- HITL approver minimum for `migration-ready`:
  - **Modernization Engineer + Domain SME + Risk/Controls Owner**

## Parsing and Ingest

- Parser failure policy: **best effort**
- Incremental ingest gate: **high-assurance full recompute required before migration-ready**
- Canonical IR:
  - MVP: **Strategy A (typed AST + graph overlay)**
  - Final: **Strategy B (unified schema/DSL)**

## Security and Deployment

- Deployment path: **external-first**
- Sensitive/proprietary workload policy: **route to local/private mode by default**
- Inference mode switchability: **first-class mode-switch module with policy-based routing and audit logs**
- Inference modes supported: **local/private** and **external**
- MVP benchmark scale: **500K LOC**
- Near-term post-MVP target: **3M+ LOC**
- Latency profile (p95):
  - Lineage: **4.0s**
  - Impact: **6.0s**
  - RAG with citations: **9.0s**
- Stretch post-MVP latency (p95):
  - Lineage: **2.0s**
  - Impact: **3.0s**
  - RAG with citations: **5.0s**
- Reliability SLOs:
  - Ingest success: **99.0%**
  - Incremental refresh success: **99.5%**
  - Parser coverage: **90% overall; 95% for migration-candidate modules**

## Commercial Model

- Primary proof point: **impact accuracy**
- Secondary proof point: **validated modernization percentage**
- Pricing axis: **hybrid (platform + usage)**
- Default personas:
  - Economic buyer: **CIO / Head of Core Systems Modernization**
  - Day-to-day champion: **Mainframe Modernization Lead (or Principal Enterprise Architect)**
  - Compliance signer: **Risk/Controls Lead (with IT audit/compliance involvement)**

## Metric and Scoring Definitions

- **Impact accuracy** = `correct impact predictions / total reviewed impact predictions`
- **Validated modernization percentage** = `modules marked migration-ready with passing differential validation / total modules submitted for modernization validation`
- **Readiness score inputs** = parser coverage + evidence/verifier quality + testability + dependency isolation
- **Readiness threshold ownership** = risk/controls governance (implementation maintained by platform engineering)

## Decision-Making Rule

If any topic doc conflicts with this file, treat this file as canonical until an explicit new lock decision is made.
