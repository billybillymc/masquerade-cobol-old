# Implementation Plan (Execution-Oriented)

## Phase 0 (2-3 days): Foundation

- Establish monorepo structure and service boundaries.
- Define shared contracts:
  - IDs,
  - artifact schemas,
  - claim/evidence/verifier schema.
- Add policy docs to code (`policy-gateway` contract as code).

Exit criteria:
- all services compile/run hello-world,
- shared schema package versioned.

## Phase 1 (Week 1): Parse + IR + Coverage

- Integrate parser and copybook resolution.
- Emit AST + graph overlay payload.
- Implement parse diagnostics and coverage scoring.

Exit criteria:
- parse and index CardDemo baseline,
- produce coverage report and unknown-construct report.

## Phase 2 (Week 2): Graph + Query Backbone

- Persist graph entities/edges.
- Implement API endpoints for:
  - graph neighborhood,
  - dependency lookup,
  - change blast-radius skeleton.

Exit criteria:
- UI can browse dependencies and show source-linked nodes.

## Phase 3 (Week 3): RAG + Verifier + Evidence UX

- Build retrieval pipeline (hybrid + graph-neighbor expansion).
- Implement explanation/rule generation with verifier pass.
- Enforce rejected/low-support visibility + action blocking.

Exit criteria:
- business-question queries return evidence-backed results.

## Phase 4 (Week 4): Lineage + Impact Accuracy Loop

- Implement field lineage traversal + confidence labels.
- Implement impact prediction endpoint with reviewer feedback capture.
- Start impact-accuracy measurement loop.

Exit criteria:
- baseline impact-accuracy dashboard available.

## Phase 5 (Week 5): Validation Harness + Reimplementation Pilot

- Implement candidate generation path.
- Add differential harness and mismatch taxonomy.
- Enforce strict emulation for migration-ready path.
- Support sandbox bounded-equivalence mode (non-actionable).

Exit criteria:
- at least one scoped module can complete end-to-end differential run.

## Phase 6 (Week 6): Governance + Hardening

- Implement high-assurance recompute gate.
- Implement 3-party approval workflow and audit logs.
- Add readiness score dashboard and gate status.
- Run benchmark + demo script finalization.

Exit criteria:
- migration-ready gate demonstrates all required checks.

## Cross-Phase Non-Negotiables

- keep policy routing test coverage high,
- treat unknown parse artifacts as first-class outputs,
- keep benchmark/eval regression suite running continuously,
- keep all claims source-linked and schema-valid.
