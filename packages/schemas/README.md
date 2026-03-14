# schemas

Shared contracts used by all services.

## Initial Schemas

- `claim.schema.json`
- `readiness-gate.schema.json`
- `policy-routing-decision.schema.json`
- `validation-run.schema.json`

## Rules

- Schema changes must be versioned.
- Backward-incompatible changes require a major version bump.
- All services validate payloads at boundaries.
