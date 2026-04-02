# Feature Documentation

Detailed documentation for each major capability in the Masquerade pipeline.

---

## Conditional Logic Extraction

The parser extracts the full decision tree from COBOL programs: `IF/ELSE/END-IF`, `EVALUATE/WHEN/WHEN OTHER/END-EVALUATE`, `GO TO`, and `PERFORM ... UNTIL` predicates. Each paragraph's `conditional_blocks` contains structured `Statement` objects representing the branching logic.

This means generated skeletons and business rules reflect the actual decision paths, not just a flat list of CALL/PERFORM targets.

**Example**: `COSGN00C.cbl` lines 221-257 contain an `EVALUATE WS-RESP-CD` with three branches (success, not-found, error). The parser extracts all three branches with their predicates, and the skeleton generator produces corresponding method stubs.

**22 tests** covering IF, EVALUATE, EVALUATE TRUE, nested conditionals, GO TO, and inline PERFORM.

---

## Copybook Field Wiring

Skeleton generation uses the `CopybookDictionary` to populate `@dataclass` stubs with actual typed fields from `.cpy` definitions:

| COBOL PIC | Python type | Metadata |
|-----------|------------|----------|
| `PIC X(08)` | `str` | `max_length=8` |
| `PIC S9(09) COMP` | `int` | `signed=True, usage='COMP'` |
| `PIC 9(05)V99` | `Decimal` | `max_digits=5, scale=2` |
| `OCCURS 12 TIMES` | `list[T]` | `occurs=12` |
| `REDEFINES X` | `Optional[T]` | comment noting redefines target |
| Level-88 condition | `ClassVar` | boolean constant |

Nested groups become nested `@dataclass` types. This produces skeletons where the data contracts are immediately usable, not empty `pass` bodies.

**12 tests** covering all PIC-to-Python type mappings.

---

## CobolDecimal — Faithful Numeric Semantics

`CobolDecimal` is a Python type that exactly reproduces COBOL arithmetic behavior. This is the single most common source of reimplementation bugs — Python's `Decimal` and `float` do not match COBOL's rules for overflow, truncation, and intermediate precision.

**What CobolDecimal handles:**
- **Silent left-truncation on overflow**: assigning 12345 to PIC 9(3) yields 345, not an error
- **COBOL intermediate precision**: ADD/SUB use `max(d1, d2) + 1` digits; MUL uses `d1 + d2` digits
- **Truncate vs ROUND_HALF_UP rounding**: truncation is the default (matching COBOL behavior without `ROUNDED`)
- **COMP/COMP-3/DISPLAY storage byte sizes**: matches IBM mainframe storage layout
- **SPACES-to-zero coercion**: assigning SPACES to a numeric field yields 0 (COBOL standard)

**49 tests** covering precision, overflow, arithmetic operations, storage sizes, and coercion.

---

## Business Rule Extraction

Two-tier extraction that produces structured, evidence-anchored business rules:

**Structural tier** (deterministic, no LLM needed): walks conditional blocks and classifies rules by field-name patterns:
- `PWD`, `PASSWORD` fields -> `ACCESS_CONTROL`
- `RESP`, `RESP-CD` fields -> `ROUTING`
- `ERR`, `ERROR` fields -> `VALIDATION`
- Arithmetic operations -> `CALCULATION`

**LLM tier** (optional): uses a prompt template to produce rules in the same `BusinessRule` schema, with anti-hallucination validation that rejects claims without matching source line evidence.

Each rule includes: `claim` (what it does), `evidence` (source line spans), `confidence` (HIGH/MEDIUM/LOW), `rule_type` (classification).

**15 tests** including hallucination rejection tests.

---

## Behavioral Test Generation

Generates pytest suites from the COBOL decision tree. Each leaf branch in an EVALUATE/IF produces a test scenario with:
- **Setup**: field values that trigger this branch
- **Assertions**: expected MOVE targets, XCTL programs, PERFORM targets
- **Category**: happy_path, error_path, decision_branch, boundary

This produces tests that verify actual business behavior, not just structural presence (`hasattr`, `callable`).

**10 tests** verifying scenario generation and assertion quality.

---

## File I/O to Repository Mapping

Maps CICS file operations to typed Python repository interfaces:

| CICS Operation | Repository Method |
|---------------|------------------|
| `READ DATASET(...) INTO(...) RIDFLD(...)` | `find_by_id(key) -> RecordType` |
| `WRITE DATASET(...) FROM(...)` | `save(record: RecordType)` |
| `REWRITE DATASET(...)` | `update(record: RecordType)` |
| `DELETE DATASET(...)` | `delete(key)` |
| `STARTBR/READNEXT/ENDBR` | `browse() -> Iterator[RecordType]` |

Sequential files map to context manager readers/writers. The RIDFLD clause determines the key parameter type, and the INTO clause determines the return type (resolved from copybook definitions).

**14 tests** covering all CICS operations and sequential file patterns.

---

## BMS Screen to API Contract

Maps CICS screen programs to modern API contracts:

- **RECEIVE MAP** input fields (UNPROT) -> Pydantic `BaseModel` request schema
- **SEND MAP** output fields (PROT) -> Pydantic `BaseModel` response schema
- BMS attributes map to annotations: `DRK` -> `write_only`, `IC` -> `primary_input`, `BRT` -> `display_emphasis`
- Generates FastAPI route stubs with typed request/response models

**15 tests** covering field mapping, attribute translation, and route generation.

---

## Multi-Language Skeleton Support

While the primary focus is Python, the pipeline supports generating skeletons in Java and C# through a language-neutral intermediate representation (`IRModule`):

- **Python**: `@dataclass`, typing, pytest-compatible
- **Java**: Spring Boot with `@RestController`, BigDecimal, camelCase
- **C#**: .NET with `[ApiController]`, record types, PascalCase

All renderers preserve the same paragraph-to-method and copybook-to-type mappings.

**27 tests** covering all three renderers and cross-language parity.

---

## Differential Test Harness

Field-by-field equivalence checking between COBOL golden outputs and Python reimplementations:

- **Numeric comparison**: uses CobolDecimal — compares stored values under the same PIC definition, not raw Python numbers
- **String comparison**: trailing-space trimming (COBOL pads with spaces)
- **Confidence scoring**: `pass_rate * 100` across all test vectors
- **Reports**: JSON for automation + human-readable text for review

**15 tests** covering identical values, numeric tolerance, string differences, and confidence scoring.

---

## RAG-Powered Q&A

The synthesis pipeline (`synthesis/chain.py`) enables natural-language questions about any analyzed COBOL codebase:

1. **Embed** the user's question using OpenAI embeddings (with local cache)
2. **Search** Pinecone vector database for relevant code chunks
3. **Expand** results with graph neighbors (callers, callees, shared copybooks)
4. **Rerank** using Cohere (optional, degrades gracefully without API key)
5. **Resolve** copybook content inline for field-level context
6. **Generate** a grounded answer using Google Gemini with source citations

**Prompt contract**: All answers must cite sources as `file_path:start_line-end_line`. Claims without evidence are explicitly rejected ("I cannot determine this from the provided code context.").

**Models used**: Google Gemini 2.5 Flash (LLM, temperature=0.0), OpenAI text-embedding-3-small (embeddings), Cohere rerank-v3.5 (reranking, optional).

---

## Reimplementation Spec Generation

The `/spec` CLI command generates full reimplementation specifications by combining structural analysis (from the parser/graph — treated as ground truth) with RAG-retrieved code context (for behavioral understanding):

- **Purpose statement** — what the program does and its role in the system
- **Input/output contracts** — files, CICS maps, CALL parameters, copybook structures
- **Business rules** — numbered list with evidence citations and confidence levels
- **Data contracts** — copybook descriptions with key fields and roles
- **Dependencies** — each dependency with relationship type and why it's needed
- **Control flow summary** — main execution path through paragraphs with decision points
- **Reimplementation notes** — suggested modern patterns, type mappings, edge cases, what to preserve exactly

---

## Interactive CLI

The REPL (`cli.py`) provides 20+ commands organized into three categories:

**Graph commands** (`cli_graph.py`):
- `/impact <name>` — blast-radius analysis for a program or copybook
- `/deps <name>` — dependency tree visualization
- `/hotspots` — hub programs with highest change risk
- `/isolated` — leaf programs (safe reimplementation candidates)
- `/readiness <name>` — detailed readiness score breakdown
- `/dead` — dead code analysis (unreachable paragraphs, orphan programs)

**Data commands** (`cli_data.py`):
- `/dict <field>` — copybook field lookup with PIC, type, and parent info
- `/screens` — BMS screen map browser
- `/jobs` — JCL job/step viewer
- `/trace <field>` — field-level data flow tracing
- `/xref <name>` — cross-reference lookup

**Generation commands** (`cli_generate.py`):
- `/spec <program>` — LLM-powered reimplementation spec
- `/rules <program>` — LLM-powered business rule extraction
- `/skeleton <program>` — Python skeleton with typed copybook fields
- `/test-gen <program>` — behavioral test suite generation
- `/complexity <program>` — cyclomatic complexity analysis
- `/estimate <program>` — migration effort estimation

---

## Symbol Table and Scope Resolution

Resolves hierarchical COBOL field references (`FIELD OF GROUP OF RECORD`):

- Builds symbol tree from copybook level numbers
- Qualified resolution walks ancestor chains
- REDEFINES tracking (type unions over same memory)
- Section scope tags (WORKING-STORAGE, LINKAGE)
- `AmbiguousReferenceError` when an unqualified name exists in multiple copybooks

**12 tests** covering qualified resolution, REDEFINES, ambiguity detection, and scope tagging.
