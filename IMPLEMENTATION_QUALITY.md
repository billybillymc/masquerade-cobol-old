# Implementation Quality Checklist — COBOL Reimplementation Readiness

**Purpose**: Track incremental improvements to the pipeline's ability to produce
reimplementable modern-language code from COBOL source. Each item follows
spec-driven + test-driven development: specify the behavior, write failing tests,
implement to green, then refactor.

**Status key**: `[ ]` not started · `[~]` in progress · `[x]` done

---

## IQ-01  Conditional Logic Extraction

> Extract IF/EVALUATE/GO TO/inline PERFORM structure so paragraph bodies
> contain the actual decision tree, not just a list of targets.

**Problem**: The parser captures PERFORM targets, CALL targets, and data flows,
but ignores all branching logic — `IF … ELSE … END-IF`,
`EVALUATE … WHEN … WHEN OTHER … END-EVALUATE`, `GO TO`, and
`PERFORM … UNTIL <condition>` predicates. This means every generated skeleton
method is a flat stub with no business logic.

**Evidence**: `COSGN00C.cbl` lines 221–257 contain an `EVALUATE WS-RESP-CD`
with three branches (success, not-found, error). The generated skeleton
`cosgn00c.py` reduces this to three `# CICS ...` comments.

**Deliverables**:
- [x] Spec: define `Predicate`, `IfBlock`, `EvaluateBlock`, `WhenBranch`, `GoTo`, `PerformInline`, `Statement` dataclasses (`specs/iq-01-conditional-logic/spec.md`)
- [x] Spec: define extraction rules for IF, EVALUATE, GO TO, inline PERFORM (DD-01 through DD-05)
- [x] Test: parser extracts IF/ELSE from COSGN00C MAIN-PARA (5 assertions)
- [x] Test: parser extracts EVALUATE/WHEN from COSGN00C (nested in IF, standalone, EVALUATE TRUE)
- [x] Test: EVALUATE TRUE branches have structured `condition_predicate`
- [x] Test: parser recognizes NOT + level-88 condition predicates
- [x] Test: nested IF within EVALUATE WHEN 0 branch in READ-USER-SEC-FILE (5 assertions)
- [x] Test: `raw_text` always present on every Predicate in COSGN00C (DD-02 fallback)
- [x] Test: paragraphs with no conditionals have empty `conditional_blocks`
- [x] Impl: extend `Paragraph` with `conditional_blocks: list[Statement]` and `goto_targets: list[GoTo]`
- [x] Impl: recursive descent parser for IF/EVALUATE/inline-PERFORM/GO-TO extraction
- [x] Impl: conditional blocks serialized to `programs.json` via `analyze.py`
- [x] Verify: 5 carddemo programs spot-checked (COSGN00C, COACTUPC, COTRN01C, CORPT00C, COMEN01C) — 149 tests pass, all 4 block types represented

---

## IQ-02  Wire Copybook Fields into Skeletons

> Use `copybook_dict.py` to populate dataclass stubs with actual typed fields
> instead of empty `pass` bodies.

**Problem**: `skeleton_generator._generate_dataclass_for_copybook()` produces
empty dataclasses with `TODO: Map fields from copybook definition`. The
`CopybookDictionary` already parses `.cpy` files into typed field catalogs with
PIC, USAGE, OCCURS, REDEFINES, and level-88 conditions. These two modules are
not connected.

**Evidence**: Skeleton `cosgn00c.py` has 8 copybook dataclasses, all `pass`.
`copybook_dict.py` can resolve every field in those copybooks.

**Deliverables**:
- [x] Spec: define mapping from `CopybookField` to Python dataclass field (`specs/iq-02-copybook-wiring/spec.md` DD-07)
- [x] Spec: define group/elementary hierarchy → nested dataclass or flat fields (`specs/iq-02-copybook-wiring/spec.md` DD-01)
- [x] Spec: define level-88 condition → ClassVar constants (`specs/iq-02-copybook-wiring/spec.md` DD-03)
- [x] Test: skeleton for COSGN00C copybook CSUSR01Y has typed fields (test_csusr01y_has_typed_fields)
- [x] Test: PIC X(08) → `str` field with max_length metadata (test_pic_x_produces_str_with_max_length_metadata)
- [x] Test: PIC S9(09) COMP → `int` field (test_pic_s9_comp_produces_int)
- [x] Test: PIC 9(05)V99 → `Decimal` field with scale metadata (test_pic_decimal_produces_decimal_with_scale)
- [x] Test: OCCURS clause → `list[T]` field (test_occurs_produces_list)
- [x] Test: REDEFINES → Optional with comment (test_redefines_produces_optional_with_comment)
- [x] Test: level-88 condition → ClassVar constant (test_level_88_produces_class_constants)
- [x] Impl: pass `CopybookDictionary` into skeleton generator (generate_skeleton accepts copybook_dict=)
- [x] Impl: generate typed fields from copybook catalog (_pic_to_field_metadata, _generate_nested_dataclasses)
- [x] Impl: handle group items as nested dataclasses (_build_field_hierarchy, recursive generation)
- [x] Verify: re-generate carddemo skeletons, all dataclasses populated (161 tests pass, 0 regressions)

---

## IQ-03  COBOL Numeric Semantics Module

> Provide a `CobolDecimal` (or equivalent) type that preserves PIC precision,
> scale, and overflow behavior in generated code.

**Problem**: `_pic_to_python_type()` maps PIC to `int`, `str`, or `Decimal`
without preserving the exact precision, scale, sign, or overflow rules. COBOL
arithmetic has specific intermediate precision, truncation on overflow, implied
decimal alignment, and rounding behavior that differ from Python/Java defaults.
This is the single most common source of reimplementation bugs.

**Evidence**: `PIC S9(7)V9(2) COMP-3` maps to `Decimal` but loses the constraint
that it has exactly 7 integer digits and 2 decimal places, overflows silently,
and truncates on assignment.

**Deliverables**:
- [x] Spec: define `CobolDecimal(digits, scale, signed, usage)` value type (`specs/iq-03-cobol-numeric-semantics/spec.md`)
- [x] Spec: define overflow policy — truncate-left default, raise opt-in (DD-01)
- [x] Spec: define rounding rules — truncate default, ROUND_HALF_UP opt-in (DD-02)
- [x] Spec: define null/blank coercion — SPACES/None/empty → 0 via from_display() (DD-04)
- [x] Test: CobolDecimal(5,2,signed=True) stores 999.99 correctly (test_stores_value_within_pic_range + 5 more basic tests)
- [x] Test: CobolDecimal overflow truncates per COBOL rules (test_overflow_truncates_left_digits + 4 more overflow tests)
- [x] Test: CobolDecimal addition aligns decimals before computing (test_add_different_scales_aligns + 2 more ADD/SUB tests)
- [x] Test: COMP-3 storage size matches COBOL spec (test_comp3_storage_size + 5 more storage tests)
- [x] Test: assignment from larger to smaller PIC truncates left digits (test_assign_larger_to_smaller_truncates_left + 2 more)
- [x] Test: SPACES assigned to numeric field yields zero (test_spaces_coercion_to_zero + 7 more coercion tests)
- [x] Impl: `cobol_decimal.py` module with CobolDecimal class
- [x] Impl: arithmetic ops respect intermediate precision rules (ADD/SUB/MUL/DIV with COBOL precision)
- [x] Impl: light skeleton integration — import + IQ-09 upgrade note (DD-06, deferred full integration to IQ-09)
- [x] Verify: golden vector tests against carddemo patterns (CBTRN02C balance, COPAUA0C timestamp, date reversal) — 210 tests pass, 0 regressions

---

## IQ-04  Business Rule Extraction (LLM-Assisted)

> Produce structured, evidence-anchored business rule descriptions for each
> paragraph using conditional logic + data flow + LLM interpretation.

**Problem**: The spec generator produces structural summaries ("PERFORMs X,
CALLs Y, Writes Z") but does not capture *what the paragraph does* in business
terms. A reimplementing developer needs to know "this paragraph authenticates the
user and routes admins to COADM01C" — not just that it calls XCTL twice.

**Prerequisite**: IQ-01 (conditional logic extraction)

**Evidence**: Spec for COSGN00C `READ-USER-SEC-FILE` lists CICS operations and
data flows but never mentions "authentication", "password comparison", or
"admin vs regular routing".

**Deliverables**:
- [x] Spec: define `BusinessRule` schema — claim, evidence, confidence, type (`specs/iq-04-business-rule-extraction/spec.md` DD-02)
- [x] Spec: define rule types — VALIDATION/CALCULATION/ROUTING/THRESHOLD/STATE_TRANSITION/ACCESS_CONTROL/DATA_TRANSFORM (DD-03)
- [x] Spec: define LLM prompt contract — uses existing RULES_PROMPT_TEMPLATE, parsed by `parse_llm_rules_output()` (DD-01)
- [x] Test: rule extraction for READ-USER-SEC-FILE identifies authentication logic (test_read_user_sec_file_identifies_authentication)
- [x] Test: rule extraction includes source span evidence for each claim (test_evidence_has_source_spans)
- [x] Test: rule extraction assigns confidence score with rationale (test_confidence_is_valid)
- [x] Test: rule extraction rejects fabricated claims — no hallucination (test_fabricated_evidence_rejected, test_out_of_range_lines_rejected)
- [x] Test: rules are serialized to structured JSON alongside specs (test_round_trip)
- [x] Impl: paragraph-level extraction in new module `business_rules.py` — structural tier (deterministic) + LLM parser tier (optional)
- [x] Impl: structured output parsing with validation (`parse_llm_rules_output`, `validate_evidence`)
- [x] Impl: integrates with existing RULES_PROMPT_TEMPLATE from `synthesis/prompts.py` — LLM output feeds into same `BusinessRule` schema
- [x] Verify: structural extraction tested against COSGN00C carddemo — 225 tests pass, 0 regressions

---

## IQ-05  Behavioral Test Generation with Assertions

> Generate tests that encode actual business rules and decision paths, not
> just structural presence checks.

**Problem**: Generated tests only check `hasattr` and `callable`. No test
verifies that the reimplemented code produces correct output for a given input.
Tests should encode the decision tree from the COBOL source as expected
behavior.

**Prerequisites**: IQ-01 (conditional logic), IQ-02 (copybook fields),
IQ-04 (business rules)

**Evidence**: `test_cosgn00c.py` has 16 tests; 10 are `hasattr` checks, 6 are
`# TODO` comments. None assert business behavior.

**Deliverables**:
- [x] Spec: define test categories — happy_path, error_path, decision_branch, boundary (`specs/iq-05-behavioral-tests/spec.md` DD-01)
- [x] Spec: define how conditional blocks map to test scenarios — one test per leaf branch (DD-01)
- [x] Spec: define how data contracts map to test fixtures — setup lines from copybook metadata (DD-02)
- [x] Test: generated test for COSGN00C checks successful login routes to admin (test_successful_login_scenario)
- [x] Test: generated test for COSGN00C checks wrong password returns error (test_wrong_password_scenario)
- [x] Test: generated test for COSGN00C checks user-not-found RESP 13 (test_user_not_found_scenario)
- [x] Test: generated tests have real assertions not just TODOs (test_behavioral_tests_have_real_assertions)
- [x] Test: generated tests are executable — compiles as valid Python (test_full_suite_compiles)
- [x] Impl: `_generate_behavioral_tests()` in test_generator.py — walks conditional blocks per paragraph
- [x] Impl: generate typed fixture setup from branch conditions and field names
- [x] Impl: generate assertions from MOVE targets, XCTL/CALL programs, PERFORM targets
- [x] Verify: behavioral tests increase assertion count over structural-only suite — 235 tests pass, 0 regressions

---

## IQ-06  File I/O → Repository Pattern Mapping

> Map VSAM/sequential/CICS file operations to typed repository interfaces
> instead of generic TODO comments.

**Problem**: Every file operation becomes `# TODO: Replace with database
operation`. The parser already captures `FileControl` (SELECT/ASSIGN) and
CICS file ops (READ/WRITE/DELETE with DATASET, RIDFLD, etc.). This is enough
to generate a typed repository interface.

**Evidence**: `COSGN00C` does `EXEC CICS READ DATASET(WS-USRSEC-FILE) INTO
(SEC-USER-DATA) RIDFLD(WS-USER-ID)`. This should produce
`UserSecurityRepository.find_by_id(user_id: str) -> SecUserData`.

**Deliverables**:
- [x] Spec: define mapping from CICS file ops to repository methods (`specs/iq-06-repository-mapping/spec.md` DD-01)
- [x] Spec: define mapping from sequential file I/O to iterator/stream patterns (DD-02)
- [x] Spec: define how RIDFLD/KEYLENGTH map to query parameters — `extract_cics_details()` parses source lines (DD-03)
- [x] Test: CICS READ with RIDFLD → `find_by_id(key) -> RecordType` (test_read_with_ridfld_produces_find_by_id, test_find_by_id_has_key_and_return_type)
- [x] Test: CICS WRITE → `save(record: RecordType)` (test_write_produces_save)
- [x] Test: CICS DELETE → `delete(key)` (test_delete_produces_delete)
- [x] Test: sequential input → reader with iterator, output → writer (test_sequential_input_produces_reader, test_sequential_output_produces_writer)
- [x] Test: context manager pattern in generated code (test_sequential_reader_generates_context_manager)
- [x] Test: repository uses typed record from copybook — SecUserData (test_repository_has_typed_record)
- [x] Impl: `repository_mapper.py` — RepositorySpec, FileReaderSpec, map_cics_repositories, map_sequential_files
- [x] Impl: generate_repository_code, generate_file_reader_code produce compilable Python
- [x] Verify: carddemo repos mapped — WS-USRSEC-FILE has full CRUD+browse, 14 datasets total — 249 tests pass, 0 regressions

---

## IQ-07  BMS Screen → API Contract Generation

> Map SEND MAP / RECEIVE MAP pairs to typed request/response schemas using
> the existing `bms_parser.py` output.

**Problem**: CICS screen programs have `SEND MAP` / `RECEIVE MAP` that define a
clear request/response contract. `bms_parser.py` already parses BMS maps into
fields with attributes. This isn't connected to skeleton generation — screen
operations become `# TODO: Replace with API endpoint handler`.

**Evidence**: `COSGN00C` sends/receives `COSGN0A` from mapset `COSGN00`.
`bms_parser.py` can extract the input/output fields of that map.

**Deliverables**:
- [x] Spec: define mapping from BMS map fields to request/response schemas (`specs/iq-07-bms-api-contracts/spec.md` DD-01/DD-02)
- [x] Spec: define how SEND MAP → response and RECEIVE MAP → request (DD-01/DD-02)
- [x] Spec: define attribute mapping — DRK→write_only, IC→primary_input, BRT→display_emphasis, LENGTH→max_length (DD-04)
- [x] Test: COSGN0A RECEIVE fields → request schema with USERID, PASSWD (test_receive_fields_become_request_schema)
- [x] Test: COSGN0A SEND fields → response schema with ERRMSG (test_send_fields_become_response_schema)
- [x] Test: FastAPI route stub with typed request/response (test_generates_compilable_route, test_route_has_post_endpoint)
- [x] Test: field attributes map — DRK→write_only, IC→primary, BRT→emphasis, length (4 attribute tests)
- [x] Impl: `api_contract_mapper.py` — map_screen_contracts, ApiContract, SchemaField
- [x] Impl: generate Pydantic BaseModel request/response from BMS fields
- [x] Impl: generate FastAPI route stubs with typed models
- [x] Verify: COSGN00C contract mapped — USERID+PASSWD request, ERRMSG+headers response — 264 tests pass, 0 regressions

---

## IQ-08  Multi-Language Skeleton Support

> Factor skeleton generation into a language-neutral IR with pluggable
> renderers for Python, Java, and C#.

**Problem**: `skeleton_generator.py` is hardcoded to Python. Most COBOL shops
target Java (Spring Boot) or C# (.NET). The structural mapping logic (paragraph →
method, copybook → data class, PERFORM → method call) is language-independent
but currently emits Python syntax directly.

**Deliverables**:
- [x] Spec: define language-neutral skeleton IR — IRModule, IRClass, IRField, IRMethod (`specs/iq-08-multi-language/spec.md` DD-01)
- [x] Spec: define Python renderer — @dataclass, def, self (DD-02)
- [x] Spec: define Java renderer — Spring Boot @RestController, public class, camelCase (DD-03)
- [x] Spec: define C# renderer — .NET [ApiController], namespace, PascalCase, record types (DD-04)
- [x] Test: same ProgramSpec produces valid Python skeleton (test_produces_valid_python — compiles)
- [x] Test: same ProgramSpec produces valid Java skeleton (test_has_class_declaration, test_braces_are_balanced, test_no_python_keywords)
- [x] Test: same ProgramSpec produces valid C# skeleton (test_has_namespace, test_braces_are_balanced, test_no_python_keywords)
- [x] Test: all renderers preserve paragraph→method, copybook→type mappings (TestAllRenderersParity — 3 parity tests)
- [x] Impl: `skeleton_ir.py` with `spec_to_ir()` → IRModule
- [x] Impl: `PythonRenderer` — @dataclass, typing, `__main__`
- [x] Impl: `JavaRenderer` — Spring Boot, @RestController, BigDecimal, camelCase
- [x] Impl: `CSharpRenderer` — .NET, [ApiController], record, PascalCase
- [x] Verify: 6 IR tests + 4 Python + 7 Java + 7 C# + 3 parity = 27 tests — 291 total pass, 0 regressions

---

## IQ-09  Differential Test Harness

> Run the same test vectors against COBOL golden outputs and modern
> reimplementations, producing a field-by-field equivalence report.

**Problem**: There is no way to verify that a reimplementation is behaviorally
equivalent to the original COBOL. Without this, "95% diff pass" from spec-005
cannot be measured and no confidence score is meaningful.

**Prerequisites**: IQ-03 (numeric semantics), IQ-05 (behavioral tests)

**Deliverables**:
- [x] Spec: define test vector format — vector_id, inputs, expected_outputs, field_types (`specs/iq-09-differential-harness/spec.md` DD-01)
- [x] Spec: define golden output mode — JSON at `_analysis/golden_vectors/{program}.json` (DD-04)
- [x] Spec: define field-by-field comparator with CobolDecimal tolerance (DD-02)
- [x] Spec: define diff report format — JSON + human-readable text (DD-03)
- [x] Test: identical outputs → pass (test_identical_strings_pass, test_identical_integers_pass)
- [x] Test: numeric difference within tolerance → pass (test_numeric_same_pic_value_passes — 123.456 vs 123.45 under PIC V99)
- [x] Test: numeric difference outside tolerance → fail with evidence (test_numeric_difference_outside_pic_fails)
- [x] Test: string difference → fail with expected vs actual (test_string_difference_fails, test_trailing_spaces_trimmed)
- [x] Test: confidence score computed from pass rate (test_all_pass_gives_100_confidence, test_one_fail_reduces_confidence)
- [x] Impl: `differential_harness.py` — run_vectors, compare_fields, DiffReport
- [x] Impl: golden output loader — save_golden_vectors / load_golden_vectors (JSON round-trip)
- [x] Impl: field-by-field comparator — CobolDecimal for numerics, trailing-space trim for strings
- [x] Impl: diff report generator — generate_report (JSON) + render_report_text (human-readable)
- [x] Verify: 15 tests — 306 total pass, 0 regressions

---

## IQ-10  Symbol Table and Scope Resolution

> Build a proper symbol table that resolves hierarchical field references
> (`FIELD OF GROUP`) and tracks REDEFINES unions.

**Problem**: The parser treats all field names as flat strings. COBOL has
hierarchical scope (`ERRMSGO OF COSGN0AO` qualifies which `ERRMSGO`), and
`REDEFINES` creates type unions over the same memory. Without a symbol table,
data flow analysis produces false edges when two copybooks define fields with
the same name, and qualified references are not resolved.

**Deliverables**:
- [x] Spec: define `SymbolTable` with hierarchical lookup (`specs/iq-10-symbol-table/spec.md` DD-01)
- [x] Spec: define qualified name resolution — `resolve(name, qualifier)` (DD-02)
- [x] Spec: define REDEFINES as `redefines_target` on SymbolNode (DD-03)
- [x] Spec: define scope rules — section tag on each node (DD-04)
- [x] Test: unqualified SEC-USR-ID resolves to correct parent (test_unqualified_unique_resolves)
- [x] Test: qualified CUST-ADDR-COUNTRY-CD OF CUSTOMER-RECORD resolves uniquely (test_qualified_resolves_uniquely)
- [x] Test: REDEFINES entries tracked with target (test_redefines_tracked, test_redefines_children_accessible)
- [x] Test: ambiguous unqualified raises AmbiguousReferenceError (test_ambiguous_unqualified_raises)
- [x] Test: LINKAGE SECTION fields flagged (test_linkage_section_flagged)
- [x] Impl: `symbol_table.py` — SymbolTable, SymbolNode, build_symbol_table, AmbiguousReferenceError
- [x] Impl: hierarchical tree from COBOL level numbers with copybook origin + section tags
- [x] Impl: qualified resolution walks ancestor chain; ambiguous detection raises diagnostic
- [x] Verify: CUSTREC vs CVCUS01Y collision detected and resolved — 318 tests pass, 0 regressions

---

## Progress Tracker

| ID    | Title                              | Status | Tests | Impl |
|-------|------------------------------------|--------|-------|------|
| IQ-01 | Conditional Logic Extraction       | `[x]`  | 22/22 | 3/3  |
| IQ-02 | Wire Copybook Fields into Skeletons| `[x]`  | 12/12 | 3/3  |
| IQ-03 | COBOL Numeric Semantics Module     | `[x]`  | 49/49 | 3/3  |
| IQ-04 | Business Rule Extraction (LLM)     | `[x]`  | 15/15 | 3/3  |
| IQ-05 | Behavioral Test Generation         | `[x]`  | 10/10 | 3/3  |
| IQ-06 | File I/O → Repository Mapping      | `[x]`  | 14/14 | 3/3  |
| IQ-07 | BMS Screen → API Contract          | `[x]`  | 15/15 | 3/3  |
| IQ-08 | Multi-Language Skeleton Support     | `[x]`  | 27/27 | 4/4  |
| IQ-09 | Differential Test Harness          | `[x]`  | 15/15 | 4/4  |
| IQ-10 | Symbol Table and Scope Resolution  | `[x]`  | 12/12 | 3/3  |

**Recommended order**: IQ-01 → IQ-02 → IQ-03 → IQ-10 → IQ-06 → IQ-07 →
IQ-04 → IQ-05 → IQ-08 → IQ-09

**Rationale**: IQ-01 (conditional logic) unblocks everything downstream.
IQ-02 (copybook wiring) is low-effort/high-impact since `copybook_dict.py`
already exists. IQ-03 (numeric semantics) is needed before any correctness
testing. IQ-10 (symbol table) improves data flow fidelity before we build on
it. IQ-06 and IQ-07 are self-contained wins. IQ-04 and IQ-05 depend on
earlier items. IQ-08 is a refactor. IQ-09 is the capstone.
