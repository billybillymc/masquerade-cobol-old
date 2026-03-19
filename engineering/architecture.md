# Engineering Architecture

## 1. What This Is

Masquerade is a Python-based COBOL intelligence engine. It parses COBOL source
trees, builds a dependency graph, extracts business rules and data flows, and
supports differential testing between original COBOL and modern Python
reimplementations.

The system is a Python monolith — not a multi-service architecture. The design
below documents the actual modules and their responsibilities as implemented.

---

## 2. Module Map

### 2.1 Parsing (`cobol_parser.py`, `bms_parser.py`, `jcl_parser.py`)

**`cobol_parser.py`** — 1200-line recursive-descent parser for COBOL-85/2002.
Extracts:
- Divisions, sections, paragraphs with line spans
- Copybook `COPY` references (with `REPLACING`)
- `CALL`, `PERFORM`, `EXEC CICS` targets
- `SELECT` file controls and `FD` record layouts
- Data items: level numbers, PIC clauses, `REDEFINES`, `OCCURS`, `VALUE`
- Conditional blocks and decision points (for cyclomatic complexity)

**`bms_parser.py`** — Parses BMS map definitions. Builds a `ScreenFlowIndex`
mapping mapsets to fields, programs, and screen navigation edges.

**`jcl_parser.py`** — Parses JCL job streams. Produces a `JclIndex` of job
steps, DD datasets, execution order, and cross-job data flows.

---

### 2.2 Graph (`graph_context.py`, `synthesis/`)

**`graph_context.py`** — In-memory graph over parsed programs, copybooks, files,
and BMS maps. Nodes typed as `PGM`, `CPY`, `FILE`, `MAP`. Edges typed as
`CALLS`, `COPIES`, `READS_FILE`, `CICS_IO`.

Provides:
- `impact_of(node_id)` — upstream dependency walk (blast radius)
- `dependency_tree(program)` — outgoing call/copy tree
- `hub_programs()`, `leaf_programs()`, `dead_code_analysis()`
- `readiness_score(program)` — composite (isolation, simplicity, testability)
- `DataFlowIndex` — MOVE/COMPUTE/CALL USING trace per field

**`synthesis/`** — LangChain RAG pipeline:
- `chain.py` — retrieval, reranking (Cohere), streaming LLM (Gemini), query loop
- `prompts.py` — structured prompt templates for spec, rules, and Q&A modes
- `ingest.py` — chunks COBOL source + graph metadata → Pinecone

---

### 2.3 Analysis (`analyze.py`, `complexity.py`, `copybook_dict.py`)

**`analyze.py`** — Orchestrates full-codebase analysis: parse all `.cbl` files,
build graph, extract data flows, compute complexity, write `_analysis/` artifacts.

**`complexity.py`** — Cyclomatic complexity per program and paragraph (decision
point counting).

**`copybook_dict.py`** — Builds a searchable field dictionary from all `.cpy`
files in a codebase.

---

### 2.4 Generation (`skeleton_generator.py`, `test_generator.py`, `spec_generator.py`)

**`skeleton_generator.py`** — Generates typed Python, Java, and C# module stubs
from parsed COBOL structure. Uses a language-neutral `IRModule` intermediate
representation with pluggable renderers.

**`test_generator.py`** — Generates scenario-based pytest suites from COBOL
decision trees (conditional blocks → test cases).

**`spec_generator.py`** — Generates structured Markdown specs for each program
(inputs, outputs, data flows, business rules) from graph + parsed data.

**`api_contract_mapper.py`** — Maps BMS screens to Pydantic request/response
schemas and FastAPI route stubs.

**`repository_mapper.py`** — Maps CICS file operations (READ, WRITE, DELETE) to
typed repository interfaces.

---

### 2.5 Differential Testing (`differential_harness.py`, `cobol_runner.py`)

**`differential_harness.py`** — Core differential engine.
- `DiffVector` dataclass: inputs, expected outputs, actual outputs, field types
- `run_vectors(vectors)` → `DiffReport` with per-field pass/fail and confidence score
- `CobolDecimal` — faithful COBOL numeric type (PIC precision, silent overflow, sign)

**`cobol_runner.py`** — Compiles and executes COBOL via GnuCOBOL in WSL.
Handles Windows→WSL path conversion, file assignments, and output capture.

---

### 2.6 CLI and Web (`cli.py` + submodules, `web_dashboard.py`)

**`cli.py`** — Interactive REPL entry point. Dispatches to:
- `cli_graph.py` — graph commands: `/impact`, `/deps`, `/hotspots`, `/isolated`,
  `/summary`, `/readiness`, `/dead`, `/files`
- `cli_data.py` — data commands: `/dict`, `/screens`, `/jobs`, `/trace`, `/xref`
- `cli_generate.py` — generation commands: `/spec`, `/rules`, `/spec-gen`,
  `/skeleton`, `/test-gen`, `/export`, `/report`, `/eval`, `/complexity`, `/estimate`

**`web_dashboard.py`** — Flask app serving a local analysis dashboard.

---

### 2.7 Reimplementations (`reimpl/`)

Python reimplementations of COBOL programs, organized as a package. Each module
mirrors one COBOL program using dataclasses for record layouts and dependency
injection for file I/O (repository pattern). All numeric fields use `Decimal`.

| Scope | Programs |
|---|---|
| CardDemo batch | `cbact01c`–`cbact04c`, `cbexport`, `cbimport`, `cbtrn01c`–`cbtrn03c`, `cbstm03a/b`, `cbcus01c` |
| CardDemo online (CICS) | `cocrdslc`, `cocrdupc`, `cocrdlic`, `cobil00c`, `cotrn00c`–`cotrn02c`, `coactupc`, `coactvwc`, `coadm01c`, `comen01c`, `corpt00c`, `cousr00c`–`cousr03c`, `cobswait` |
| Sign-on | `cosgn00c` |
| Utilities | `csutldtc` (date validation / CEEDAYS wrapper) |
| Shared data | `carddemo_data` (copybook dataclasses) |
| Other codebases | `star_trek`, `taxe_fonciere`, `cbsa_dbcrfun` |

---

## 3. Data Flow (Analysis Run)

```
COBOL source (.cbl, .cpy)
        │
        ▼
  cobol_parser.py          → per-program AST dict
        │
        ▼
  analyze.py               → _analysis/*.json artifacts
        │
   ┌────┴────┐
   ▼         ▼
graph_context   synthesis/ingest.py → Pinecone vectors
   │
   ├── readiness scores
   ├── complexity
   ├── dead code
   └── data flows
```

---

## 4. Infrastructure

| Component | Technology |
|---|---|
| COBOL execution | GnuCOBOL 3.x via WSL (Ubuntu) |
| Vector store | Pinecone |
| Embedding model | OpenAI text-embedding-ada-002 |
| Generation LLM | Google Gemini |
| Reranking | Cohere |
| Observability | LangSmith |
| Web UI | Flask (local only) |

All API credentials are loaded from `pipeline/.env` (excluded from version
control — see `.gitignore`).

---

## 5. Key Design Constraints

- **No fabrication**: all semantic claims must cite source file + line span.
- **COBOL numeric fidelity**: `CobolDecimal` preserves PIC scale, sign, and
  silent left-truncation overflow — not Python `float`.
- **Repository pattern**: reimplementations use injected interfaces for all I/O,
  making them unit-testable without a CICS runtime.
- **Differential as ground truth**: Python behaviour is only trusted once a
  `DiffVector` suite confirms equivalence against compiled COBOL output.

---

## 6. What Was Planned But Not Built

The `MVP_PRD.md` and earlier drafts of this file described a multi-service
architecture (Java/Kotlin parser service, Neo4j graph DB, Next.js frontend,
TypeScript policy gateway). None of that was implemented. The directories
`services/`, `packages/sdk/`, and `infra/` exist as empty placeholders.

The current Python monolith covers the full analysis, generation, and testing
surface described in the IQ checklist and README.
