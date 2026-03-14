# MVP Backlog (Prioritized)

## P0 - Must Ship

- Parser integration with copybook resolution (IBM Enterprise COBOL scope).
- AST + graph overlay extraction with stable IDs.
- Parse coverage and unknown-construct reporting.
- Evidence contract implementation (claim schema + verifier pass).
- External-first routing with sensitive-local policy enforcement.
- Rejected/low-support claim blocking in action flows.
- Impact analysis baseline endpoint + reviewer feedback loop.
- Readiness score computation + gate checks.
- Strict numeric emulation check in migration-ready path.
- High-assurance recompute gate.
- 3-party approval workflow + audit trail.

## P1 - Strongly Recommended

- Lineage confidence explanations with provenance snippets.
- Mismatch taxonomy enrichment for differential harness.
- UI filters for rejected claims and uncertainty clusters.
- Policy templates for mode switch (`standard-external`, `sensitive-local`).
- Benchmark automation and trend dashboards.

## P2 - Nice To Have (Post-MVP)

- Policy profiles (`strict`, `standard`, `permissive`) rollout.
- Improved CICS transaction coverage depth.
- IR migration prep utilities (A -> B transition helpers).
- Batch migration campaign orchestration.

## Definition of Done (Feature-Level)

- unit tests for logic,
- integration tests for contracts,
- policy enforcement tests for security/routing,
- audit events emitted and queryable,
- docs updated (engineering + PRD references).
