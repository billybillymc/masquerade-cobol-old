# Background: Product Requirements

This document captures the original requirements and design thinking behind Masquerade. It's preserved here as context for contributors who want to understand the "why" behind the architecture.

## The Problem

Organizations maintaining legacy COBOL systems face:
- Multi-million line codebases with no reliable documentation or tests
- Critical business logic split across COBOL programs, copybooks, JCL, CICS, VSAM, and flat files
- High operational risk from small changes
- Modernization pressure with low confidence in behavioral equivalence

The core pain is not "translate one file." It is "understand an entire system well enough to change it safely."

## Design Goals

1. Parse and model IBM Enterprise COBOL end-to-end
2. Resolve copybooks and extract cross-program dependencies
3. Build an explorable dependency graph
4. Extract paragraph-level business rules in structured form
5. Provide field-level lineage tracing
6. Generate typed Python skeletons from structural analysis
7. Verify reimplementations through differential testing

## Non-Goals

- Full multi-dialect support (Micro Focus, ACUCOBOL) — contributions welcome
- Full semantic equivalence proofs for arbitrary programs
- Full CICS transaction emulation
- Fully automated code translation without human review

## Key Technical Challenges

### Numeric Semantics Mismatch
COBOL arithmetic (COMP-3, rounding, sign handling, silent overflow) differs fundamentally from Python. Solution: `CobolDecimal` encodes COBOL rules directly.

### Parser Dialect Drift
COBOL syntax differs by compiler and era. Solution: target one dialect (IBM Enterprise COBOL) well, degrade gracefully on others.

### LLM Hallucination
Plausible but incorrect business-rule explanations. Solution: evidence contract — every claim must map to source spans. Anti-hallucination validation rejects unsupported claims.

### Verified Modernization
Behavioral equivalence is harder than translation. Solution: differential test harness with CobolDecimal-aware field comparison and confidence scoring.

## Success Metrics

- Parse coverage >= 98% on IBM Enterprise COBOL
- 560 passing tests across pipeline and reimplementations
- 37 programs fully reimplemented with verified equivalence
- 5 codebases validated (273 programs, 96K LOC)
