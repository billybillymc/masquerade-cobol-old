# Masquerade COBOL Intelligence Engine

A comprehensive COBOL analysis and modernization pipeline that parses legacy COBOL systems, extracts business logic, and generates reimplementable modern-language skeletons with typed data contracts, repository interfaces, API schemas, and behavioral test suites.

## What It Does

Masquerade takes a COBOL codebase (programs, copybooks, BMS screen maps, JCL) and produces:

- **Structural analysis** (`programs.json`, `graph.json`) — full AST with paragraphs, data flows, conditional logic, CICS operations, and a dependency graph across all programs
- **Program specifications** — per-program markdown specs with complexity metrics, readiness scores, migration wave assignments, and effort estimates
- **Python/Java/C# skeletons** — typed class stubs with copybook dataclasses, repository interfaces, API contracts, and method bodies derived from paragraph structure
- **Behavioral test suites** — pytest files with scenario-based tests generated from the COBOL decision tree, not just `hasattr` stubs
- **Business rule catalogs** — structured, evidence-anchored rules extracted from conditional blocks with classification (ACCESS_CONTROL, ROUTING, VALIDATION, etc.)
- **Differential test harness** — field-by-field equivalence checking between COBOL golden outputs and modern reimplementations with CobolDecimal-aware numeric comparison

## Architecture

```
COBOL Source (.cbl, .cpy, .bms, .jcl)
    |
    v
[cobol_parser.py] -----> CobolProgram AST (paragraphs, data flows, conditionals)
    |
    v
[analyze.py] -----------> programs.json + graph.json
    |
    +---> [graph_builder.py] ------> dependency graph (call, copy, file edges)
    +---> [graph_context.py] ------> GraphIndex + DataFlowIndex (fast lookups)
    +---> [copybook_dict.py] ------> CopybookDictionary (typed field catalog)
    +---> [bms_parser.py] ---------> BmsMapset (screen layouts, field attributes)
    |
    v
[spec_generator.py] ----> ProgramSpec (complexity, readiness, patterns)
    |
    +---> [skeleton_generator.py] -> Python skeletons with typed copybook fields
    +---> [skeleton_ir.py] --------> Language-neutral IR -> Python/Java/C# renderers
    +---> [test_generator.py] -----> Structural + behavioral pytest suites
    +---> [business_rules.py] -----> BusinessRule extraction (structural + LLM tiers)
    +---> [repository_mapper.py] --> CICS file ops -> typed repository interfaces
    +---> [api_contract_mapper.py] > BMS screens -> Pydantic request/response + FastAPI routes
    +---> [symbol_table.py] -------> Hierarchical field resolution with qualified names
    +---> [cobol_decimal.py] ------> CobolDecimal with PIC precision enforcement
    +---> [differential_harness.py] > Golden vector comparison with confidence scoring
    |
    v
[synthesis/chain.py] ---> RAG pipeline (Pinecone + Gemini + Cohere reranking)
[web_dashboard.py] -----> Flask dashboard for interactive exploration
```

## Pipeline Modules

### Core Analysis

| Module | Purpose |
|--------|---------|
| `cobol_parser.py` | Recursive descent parser for COBOL-85/2002. Extracts paragraphs, PERFORM/CALL/CICS targets, data flows (MOVE/COMPUTE/ADD/etc.), and full conditional logic (IF/EVALUATE/GO TO/inline PERFORM with structured predicates). |
| `analyze.py` | Orchestrates parsing across a codebase. Produces `programs.json` (per-program AST) and `graph.json` (dependency graph). |
| `graph_builder.py` | Builds the dependency graph with CALL, COPY, FILE, CICS_IO edges between programs, copybooks, and files. |
| `graph_context.py` | `GraphIndex` for fast dependency lookups (callers, callees, transitive dependencies, readiness scores, dead code detection). `DataFlowIndex` for field-level tracing across programs. |
| `copybook_dict.py` | Parses all `.cpy` files into a searchable `CopybookDictionary` with typed fields (PIC, USAGE, OCCURS, REDEFINES, level-88 conditions). |
| `bms_parser.py` | Parses BMS map definitions into `BmsMapset` with fields, attributes (PROT/UNPROT/BRT/DRK), and screen flow graph from XCTL/LINK/RETURN TRANSID references. |
| `complexity.py` | Cyclomatic complexity, nesting depth, and complexity grading (LOW/MODERATE/HIGH/VERY HIGH). |
| `jcl_parser.py` | JCL job/step/DD statement parser for batch orchestration analysis. |

### Code Generation (IQ-01 through IQ-10)

| Module | IQ | Purpose |
|--------|----|---------|
| `skeleton_generator.py` | IQ-02 | Generates Python skeletons from ProgramSpec. Copybook dataclasses have typed fields with enforced metadata (max_length, max_digits, scale, signed, usage) instead of empty `pass` bodies. Nested groups become nested dataclasses, OCCURS becomes `list[T]`, REDEFINES becomes `Optional[T]`, level-88 becomes `ClassVar`. |
| `cobol_decimal.py` | IQ-03 | `CobolDecimal` class with faithful COBOL arithmetic: silent left-truncation on overflow, truncate/ROUND_HALF_UP rounding, COBOL-standard intermediate precision for ADD/SUB/MUL/DIV, SPACES-to-zero coercion, COMP/COMP-3/DISPLAY storage byte sizes. |
| `business_rules.py` | IQ-04 | Two-tier business rule extraction. **Structural tier** (deterministic): walks conditional blocks, classifies rules by field-name patterns (PWD->ACCESS_CONTROL, RESP->ROUTING, ERR->VALIDATION). **LLM tier** (optional): parses `RULES_PROMPT_TEMPLATE` output into the same `BusinessRule` schema. Anti-hallucination via evidence span validation. |
| `test_generator.py` | IQ-05 | Generates pytest suites with **behavioral tests** from the COBOL decision tree. Each leaf branch in an EVALUATE/IF produces a test scenario with setup (field values), assertions (MOVE targets, XCTL programs), and category (happy_path, error_path, decision_branch). |
| `repository_mapper.py` | IQ-06 | Maps CICS file operations to typed repository interfaces: READ->find_by_id, WRITE->save, REWRITE->update, DELETE->delete, STARTBR/READNEXT/ENDBR->browse. Extracts INTO/RIDFLD from source lines for typed record returns. Sequential files map to context manager readers/writers. |
| `api_contract_mapper.py` | IQ-07 | Maps BMS SEND MAP/RECEIVE MAP to Pydantic request/response schemas and FastAPI route stubs. Input fields (UNPROT) become request fields, output fields (PROT) become response fields. BMS attributes map to validation annotations (DRK->write_only, IC->primary_input, BRT->display_emphasis). |
| `skeleton_ir.py` | IQ-08 | Language-neutral `IRModule` intermediate representation with pluggable renderers. `PythonRenderer` emits @dataclass/typing, `JavaRenderer` emits Spring Boot with @RestController, `CSharpRenderer` emits .NET with [ApiController] and record types. |
| `differential_harness.py` | IQ-09 | Field-by-field equivalence checking between COBOL golden outputs and reimplementations. CobolDecimal-aware numeric comparison (same PIC = same stored value), trailing-space trimming for strings, confidence scoring (pass_rate * 100). JSON + human-readable diff reports. |
| `symbol_table.py` | IQ-10 | Hierarchical symbol table from copybook fields. Qualified name resolution (`FIELD OF GROUP OF RECORD`), REDEFINES tracking, section scope tags (WORKING-STORAGE, LINKAGE), ambiguous reference detection with `AmbiguousReferenceError`. |

### RAG and Synthesis

| Module | Purpose |
|--------|---------|
| `synthesis/chain.py` | LCEL RAG pipeline: embed query -> Pinecone vector search -> graph expansion (1-hop neighbors) -> dedup -> Cohere reranking -> copybook resolution -> Gemini LLM generation. Streaming support. |
| `synthesis/prompts.py` | Prompt templates for RAG Q&A, impact analysis, business rule extraction, and reimplementation spec generation. |
| `spec_generator.py` | Generates `ProgramSpec` with complexity metrics, readiness scores, modern pattern inference (REST API for CICS, event-driven for batch), migration wave assignment, and effort estimation. |

### Presentation

| Module | Purpose |
|--------|---------|
| `web_dashboard.py` | Flask web dashboard for interactive codebase exploration. |
| `render_html.py` | HTML report generation. |
| `render_report.py` | Markdown/text report rendering. |
| `export.py` | Export analysis artifacts. |
| `cli.py` | Command-line interface for all pipeline operations. |

## Test Codebases

The pipeline is tested against three real COBOL codebases:

| Codebase | Description | Programs | Copybooks |
|----------|-------------|----------|-----------|
| **carddemo** | AWS CardDemo — credit card management system with CICS online programs, batch processing, BMS screens, VSAM files | 44 programs | 29 copybooks, 21 BMS maps |
| **star-trek** | Classic Star Trek game in COBOL — deep nesting, GO TO, PERFORM VARYING | 1 program | - |
| **taxe-fonciere** | French property tax calculation — EVALUATE ALSO, complex computation | 1 program | - |

## Quick Start

### Prerequisites

- Python 3.11+
- Dependencies: `pip install -r pipeline/requirements.txt`

### Analyze a COBOL Codebase

```bash
cd pipeline
python analyze.py ../test-codebases/carddemo
```

This produces `_analysis/` with:
- `programs.json` — per-program structural AST (44 programs)
- `graph.json` — full dependency graph (1059 nodes, 2146 edges)
- `stats.json` — summary statistics
- `call_graph.dot` — Graphviz visualization

### Generate Skeletons

```python
from skeleton_generator import generate_all_skeletons
results = generate_all_skeletons("../test-codebases/carddemo")
# Produces _analysis/skeletons/*.py with typed copybook fields
```

### Generate Multi-Language Skeletons

```python
from skeleton_ir import spec_to_ir, PythonRenderer, JavaRenderer, CSharpRenderer
from spec_generator import generate_program_spec

spec = generate_program_spec("COSGN00C", graph, program_data, codebase_dir)
ir = spec_to_ir(spec)

python_code = PythonRenderer().render(ir)
java_code = JavaRenderer().render(ir)
csharp_code = CSharpRenderer().render(ir)
```

### Extract Business Rules

```python
from business_rules import extract_structural_rules
import json

programs = json.loads(open("_analysis/programs.json").read())
rules = extract_structural_rules("COSGN00C", programs["COSGN00C"])
for r in rules:
    print(f"[{r.rule_type}] {r.claim}")
    # [ROUTING] Routes based on WS-RESP-CD with 3 branches...
    # [ACCESS_CONTROL] When SEC-USR-PWD = WS-USER-PWD matches...
```

### Run the Differential Harness

```python
from differential_harness import TestVector, run_vectors, render_report_text

vectors = [
    TestVector(
        vector_id="V001",
        program="CODATE01",
        inputs={"WS-DATE-IN": "20260315"},
        expected_outputs={"WS-DATE-OUT": "03/15/2026"},
        actual_outputs={"WS-DATE-OUT": "03/15/2026"},  # from reimplementation
        field_types={"WS-DATE-OUT": "str"},
    ),
]
report = run_vectors(vectors)
print(render_report_text(report))
# Confidence: 100.0%
```

### Use CobolDecimal for Faithful Arithmetic

```python
from cobol_decimal import CobolDecimal
from decimal import Decimal

# PIC S9(10)V99 — 10 integer digits, 2 decimal places, signed
balance = CobolDecimal(digits=10, scale=2, signed=True)
balance.set(Decimal("5000.00"))

debit = CobolDecimal(digits=10, scale=2, signed=True)
debit.set(Decimal("3500.75"))

result = balance.subtract(debit)  # Intermediate: max(10,10)+1=11 digits, scale=2
print(result.value)  # 1499.25

# Overflow silently truncates (COBOL default — no ON SIZE ERROR)
small = CobolDecimal(digits=3, scale=0, signed=False)
small.set(12345)
print(small.value)  # 345 (left-truncated)
```

### Map CICS Operations to Repositories

```python
from repository_mapper import map_cics_repositories, generate_repository_code

repos = map_cics_repositories("COSGN00C", programs["COSGN00C"],
                               source_dir="test-codebases/carddemo/app/cbl")
for repo in repos:
    print(generate_repository_code(repo))
    # class WsUsrsecFileRepository:
    #     def find_by_id(self, ws_user_id: str) -> Optional[SecUserData]:
    #         ...
```

### Resolve Qualified Field References

```python
from symbol_table import build_symbol_table, AmbiguousReferenceError
from copybook_dict import CopybookDictionary

cbd = CopybookDictionary("test-codebases/carddemo/app/cpy")
st = build_symbol_table(["CUSTREC", "CVCUS01Y"], cbd)

# Qualified resolution
node = st.resolve("CUST-ADDR-COUNTRY-CD", qualifier="CUSTOMER-RECORD")
print(node.fully_qualified_name())  # CUST-ADDR-COUNTRY-CD.CUSTOMER-RECORD

# Ambiguous detection
try:
    st.resolve("CUST-ADDR-COUNTRY-CD")  # exists in both copybooks
except AmbiguousReferenceError as e:
    print(e)  # Ambiguous reference: found in 2 locations
```

## Running Tests

```bash
# From repo root
python -m pytest pipeline/tests/ -v

# 318 tests, all passing
# Covers: parser, graph, specs, skeletons, copybook wiring, CobolDecimal,
#         business rules, behavioral tests, repositories, API contracts,
#         multi-language IR, differential harness, symbol table
```

## Implementation Quality Checklist

All 10 implementation quality items are complete. Each followed spec-driven + test-driven development (specify, write failing tests, implement to green, verify no regressions).

| ID | Title | Tests | Status |
|----|-------|-------|--------|
| IQ-01 | Conditional Logic Extraction | 22 | Done |
| IQ-02 | Wire Copybook Fields into Skeletons | 12 | Done |
| IQ-03 | COBOL Numeric Semantics Module | 49 | Done |
| IQ-04 | Business Rule Extraction (LLM-Assisted) | 15 | Done |
| IQ-05 | Behavioral Test Generation | 10 | Done |
| IQ-06 | File I/O to Repository Mapping | 14 | Done |
| IQ-07 | BMS Screen to API Contract | 15 | Done |
| IQ-08 | Multi-Language Skeleton Support | 27 | Done |
| IQ-09 | Differential Test Harness | 15 | Done |
| IQ-10 | Symbol Table and Scope Resolution | 12 | Done |

See [IMPLEMENTATION_QUALITY.md](IMPLEMENTATION_QUALITY.md) for detailed deliverables, design decisions, and evidence references per item.

## Project Structure

```
masquerade-cobol/
  pipeline/
    analyze.py                 # Codebase analysis orchestrator
    cobol_parser.py            # COBOL structural parser
    graph_builder.py           # Dependency graph construction
    graph_context.py           # Graph/data flow indexes
    copybook_dict.py           # Copybook field catalog
    bms_parser.py              # BMS screen map parser
    spec_generator.py          # Program specification generator
    skeleton_generator.py      # Python skeleton generator (IQ-02)
    skeleton_ir.py             # Multi-language IR + renderers (IQ-08)
    test_generator.py          # Test suite generator (IQ-05)
    cobol_decimal.py           # COBOL numeric semantics (IQ-03)
    business_rules.py          # Business rule extraction (IQ-04)
    repository_mapper.py       # File I/O repository mapping (IQ-06)
    api_contract_mapper.py     # BMS to API contract mapping (IQ-07)
    differential_harness.py    # Golden vector comparison (IQ-09)
    symbol_table.py            # Hierarchical field resolution (IQ-10)
    complexity.py              # Cyclomatic complexity analysis
    effort_estimator.py        # Migration effort estimation
    jcl_parser.py              # JCL job parser
    cli.py                     # Command-line interface
    web_dashboard.py           # Flask web dashboard
    synthesis/
      chain.py                 # RAG pipeline (Pinecone + Gemini)
      prompts.py               # LLM prompt templates
    ingestion/
      chunker.py               # Code chunking for embeddings
      embedder.py              # OpenAI embedding generation
      scanner.py               # Codebase file scanner
      uploader.py              # Pinecone vector upload
    tests/                     # 318 tests across 19 test files
  specs/
    001-006/                   # Feature specifications
    iq-01 through iq-10/       # Implementation quality specs
  test-codebases/
    carddemo/                  # AWS CardDemo (44 COBOL programs)
    star-trek/                 # Star Trek game in COBOL
    taxe-fonciere/             # French property tax system
  IMPLEMENTATION_QUALITY.md    # IQ checklist with full deliverables
```

## Design Principles

- **Spec-driven development**: Every feature starts with a specification documenting design decisions with reasoning and alternatives considered
- **Test-driven development**: Red-green-refactor strictly — failing tests before implementation, minimum code to pass, then refactor
- **LLM evidence contract**: Every claim needs a source reference — no hallucinated behavior
- **Faithful COBOL semantics**: `CobolDecimal` preserves exact PIC precision, overflow, and truncation behavior rather than approximating with Python defaults
- **Incremental enrichment**: Each IQ item builds on prior work (IQ-01 conditional blocks feed IQ-04 business rules feed IQ-05 behavioral tests)
- **No API keys required for core analysis**: Static analysis, skeleton generation, and test generation work entirely offline. RAG synthesis is optional.

## License

MIT License. See [LICENSE](LICENSE).

Test codebases have their own licenses: CardDemo is Apache 2.0 (AWS).
