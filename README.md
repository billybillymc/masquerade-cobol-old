# Masquerade — COBOL-to-Python Reimplementation Engine

Masquerade parses legacy COBOL systems, uses LLM-powered analysis to extract their business logic, and helps you reimplement them in Python with verified behavioral equivalence.

It combines **static analysis** (parsing, dependency graphs, typed skeleton generation) with **LLM-powered intelligence** (RAG-based Q&A, semantic business rule extraction, reimplementation spec generation) so you can understand what COBOL code does, generate typed Python skeletons, and **prove** your reimplementation matches the original through differential testing.

## Designed for AI Coding Agents

Masquerade is built to be operated by a coding agent (Claude Code, Cursor, Copilot, etc.) as much as by a human. The entire pipeline produces structured, machine-readable artifacts that agents consume naturally:

- **`programs.json`** — full structural AST that an agent can query to understand any program
- **`graph.json`** — dependency graph an agent uses to trace impact and find reimplementation targets
- **Spec-driven workflow** — every feature has a specification in `specs/` that an agent follows as a contract
- **`READ_THIS_LAST.md`** — a step-by-step workflow guide that works as an agent prompt: analyze → explore → pick target → generate skeleton → reimplement → test → verify
- **Deterministic test suites** — 560 tests that an agent runs after every change to catch regressions immediately
- **Evidence contract** — every claim is anchored to source line spans, giving agents grounded context instead of hallucination-prone summaries

The typical workflow: point your coding agent at a COBOL codebase, tell it to follow the guide, and it will analyze the system, pick reimplementation targets, generate skeletons, write Python reimplementations, and verify them — with you reviewing at each step.

## Why This Exists

There are 220 billion lines of COBOL still running in production — at banks, insurers, and government agencies. Most of it is undocumented, untested, and written by people who have long since retired.

The hard problem isn't generating modern code. LLMs can do that passably. The hard problem is **proving the modern code does the same thing**. COBOL arithmetic is weird (silent overflow, implicit decimal points, left-truncation). Control flow is weird (PERFORM THRU, GO TO, fall-through paragraphs). Data is weird (REDEFINES unions, OCCURS DEPENDING ON, packed decimal).

Masquerade gives you the tools to understand, reimplement, and verify — not just translate.

## What You Get

### Offline Analysis (no API keys needed)

| Capability | What it does |
|-----------|-------------|
| **COBOL Parser** | Recursive-descent parser for COBOL-85/2002. Extracts paragraphs, conditionals, data flows, CICS operations, copybook references — the full structural AST. |
| **Dependency Graph** | Cross-program CALL/COPY/FILE dependency graph with readiness scores, hub detection, dead code analysis. |
| **Python Skeletons** | Typed `@dataclass` stubs generated from copybook definitions. PIC clauses become `str`, `int`, or `Decimal` fields with enforced metadata. |
| **Structural Business Rules** | Deterministic rule extraction from conditional blocks using field-name pattern matching. No LLM needed. |
| **Behavioral Tests** | pytest suites generated from the COBOL decision tree — one test per branch, not `hasattr` stubs. |
| **CobolDecimal** | A Python type that faithfully reproduces COBOL numeric semantics: PIC precision, silent overflow, left-truncation, COMP-3 storage. The most common source of reimplementation bugs, solved. |
| **Differential Harness** | Field-by-field equivalence checking between COBOL outputs and your Python reimplementation, with CobolDecimal-aware comparison and confidence scoring. |
| **Repository Mapping** | CICS file operations (READ/WRITE/DELETE/BROWSE) mapped to typed Python repository interfaces. |
| **API Contracts** | BMS screen maps converted to Pydantic request/response schemas with FastAPI route stubs. |

### LLM-Powered Intelligence (requires API keys)

| Capability | What it does |
|-----------|-------------|
| **RAG Q&A** | Ask natural-language questions about any COBOL codebase. Uses Pinecone vector search + Cohere reranking + Google Gemini to answer with source citations. "Where do we calculate late fees?" → grounded answer with file:line evidence. |
| **Semantic Business Rules** | LLM-assisted extraction that goes beyond pattern matching — identifies authentication flows, routing logic, and domain constraints with evidence validation and anti-hallucination guards. |
| **Reimplementation Specs** | Full specification documents generated from structural analysis + RAG context: purpose, inputs/outputs, business rules, data contracts, control flow, and reimplementation notes. |
| **Impact Analysis** | Change impact assessment using dependency graph + LLM interpretation. "If I change this copybook field, what breaks?" |
| **Interactive CLI** | REPL with 20+ commands: `/spec`, `/rules`, `/impact`, `/hotspots`, `/isolated`, `/dict`, `/trace`, and more. |

## Quick Start

### Install

```bash
git clone https://github.com/billybillymc/masquerade-cobol.git
cd masquerade-cobol
pip install -r pipeline/requirements.txt
```

Requires Python 3.11+. Parsing, graph building, skeleton generation, and differential testing work offline. For LLM-powered features (RAG Q&A, semantic rules, specs), configure API keys in a `.env` file:

```bash
# pipeline/.env
GOOGLE_API_KEY=...        # Google Gemini (primary LLM — gemini-2.5-flash)
OPENAI_API_KEY=...        # OpenAI (embeddings — text-embedding-3-small)
PINECONE_API_KEY=...      # Pinecone (vector database for RAG retrieval)
COHERE_API_KEY=...        # Cohere (optional — reranking, degrades gracefully)
```

### 1. Analyze a COBOL Codebase

```bash
cd pipeline
python analyze.py ../test-codebases/carddemo
```

This produces `_analysis/` with:
- `programs.json` — per-program structural AST
- `graph.json` — full dependency graph
- `stats.json` — summary statistics
- `call_graph.dot` — Graphviz visualization

### 2. Explore the Dependency Graph

```python
from graph_context import GraphIndex

idx = GraphIndex("../test-codebases/carddemo/_analysis")

# Find safe reimplementation targets (leaf programs, no downstream callers)
for name in idx.leaf_programs()[:10]:
    print(name)

# Check readiness scores (higher = easier to reimplement)
for name, score in sorted(
    [(p, idx.readiness_score(p)) for p in idx.leaf_programs()],
    key=lambda x: x[1], reverse=True
)[:10]:
    print(f"  {score:.0f}  {name}")
```

### 3. Generate a Python Skeleton

```python
from spec_generator import generate_program_spec
from skeleton_generator import generate_skeleton
from copybook_dict import CopybookDictionary

idx = GraphIndex("../test-codebases/carddemo/_analysis")
programs = json.loads(open("../test-codebases/carddemo/_analysis/programs.json").read())
cbd = CopybookDictionary("../test-codebases/carddemo")

spec = generate_program_spec("COSGN00C", idx, programs, "../test-codebases/carddemo")
skeleton = generate_skeleton(spec, cbd)
print(skeleton)
# Produces a Python file with:
#   - Typed @dataclass for each copybook (PIC X -> str, PIC 9V99 -> Decimal)
#   - Method stubs per paragraph with CICS operation comments
#   - Repository interface stubs for file operations
```

### 4. Extract Business Rules

```python
from business_rules import extract_structural_rules

rules = extract_structural_rules("COSGN00C", programs["COSGN00C"])
for r in rules:
    print(f"[{r.rule_type}] {r.claim}")
    # [ROUTING] Routes based on WS-RESP-CD with 3 branches...
    # [ACCESS_CONTROL] When SEC-USR-PWD = WS-USER-PWD matches...
```

### 5. Use CobolDecimal for Faithful Arithmetic

```python
from cobol_decimal import CobolDecimal
from decimal import Decimal

# PIC S9(10)V99 — 10 integer digits, 2 decimal places, signed
balance = CobolDecimal(digits=10, scale=2, signed=True)
balance.set(Decimal("5000.00"))

debit = CobolDecimal(digits=10, scale=2, signed=True)
debit.set(Decimal("3500.75"))

result = balance.subtract(debit)
print(result.value)  # 1499.25

# Overflow silently truncates (COBOL default — no ON SIZE ERROR)
small = CobolDecimal(digits=3, scale=0, signed=False)
small.set(12345)
print(small.value)  # 345 (left-truncated to fit PIC 9(3))
```

### 6. Verify Your Reimplementation

```python
from differential_harness import DiffVector, run_vectors, render_report_text

vectors = [
    DiffVector(
        vector_id="V001",
        program="MY-PROGRAM",
        inputs={"WS-DATE-IN": "20260315"},
        expected_outputs={"WS-DATE-OUT": "03/15/2026"},
        actual_outputs={"WS-DATE-OUT": "03/15/2026"},  # from your Python reimplementation
        field_types={"WS-DATE-OUT": "str"},
    ),
]
report = run_vectors(vectors)
print(render_report_text(report))
# Confidence: 100.0%
```

## Included Test Codebases

Masquerade ships with 5 real COBOL codebases (273 programs, 96K lines of code) for testing and learning:

| Codebase | What it is | Programs | Lines |
|----------|-----------|----------|-------|
| **carddemo** | AWS CardDemo — credit card management with CICS online + batch processing | 31 | 33K |
| **cbsa** | IBM CICS Banking Sample — accounts, customers, debit/credit, transfers | 29 | 27K |
| **star-trek** | 1979 Star Trek game — deep GO TO nesting, PERFORM VARYING | 1 | 1.6K |
| **taxe-fonciere** | French property tax calculation — EVALUATE ALSO, complex fee logic | 6 | 4.5K |
| **cobolcraft** | A Minecraft 1.21.4 server written entirely in COBOL | 206 | 30K |

## Included Python Reimplementations

37 COBOL programs have been fully reimplemented in Python with differential test suites in `pipeline/reimpl/`. These serve as reference examples for how to approach reimplementation:

| Codebase | Reimplemented | What's covered |
|----------|--------------|----------------|
| **AWS CardDemo** | All 31 programs | Sign-on, menus, accounts, cards, transactions, billing, reports, batch processing |
| **IBM CBSA** | DBCRFUN | Debit/credit engine |
| **Star Trek** | Full game | Complete 1,615-line game logic |
| **Taxe Fonciere** | EFITA3B8 | Full property tax fee calculation (669 lines) |
| **CobolCraft** | uuid, json-parse | UUID handling and full JSON token parser |

## Running Tests

```bash
# All pipeline tests (parser, graph, specs, skeletons, CobolDecimal, etc.)
python -m pytest pipeline/tests/ -v
# 502 tests

# All reimplementation differential tests
python -m pytest pipeline/reimpl/ -v
# 58 tests

# Everything
python -m pytest pipeline/tests/ pipeline/reimpl/ -v
# 560 tests, all passing
```

## Architecture

```
COBOL Source (.cbl, .cpy, .bms, .jcl)
    |
    v
[cobol_parser.py] -----> Structural AST (paragraphs, data flows, conditionals)
    |
    v
[analyze.py] -----------> programs.json + graph.json + stats.json
    |
    +---> [graph_context.py] ------> Dependency graph (callers, readiness, dead code)
    +---> [copybook_dict.py] ------> Typed field catalog (PIC, USAGE, OCCURS)
    +---> [bms_parser.py] ---------> Screen layouts and field attributes
    |
    v
[spec_generator.py] ----> Program specifications (complexity, readiness, patterns)
    |
    +---> [skeleton_generator.py] -> Python skeletons with typed copybook fields
    +---> [test_generator.py] -----> Behavioral pytest suites from decision trees
    +---> [business_rules.py] -----> Evidence-anchored business rules (structural + LLM)
    +---> [cobol_decimal.py] ------> Faithful COBOL numeric semantics
    +---> [repository_mapper.py] --> CICS file ops -> typed repository interfaces
    +---> [api_contract_mapper.py] > BMS screens -> Pydantic + FastAPI
    +---> [symbol_table.py] -------> Qualified field resolution
    +---> [differential_harness.py] > Equivalence verification
    |
    v
[synthesis/chain.py] ---> LLM-powered RAG pipeline
    |                      (Pinecone vectors + Cohere rerank + Gemini LLM)
    +---> Natural-language Q&A with source citations
    +---> Semantic business rule extraction
    +---> Reimplementation spec generation
    +---> Impact analysis
    |
    v
[cli.py] --------------> Interactive REPL (20+ commands)
[web_dashboard.py] -----> Flask web UI for exploration
```

## Pipeline Modules

### Core Analysis

| Module | What it does |
|--------|-------------|
| `cobol_parser.py` | Recursive-descent parser for COBOL-85/2002. Extracts paragraphs, PERFORM/CALL/CICS targets, data flows, and full conditional logic (IF/EVALUATE/GO TO/inline PERFORM). |
| `analyze.py` | Orchestrates parsing across a codebase. Produces `programs.json`, `graph.json`, `stats.json`. |
| `graph_builder.py` | Builds the dependency graph with CALL, COPY, FILE, CICS_IO edges. |
| `graph_context.py` | Fast dependency lookups: callers, callees, transitive deps, readiness scores, dead code detection. |
| `copybook_dict.py` | Parses `.cpy` files into a searchable typed field catalog (PIC, USAGE, OCCURS, REDEFINES, level-88). |
| `bms_parser.py` | Parses BMS screen maps into field definitions with attributes. |
| `jcl_parser.py` | JCL job/step/DD parser for batch orchestration. |

### Code Generation

| Module | What it does |
|--------|-------------|
| `skeleton_generator.py` | Generates Python skeletons with typed copybook dataclasses. Nested groups become nested `@dataclass`, OCCURS becomes `list[T]`, REDEFINES becomes `Optional[T]`. |
| `cobol_decimal.py` | Faithful COBOL arithmetic: silent left-truncation, ROUND_HALF_UP, COMP/COMP-3 storage sizes, SPACES-to-zero coercion. |
| `business_rules.py` | Two-tier rule extraction: deterministic structural analysis + optional LLM tier with anti-hallucination validation. |
| `test_generator.py` | Generates behavioral pytest suites from the COBOL decision tree. Each branch produces a test scenario with setup, assertions, and category. |
| `repository_mapper.py` | Maps CICS file operations to typed repository interfaces: READ -> `find_by_id`, WRITE -> `save`, DELETE -> `delete`, BROWSE -> iterator. |
| `api_contract_mapper.py` | Maps BMS screens to Pydantic request/response schemas and FastAPI route stubs. |
| `symbol_table.py` | Hierarchical symbol table with qualified name resolution (`FIELD OF GROUP OF RECORD`) and ambiguous reference detection. |
| `differential_harness.py` | Field-by-field equivalence checking with CobolDecimal-aware numerics and confidence scoring. |

### LLM-Powered Analysis

| Module | What it does |
|--------|-------------|
| `synthesis/chain.py` | LCEL RAG pipeline: embed query -> Pinecone vector search -> graph expansion (1-hop neighbors) -> Cohere reranking -> copybook resolution -> Google Gemini generation. Streaming support. |
| `synthesis/prompts.py` | Prompt templates for Q&A, impact analysis, business rule extraction, and reimplementation spec generation. All enforce source citation and evidence grounding. |
| `cli.py` | Interactive REPL with 20+ commands across graph analysis, data exploration, and LLM-powered generation. |
| `web_dashboard.py` | Flask web UI for interactive codebase exploration. |

## Known Parser Limitations

| Limitation | Impact | What to do |
|-----------|--------|-----------|
| Free-format COBOL (GnuCOBOL style) | Paragraph extraction fails; COPY graph still works | Accept partial parse, use dependency graph + manual source reading |
| Nested programs (multiple IDENTIFICATION DIVISION per file) | Only last program detected | Split files or accept partial extraction |
| `ANY LENGTH` / `EXTERNAL` clauses | Parsed but type info lost | Annotate manually in reimplementation |
| CICS EXEC blocks | Identified but not deep-parsed | Use stub injection for testing |

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
    skeleton_generator.py      # Python skeleton generator
    cobol_decimal.py           # COBOL numeric semantics
    test_generator.py          # Test suite generator
    business_rules.py          # Business rule extraction
    repository_mapper.py       # File I/O repository mapping
    api_contract_mapper.py     # BMS to API contract mapping
    differential_harness.py    # Equivalence verification
    symbol_table.py            # Hierarchical field resolution
    complexity.py              # Cyclomatic complexity analysis
    jcl_parser.py              # JCL job parser
    cli.py                     # Interactive REPL (20+ commands)
    web_dashboard.py           # Flask web dashboard
    synthesis/
      chain.py                 # RAG pipeline (Pinecone + Gemini + Cohere)
      prompts.py               # LLM prompt templates
    ingestion/
      chunker.py               # Code chunking for embeddings
      embedder.py              # OpenAI embedding generation
      uploader.py              # Pinecone vector upload
    tests/                     # 502 pipeline tests
    reimpl/                    # 37 reimplemented programs + 58 tests
  test-codebases/              # 5 real COBOL systems (273 programs, 96K LOC)
  specs/                       # Feature specifications (agent-consumable contracts)
  docs/
    FEATURES.md                # Detailed feature documentation
    DESIGN.md                  # Design decisions and architecture rationale
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, how to add new codebase support, and how to contribute reimplementations.

## License

MIT License. See [LICENSE](LICENSE).

Test codebases have their own licenses (CardDemo is Apache 2.0 from AWS).
