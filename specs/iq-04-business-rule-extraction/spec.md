# IQ-04: Business Rule Extraction (LLM-Assisted) — Design Specification

**Status**: In Progress
**Created**: 2026-03-15
**Prerequisites**: IQ-01 (conditional logic extraction)
**Prerequisite for**: IQ-05 (behavioral test generation)

---

## Problem Statement

The spec generator produces structural summaries ("PERFORMs X, CALLs Y, Writes Z")
but does not capture *what the paragraph does* in business terms. A reimplementing
developer needs to know "this paragraph authenticates the user and routes admins
to COADM01C" — not just that it calls XCTL twice.

### Evidence

Spec for COSGN00C `READ-USER-SEC-FILE` lists CICS operations and data flows but
never mentions "authentication", "password comparison", or "admin vs regular
routing".

Source: `test-codebases/carddemo/_analysis/skeletons/cosgn00c.py` lines 153–165.

IQ-01 gave us the full decision tree for this paragraph (EVALUATE WS-RESP-CD with
nested IF on SEC-USR-PWD). This structural data is sufficient to auto-identify
rule types deterministically, and serves as the evidence anchor for LLM enrichment.

---

## Design Decisions

### DD-01: Two-tier extraction — structural baseline + LLM enrichment

**Choice**: Two extraction tiers:
1. **Structural extraction** (deterministic, no LLM): Walks conditional blocks
   from IQ-01 and classifies rules by pattern matching on field names, operators,
   and block structure. Always available, fast, testable.
2. **LLM-assisted extraction** (optional): Feeds paragraph context to the existing
   `RULES_PROMPT_TEMPLATE` for richer human-readable descriptions. Optional —
   requires API keys. Validates against structural baseline.

**Reasoning**: Structural extraction provides the testable, deterministic foundation.
Every IQ-04 test can run in CI without API keys. The LLM layer adds interpretation
richness but must anchor every claim to a structurally-identified decision point.

---

### DD-02: BusinessRule and Evidence schema

**Choice**:
```python
@dataclass
class Evidence:
    file: str
    start_line: int
    end_line: int
    code_text: str        # actual COBOL statements
    block_type: str       # IF / EVALUATE / COMPUTE / PERFORM / MOVE / etc.

@dataclass
class BusinessRule:
    rule_id: str          # "{PROGRAM}.{PARAGRAPH}.R{N}"
    claim: str            # plain-language description
    evidence: list[Evidence]
    confidence: str       # HIGH / MEDIUM / LOW / REJECTED
    rule_type: str        # VALIDATION / CALCULATION / ROUTING / THRESHOLD /
                          # STATE_TRANSITION / ACCESS_CONTROL / DATA_TRANSFORM
    paragraph: str
    program: str
    uncertainty: str      # caveats, missing context
```

---

### DD-03: Rule type taxonomy (matches existing prompt)

VALIDATION | CALCULATION | ROUTING | THRESHOLD | STATE_TRANSITION |
ACCESS_CONTROL | DATA_TRANSFORM

Structural auto-classification patterns:
- `IF ... PWD/PASSWORD/USR/USER ... = ...` → ACCESS_CONTROL
- `EVALUATE RESP-CD / EIBAID / WS-RESP` → ROUTING
- `COMPUTE / ADD / SUBTRACT / MULTIPLY / DIVIDE` → CALCULATION
- `IF ... STATUS / FLAG / VALID / ERR ...` → VALIDATION
- `MOVE ... TO ... STATUS / STATE / FLAG / TYPE` → STATE_TRANSITION
- `IF ... > / < / >= / <= ... (numeric threshold)` → THRESHOLD
- `STRING / UNSTRING / MOVE with transformation` → DATA_TRANSFORM

---

### DD-04: Anti-hallucination via evidence validation

Every BusinessRule must have at least one Evidence span that:
1. References a file that exists (or existed at parse time)
2. Has a line range within the file's bounds
3. Corresponds to a conditional block or data flow in the parsed AST

Rules failing validation get `confidence='REJECTED'` with a reason string.

---

### DD-05: Tests work without API keys

- Structural extraction tests: real .cbl files, deterministic
- LLM output parsing tests: pre-recorded output strings
- Anti-hallucination test: fabricated evidence → REJECTED
- Full integration test: `@pytest.mark.skipif` without API keys

---

### DD-06: Rules serialized to _analysis/rules/{program}.json

Separate from programs.json to avoid bloat and allow re-extraction without
re-parsing.

---

## Implementation Plan

### New module: `pipeline/business_rules.py`

1. `BusinessRule` and `Evidence` dataclasses
2. `extract_structural_rules(program_id, program_data) -> list[BusinessRule]`
   — walks conditional_blocks for each paragraph, classifies by pattern
3. `parse_llm_rules_output(raw_text, program, paragraph) -> list[BusinessRule]`
   — parses RULES_PROMPT_TEMPLATE output into BusinessRule objects
4. `validate_evidence(rule, source_file) -> BusinessRule`
   — validates evidence spans, sets REJECTED if invalid
5. `extract_rules_for_program(program_id, program_data, source_dir) -> list[BusinessRule]`
   — orchestrates structural extraction + optional LLM enrichment
6. `save_rules(rules, output_dir)` / `load_rules(program, rules_dir)`
   — JSON serialization to `_analysis/rules/`

### Changes to existing modules

None required for core functionality. The module reads from programs.json
(already produced by analyze.py) and writes to _analysis/rules/.

### Test file: `pipeline/tests/test_business_rules.py`
