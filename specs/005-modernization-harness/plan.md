# Implementation Plan: Modernization Pilot + Differential Test Harness

**Branch**: `005-modernization-harness` | **Date**: 2026-03-14 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/005-modernization-harness/spec.md`

## Summary

Build the modernization pilot: generate modern-language candidates (Java default, Python optional) for scoped COBOL modules, auto-generate test vectors from COBOL logic, run differential execution (legacy vs generated), and enforce a four-gate HITL validation pipeline. Numeric semantics use strict emulation (BigDecimal) for migration-ready modules; bounded-equivalence permitted only in sandbox mode. Diff pass target ≥ 95%.

## Technical Context

| Dimension | Value |
|-----------|-------|
| **Languages** | Python (validation-harness), Java (generated code execution) |
| **Primary Dependencies** | 001 parser, 002 graph, 003 semantic pipeline, 004 lineage; LLM for candidate generation |
| **Target Languages** | Java (default), Python (optional) |
| **Numeric Semantics** | Strict emulation with BigDecimal; PIC-to-runtime mapping documented |
| **Test Vector Types** | Golden vectors (edge cases), property-based numeric fuzzing (sandbox) |
| **HITL Gates** | Exploration → Candidate Generation → Differential Test → Readiness |
| **Minimum Approvers** | Modernization Engineer + Domain SME + Risk/Controls Owner |
| **Diff Pass Target** | ≥ 95% for advancement to Differential Test Gate |
| **Testing** | pytest (harness), JUnit (generated Java), integration tests on CardDemo |
| **Constraints** | Block generation for modules failing Exploration Gate; legacy stub mode when COBOL cannot execute |
| **Scale** | CardDemo modules for MVP; validated modernization percentage metric |

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Evidence-Grounded Analysis | PASS | Generated candidates link constructs to source spans; semantic mappings traceable |
| II. Test-First Development | PASS | TDD for test vector generation, differential harness, confidence score, gates |
| III. Verified Modernization | PASS | Differential execution is the verification mechanism; diff pass ≥ 95% gates advancement |
| IV. Graceful Degradation | PASS | Legacy stub/golden output mode when COBOL cannot run; compilation failure reported |
| V. Structured Outputs with Provenance | PASS | Confidence score, mismatch reports, gate approvals include evidence and audit fields |
| VI. Resumable and Idempotent Pipelines | PASS | Differential runs idempotent; gate state persisted |
| VII. Single Dialect Focus | N/A | Inherits from 001 |

## Project Structure

### Documentation (this feature)

```text
specs/005-modernization-harness/
├── plan.md              # This file
├── tasks.md             # Actionable task breakdown
├── checklists/
│   └── requirements.md
├── contracts/           # API contracts for harness, gates
└── numeric-semantics.md # Numeric semantics contract (PIC, rounding, overflow, etc.)
```

### Source Code (repository root)

```text
services/validation-harness/
├── src/
│   ├── candidate/
│   │   ├── generator.py           # Modern candidate generation (Java/Python)
│   │   ├── exploration_gate.py    # Exploration Gate evaluation
│   │   └── semantic_mapping.py    # PIC→type, paragraph→method mapping
│   ├── test_vectors/
│   │   ├── generator.py           # Auto-generate from COBOL logic
│   │   ├── golden_vectors.py      # Edge case vectors
│   │   └── property_fuzz.py       # Property-based numeric fuzzing (sandbox)
│   ├── differential/
│   │   ├── harness.py             # Run legacy vs generated, diff outputs
│   │   ├── legacy_runner.py       # Legacy COBOL or stub execution
│   │   └── generated_runner.py    # Java/Python execution
│   ├── numeric/
│   │   ├── semantics_contract.py  # PIC mapping, rounding, overflow, null/blank
│   │   └── bigdecimal_emulation.py # Strict emulation for Java
│   ├── gates/
│   │   ├── hitl_pipeline.py       # Four-gate pipeline
│   │   ├── approval_store.py      # Audit log for approvals
│   │   └── gate_evaluator.py      # Gate pass/fail logic
│   └── api/
│       └── harness_api.py         # HTTP endpoints
├── tests/
│   ├── test_candidate_generator.py
│   ├── test_test_vector_generator.py
│   ├── test_differential_harness.py
│   ├── test_numeric_semantics.py
│   ├── test_hitl_gates.py
│   └── integration/
│       └── test_carddemo_harness.py
├── pyproject.toml
└── README.md

generated/                               # Output directory for generated code
├── java/                                # Generated Java candidates
└── python/                              # Generated Python candidates (optional)

packages/schemas/
├── scoped-module.schema.json
├── modern-candidate.schema.json
├── test-vector.schema.json
├── differential-run.schema.json
├── mismatch.schema.json
├── confidence-score.schema.json
└── gate.schema.json
```

## Phase 0: Research

**Duration**: 1 day  
**Output**: `specs/005-modernization-harness/research.md` (optional)

1. **COBOL-to-Java mapping**: Document PIC 9/V/COMP-3 → Java BigDecimal/Integer mapping; identify edge cases (overflow, rounding, null/blank coercion).
2. **Legacy execution options**: Evaluate options when mainframe runtime unavailable—golden output recording, GnuCOBOL for local execution, stub mode.
3. **LLM candidate generation**: Evaluate prompt patterns for COBOL→Java translation; ensure evidence anchors in output.
4. **Property-based fuzzing**: Evaluate Hypothesis or similar for numeric fuzzing in sandbox mode.

## Phase 1: Design

**Duration**: 1–2 days  
**Output**: `numeric-semantics.md`, `contracts/`, schema definitions

1. Define numeric semantics contract: PIC-to-runtime mapping, rounding/scale rules, overflow policy, null/blank coercion, comparison semantics.
2. Define ScopedModule, ModernCandidate, TestVector, DifferentialRun, Mismatch, ConfidenceScore, Gate schemas.
3. Define Exploration Gate criteria (parse coverage, evidence quality).
4. Define test vector schema: inputs, expected output, data types, edge case category.
5. Define differential harness API: input (module, candidate, vectors), output (pass/fail, mismatches, confidence score).
6. Define HITL gate API: gate type, status, approver roles, audit log.
7. Write contract tests for schema compliance and gate transitions.

## Phase 2: Implementation

**Duration**: 4–5 days  
**Output**: Working modernization pilot with differential harness and HITL gates

### Step 1: Numeric Semantics Contract (TDD)

- Write failing tests: PIC 9(5)V99 COMP-3 maps to BigDecimal with correct scale.
- Write failing tests: rounding, overflow, null/blank coercion per contract.
- Implement `NumericSemanticsContract` and `BigDecimalEmulation`.
- Make tests green.

### Step 2: Exploration Gate (TDD)

- Write failing tests: module with insufficient parse coverage or evidence quality is blocked.
- Implement `ExplorationGate` evaluation.
- Block candidate generation for failed modules.
- Make tests green.

### Step 3: Candidate Generation (TDD)

- Write failing tests: scoped module passing Exploration Gate produces Java candidate with evidence anchors.
- Write failing tests: module failing Exploration Gate is blocked.
- Implement `CandidateGenerator` using LLM + AST/graph context.
- Implement semantic mapping (PIC→type, paragraph→method) with source-span links.
- Make tests green.

### Step 4: Test Vector Generation (TDD)

- Write failing tests: module with numeric logic produces golden vectors for edge cases.
- Write failing tests: vectors respect PIC mapping and scale rules.
- Implement `TestVectorGenerator` for golden vectors (overflow, rounding, null/blank, comparison).
- Implement optional property-based fuzzing for sandbox.
- Make tests green.

### Step 5: Differential Harness (TDD)

- Write failing tests: same vectors run against legacy and generated; outputs compared.
- Write failing tests: match → pass; mismatch → surfaced with vector, expected, actual, source evidence.
- Write failing tests: migration-ready uses strict emulation; sandbox may use bounded-equivalence.
- Implement `DifferentialHarness`, `LegacyRunner` (or stub), `GeneratedRunner` (Java execution).
- Implement diff report and mismatch surfacing.
- Make tests green.

### Step 6: Confidence Score (TDD)

- Write failing tests: confidence reflects pass rate, evidence quality, numeric coverage.
- Write failing tests: ≥ 95% pass → score meets gate threshold.
- Implement `ConfidenceScore` computation.
- Make tests green.

### Step 7: HITL Gates (TDD)

- Write failing tests: each gate requires appropriate approvals.
- Write failing tests: modules cannot bypass gates.
- Implement `HITLPipeline` with four gates.
- Implement approval store with audit log (approver role, timestamp).
- Make tests green.

### Step 8: Validated Modernization Percentage (TDD)

- Write failing tests: M/N modules migration-ready → percentage = M/N.
- Implement metric computation and reporting.
- Make tests green.

### Step 9: Integration and Edge Cases

- Implement legacy stub/golden output mode when COBOL cannot execute.
- Handle compilation failure, non-deterministic vectors, external dependency stubbing.
- End-to-end test on CardDemo module.

## Complexity Tracking

No constitution violations. Numeric semantics and HITL gates align with PRD locked decisions. Differential execution is the verification mechanism per Constitution III.
