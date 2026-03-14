# Security Model

## Product Requirement

Users can choose inference mode per workspace or tenant:
- **Local/private mode** (on-prem or VPC-isolated model/runtime)
- **External model mode** (managed API providers)

## Locked Decision

Rollout path is **external-first** for frontier-model capability.
Policy default for sensitive/proprietary workloads is **local/private mode**.

Decision tradeoff summary:
- We gain higher model quality and faster capability iteration in early product phases.
- We preserve data-governance safety by requiring local/private mode for sensitive/proprietary contexts.
- We accept additional policy-routing complexity and need strong enforcement/audit controls.
- We reduce some procurement friction for innovation-focused teams, while still supporting strict environments.

## Mode Comparison

### Local/Private Mode

Pros:
- Maximum control and compliance alignment
- Easier acceptance in regulated environments

Cons:
- Higher deployment complexity and infra cost
- Potentially weaker/older models unless tuned

### External Mode

Pros:
- Faster iteration and higher model quality ceiling
- Lower initial infra burden

Cons:
- Data governance and vendor risk concerns

## Baseline Security Controls (Both Modes)

- Tenant-level isolation
- Role-based access control
- Encryption at rest and in transit
- Prompt/completion audit logs
- Retention and deletion policies by artifact type
- Configurable redaction for sensitive tokens/fields

## External Mode Additional Controls

- Per-provider allowlist and policy profiles
- Optional prompt minimization and pseudonymization
- Regional routing controls
- Contractual controls for data retention/training usage

## Local Mode Additional Controls

- Support air-gapped deployment profile
- Offline model package and update process
- Local key management integration

## Mode-Switch Module Requirement

- Include a first-class mode-switch module that makes transitioning between external and local inference easy.
- Mode switching must support policy templates (e.g., `sensitive-local`, `standard-external`) and audit logging.
- Sensitive-data detectors and tenant policy flags must hard-route to local/private mode.

## Open Questions

- Which compliance regimes are required first (SOC2, ISO 27001, regional data laws)?
