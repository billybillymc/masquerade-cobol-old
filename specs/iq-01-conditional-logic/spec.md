# IQ-01: Conditional Logic Extraction — Design Specification

**Status**: In Progress  
**Created**: 2026-03-15  
**Prerequisite for**: IQ-04 (Business Rule Extraction), IQ-05 (Behavioral Tests)

---

## Problem Statement

The COBOL parser (`pipeline/cobol_parser.py`) extracts PERFORM targets, CALL
targets, CICS operations, and data flows — but **ignores all branching logic**.
`IF … ELSE … END-IF`, `EVALUATE … WHEN … END-EVALUATE`, `GO TO`, and inline
`PERFORM … END-PERFORM` loops are not captured. This means every generated
skeleton method body is a flat stub with no business logic, and no downstream
consumer (spec generator, test generator, LLM rule extractor) has access to the
actual decision structure of the program.

### Evidence

`COSGN00C.cbl` lines 221–257 contain:
```
EVALUATE WS-RESP-CD
    WHEN 0
        IF SEC-USR-PWD = WS-USER-PWD → route admin/regular
        ELSE → "Wrong Password" error
    WHEN 13 → "User not found" error
    WHEN OTHER → "Unable to verify" error
END-EVALUATE
```

The generated skeleton (`cosgn00c.py`) reduces this to:
```python
# CICS READ(WS-USRSEC-FILE)
# TODO: Replace with database operation
# CICS XCTL()
# TODO: Replace with service call
```

All business logic — password comparison, RESP code handling, admin vs regular
routing, error messages — is lost.

---

## Design Decisions

### DD-01: Full decision tree with statement bodies

**Choice**: Capture the complete decision tree — predicates AND the statements
inside each branch (MOVE, PERFORM, CALL, CICS, nested conditionals).

**Alternatives considered**:
- *Predicates only*: Capture just condition text and block type. Cheaper but
  insufficient — knowing there's an IF without knowing what each branch does
  doesn't help reimplementation.

**Reasoning**: The whole point of IQ-01 is to make the business logic available
to skeleton generation, test generation, and LLM rule extraction. Without
statement bodies, downstream consumers still can't determine what the program
does inside each branch. The body doesn't need to be a fully parsed AST; it's a
list of recognized statement nodes (MOVE, PERFORM, CALL, CICS, nested
conditionals) that reuses existing parser dataclasses.

**Intended outcome**: A reimplementing developer (or code generator) can walk
the decision tree and see "when RESP = 0 and password matches, set these fields
and transfer to COADM01C; when RESP = 13, set error message and redisplay".

---

### DD-02: Structured predicates from the start

**Choice**: Parse predicates into structured `Predicate` objects with `left`,
`operator`, `right`, and `AND`/`OR`/`NOT` combinators.

**Alternatives considered**:
- *Raw text*: Store conditions as strings, e.g. `"EIBCALEN = 0"`. Simpler but
  pushes parsing work to every downstream consumer and limits code generation.

**Reasoning**: Structured predicates enable direct translation to modern
conditions (`if eibcalen == 0`, `match ws_resp_cd`), LLM-free test case
generation (branch on each predicate value), and field-level impact analysis
(which fields appear in conditions). The COBOL condition grammar is finite and
well-documented — operators are `=`, `>`, `<`, `>=`, `<=`, `NOT =`, `NUMERIC`,
`ALPHABETIC`, `SPACES`, `ZEROS`, plus `AND`/`OR`/`NOT` combinators and
level-88 condition names. This is tractable without a full parser.

**Intended outcome**: Each predicate is a tree of `Predicate` nodes that can be
walked, translated to target language conditions, or used to generate test case
inputs.

**Caveat**: Complex expressions (arithmetic in conditions, nested FUNCTION
calls) will fall back to `raw_text` when structured parsing fails. Every
`Predicate` node carries the original `raw_text` as a fallback. We parse what
we can and degrade gracefully.

---

### DD-03: EVALUATE as its own block type

**Choice**: Model EVALUATE as a distinct `EvaluateBlock` with a `subject` field
and a list of `WhenBranch` entries, rather than normalizing to if/else-if.

**Alternatives considered**:
- *Normalize to if/else-if*: Convert every EVALUATE to equivalent nested IFs.
  Simpler downstream model but loses the pattern — a `match`/`switch` in the
  target language is more readable than a chain of `elif`.

**Reasoning**: EVALUATE maps directly to `match` (Python 3.10+), `switch`
(Java/C#), or `case/when` (Ruby). Preserving the EVALUATE structure enables
idiomatic target-language generation. The `subject` field captures what's being
evaluated (`EIBAID`, `WS-RESP-CD`, `TRUE` for boolean-style). The ALSO variant
(multi-subject) is represented as a list of subjects.

**Intended outcome**: `EVALUATE WS-RESP-CD WHEN 0 ... WHEN 13 ... WHEN OTHER`
becomes an `EvaluateBlock(subjects=["WS-RESP-CD"], branches=[WhenBranch("0", ...),
WhenBranch("13", ...), WhenBranch("OTHER", ...)])` that a Java renderer can
emit as `switch (wsRespCd) { case 0: ... case 13: ... default: ... }`.

---

### DD-04: GO TO — context-dependent representation

**Choice**: GO TO appears both as a statement node in the conditional block list
(when it appears inside a branch body, like `GO TO COMMON-RETURN` inside an IF)
AND as a `goto_targets` field on `Paragraph` (for top-level GO TOs that define
paragraph-level flow).

**Alternatives considered**:
- *Block list only*: Treat GO TO as always appearing in the conditional block
  list. But a GO TO at paragraph top level isn't a "conditional block".
- *Separate field only*: Lose the information about which branch the GO TO
  appears in, which is critical for understanding conditional flow.

**Reasoning**: GO TO is not a nested block — it's a flow control transfer. When
it appears inside an IF or EVALUATE branch, it's part of that branch's body and
must be there to understand the flow ("if condition X, jump to paragraph Y").
When it appears at paragraph top level (unconditional), it defines which
paragraph runs next and belongs in a simple `goto_targets` list. The
`GO TO ... DEPENDING ON` form is a computed jump and is represented as a
`GoTo` node with a list of targets and a `depending_on` field.

**Intended outcome**: The decision tree for `READ-USER-SEC-FILE` in COSGN00C
shows that the WHEN OTHER branch ends with a `PERFORM SEND-SIGNON-SCREEN`,
while the success branch ends with `XCTL` (a transfer). Top-level GO TOs in
star-trek programs (like `go to 1150-exit`) appear as `goto_targets` on the
paragraph.

---

### DD-05: Inline PERFORM ... END-PERFORM as conditional block

**Choice**: Capture inline `PERFORM ... END-PERFORM` (with UNTIL/VARYING
predicates and bodies) as `PerformInline` nodes in the conditional block list.

**Alternatives considered**:
- *Skip for now*: Only capture IF/EVALUATE/GO TO. Inline PERFORM is common
  in the test codebases (COUSR00C lines 294–296, 303–312) and contains
  business logic that would be lost.

**Reasoning**: Inline PERFORM loops contain iteration logic that is critical for
reimplementation. `PERFORM VARYING WS-IDX FROM 1 BY 1 UNTIL WS-IDX > 10`
translates to `for ws_idx in range(1, 11)`. `PERFORM UNTIL USER-SEC-EOF OR
ERR-FLG-ON` translates to `while not user_sec_eof and not err_flg_on`. The
UNTIL predicate and VARYING parameters are needed for the translation, and the
loop body contains the statements being iterated.

**Intended outcome**: A `PerformInline` block with `varying` (counter, from,
by), `until` predicate, and `body` statements enables direct translation to
`for`/`while` loops in the target language.

---

## Data Model

### New dataclasses

```
Predicate
├── left: str              # left operand (field name, literal, "TRUE")
├── operator: str          # "=", ">", "<", ">=", "<=", "NOT =", "NUMERIC",
│                          #  "ALPHABETIC", "SPACES", "ZEROS", "POSITIVE",
│                          #  "NEGATIVE", "AND", "OR", "NOT"
├── right: Optional[str]   # right operand (for binary ops; None for unary like NOT)
├── children: list[Predicate]  # sub-predicates for AND/OR/NOT
├── raw_text: str          # original COBOL text (always present as fallback)
└── is_88_condition: bool  # True if this is a level-88 condition name

IfBlock
├── condition: Predicate
├── then_body: list[Statement]
├── else_body: list[Statement]  # empty if no ELSE
└── span: SourceSpan

WhenBranch
├── condition: str | list[str]  # match value(s), "OTHER" for default
├── condition_predicate: Optional[Predicate]  # structured form if EVALUATE TRUE
├── body: list[Statement]
└── span: SourceSpan

EvaluateBlock
├── subjects: list[str]     # ["WS-RESP-CD"] or ["TRUE"] or multi for ALSO
├── branches: list[WhenBranch]
└── span: SourceSpan

GoTo
├── targets: list[str]      # paragraph names
├── depending_on: Optional[str]  # field name for GO TO ... DEPENDING ON
└── span: SourceSpan

PerformInline
├── varying: Optional[dict]  # {counter, from_val, by_val} for PERFORM VARYING
├── until: Optional[Predicate]  # UNTIL condition
├── body: list[Statement]
└── span: SourceSpan

Statement (union type / tagged)
├── type: str  # "IF", "EVALUATE", "GOTO", "PERFORM_INLINE", "MOVE",
│              #  "PERFORM", "CALL", "CICS", "SET", "DISPLAY", "OTHER"
├── data: IfBlock | EvaluateBlock | GoTo | PerformInline | DataFlow
│         | PerformTarget | CallTarget | CicsOperation | str
└── span: SourceSpan
```

### Modified existing dataclasses

```
Paragraph (add field)
├── ... existing fields ...
├── conditional_blocks: list[Statement]   # NEW: decision tree
└── goto_targets: list[GoTo]             # NEW: top-level GO TOs
```

### Serialization

Conditional blocks are serialized to `programs.json` under each paragraph:
```json
{
  "name": "READ-USER-SEC-FILE",
  "conditional_blocks": [
    {
      "type": "EVALUATE",
      "subjects": ["WS-RESP-CD"],
      "branches": [
        {
          "condition": "0",
          "body": [
            {
              "type": "IF",
              "condition": {"left": "SEC-USR-PWD", "operator": "=", "right": "WS-USER-PWD", "raw_text": "SEC-USR-PWD = WS-USER-PWD"},
              "then_body": [...],
              "else_body": [...]
            }
          ]
        }
      ]
    }
  ]
}
```

---

## Patterns to Extract

Based on catalog of test codebases:

| Pattern | Present In | Priority |
|---------|-----------|----------|
| Simple IF ... END-IF | carddemo, star-trek, taxe-fonciere | P1 |
| IF ... ELSE ... END-IF | carddemo, star-trek, taxe-fonciere | P1 |
| Nested IF within IF | carddemo, star-trek, taxe-fonciere | P1 |
| EVALUATE subject WHEN value | carddemo, taxe-fonciere | P1 |
| EVALUATE TRUE WHEN condition | carddemo, taxe-fonciere | P1 |
| IF with compound AND/OR/NOT | carddemo, star-trek, taxe-fonciere | P1 |
| IF with level-88 conditions | carddemo, star-trek | P1 |
| GO TO paragraph | carddemo, star-trek | P1 |
| GO TO DEPENDING ON | star-trek | P2 |
| PERFORM ... UNTIL (inline) | carddemo, star-trek | P1 |
| PERFORM VARYING (inline) | carddemo, star-trek, taxe-fonciere | P1 |
| EVALUATE ... ALSO | taxe-fonciere | P2 |
| IF nested in EVALUATE WHEN | carddemo, taxe-fonciere | P1 |

Patterns NOT found in test codebases (defer):
- SEARCH / SEARCH ALL
- ON SIZE ERROR
- AT END / NOT AT END
- INVALID KEY / NOT INVALID KEY

---

## Test Strategy

Tests use COBOL source files from `test-codebases/` as fixtures. Each test:
1. Parses a known COBOL file
2. Finds a specific paragraph by name
3. Asserts the structure of `conditional_blocks` matches expected

Primary test file: `COSGN00C.cbl` (small, well-understood, has IF, EVALUATE,
nested IF-in-EVALUATE, level-88 conditions)

Secondary: `COUSR00C.cbl` (PERFORM VARYING, PERFORM UNTIL inline, compound
conditions), `star-trek/ctrek.cob` (GO TO, GO TO DEPENDING ON, deep nesting)
