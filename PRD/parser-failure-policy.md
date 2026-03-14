# Parser Failure Policy

## Goal

Define deterministic behavior when the parser cannot fully understand source code.

## Locked Decision

Default policy is **Option B: Best Effort**.

Decision tradeoff summary:
- We gain practical usability on real legacy estates where perfect parsing is unrealistic.
- We accept that some outputs will be partial and require explicit uncertainty handling.
- We reduce "all-or-nothing" ingest failure risk, but must invest in confidence scoring and UX guardrails.

## Failure Classes

- **Class 1: Recoverable syntax issue**
  - Continue with partial AST/graph and explicit uncertainty
- **Class 2: Unsupported construct/dialect extension**
  - Mark unknown node type, preserve raw span, continue downstream with degraded confidence
- **Class 3: Blocking parse failure**
  - Fail module-level analysis; keep codebase-level ingest running
- **Class 4: Systemic parser failure**
  - Abort ingest with actionable diagnostics

## Policy Options

### Option A: Fail Fast

- Hard-stop on first module failure

Pros:
- Avoids misleading partial outputs
- Simpler mental model for users ("if it ran, it is fully parsed")
- Lower chance of downstream systems acting on incomplete structures

Cons:
- Poor usability on real-world messy estates
- High operational friction; small syntax anomalies can block entire onboarding
- Encourages hidden workarounds outside the product

### Option B: Best Effort (recommended)

- Continue ingest with per-module failure annotations
- Compute coverage and confidence penalties

Pros:
- Delivers value even with imperfect coverage
- Mirrors reality of legacy environments
- Enables phased remediation while teams still get analysis value
- Better fit for large, heterogeneous codebases and dialect drift

Cons:
- Requires strong uncertainty UX
- Greater implementation complexity in scoring, gating, and explainability
- Risk of over-trust if warnings are not prominent and enforced

## Required Outputs on Any Failure

- Error class and machine-readable code
- Source location and parser context
- Suggested remediation path
- Coverage impact metrics

## SLA/Quality Gates

- Minimum parse coverage threshold for enabling reimplementation actions
- Hard block "equivalence-ready" status when blocking parse failures exist in module scope

Locked threshold reference:
- Parser coverage gate is aligned to platform SLOs: **90% overall; 95% for migration-candidate modules**.

## Open Questions

- Do we permit customer overrides below threshold with explicit risk acceptance?
