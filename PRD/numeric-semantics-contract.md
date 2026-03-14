# Numeric Semantics Contract

## Why This Matters

Most failed COBOL modernization attempts fail on numeric behavior:
- packed decimal conversion
- rounding mode mismatch
- sign/scale handling differences
- overflow/truncation behavior drift

## Locked Decision

Default strategy is **Strategy 1: Strict Emulation Contract**.
Policy refinement:
- **Migration-ready paths require strict emulation.**
- **Bounded-equivalence is allowed only in explicitly marked sandbox/exploration mode (non-production, non-actionable).**

Reason:
- Reliability and trust are prioritized over implementation speed.
- Performance goals are still expected from modernization of platform/runtime even with strict numeric behavior parity.

Decision tradeoff summary:
- We preserve maximum trust for production migration decisions.
- We keep experimentation speed by allowing lower-friction sandbox iterations.
- We must enforce hard UX and policy boundaries so sandbox outputs cannot be mistaken for migration-ready results.

## Strategy Options

### Strategy 1: Strict Emulation Contract (high trust, slower)

- Define exact behavior parity with COBOL runtime for in-scope operations
- Use high-precision decimal runtime wrappers
- Reimplementation code must call semantics-safe helpers

Best for:
- Financial/regulatory modules
- High-risk accounting logic

Tradeoff:
- More implementation complexity and lower initial dev speed

### Strategy 2: Bounded Equivalence Contract (faster, bounded risk)

- Define accepted behavior envelope by domain
- Allow tolerances where legally/operationally acceptable
- Focus strict parity only on critical fields

Best for:
- Non-regulated modules
- Analytics/reporting transformations

Tradeoff:
- Requires explicit governance and risk acceptance

### Strategy 3: Hybrid Tiered Contract

- Tier A (critical amounts): strict emulation
- Tier B (operational but non-critical): bounded equivalence
- Tier C (derived/reporting): pragmatic equivalence

## Contract Elements (Minimum)

- Data type mapping table (PIC -> runtime type)
- Rounding and scale rules per operation class
- Overflow/underflow behavior policy
- Null/blank coercion policy
- Comparison semantics (including signed zero and string-number coercions)

## Validation Requirements

- Golden vector suite for edge cases
- Property-based numeric fuzzing for critical operations
- Differential tests against legacy outputs before equivalence claims

## Open Questions

- Which module families should be Tier A by default?
- Can any customer legally accept bounded equivalence on money fields?
