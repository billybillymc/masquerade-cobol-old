# How to Reimplement a COBOL Program in Python

This is a step-by-step guide for using Masquerade to reimplement a COBOL program as verified Python. Follow the steps in order.

**For coding agents**: This guide is designed to work as an agent prompt. Point your agent (Claude Code, Cursor, Copilot, etc.) at this file and it will follow the workflow: analyze, explore the graph, pick targets, generate skeletons, write reimplementations, and verify with differential tests. Every step produces structured, machine-readable artifacts the agent can consume.

---

## Step 1 — Add Your COBOL Codebase

Place your COBOL source under `test-codebases/<name>/`:

```bash
git clone --depth=1 <repo-url> test-codebases/<name>
```

The parser handles `.cbl`, `.cob`, `.cpy`, `.bms` files automatically. It targets fixed-format IBM/mainframe COBOL (COBOL-85/2002) with standard column layout.

**What's supported**: standard column layout, CICS EXEC blocks, JCL, BMS screen maps, COMP/COMP-3/BINARY-LONG types.

**What's not fully supported**: free-format COBOL (GnuCOBOL extensions), nested programs, vendor-specific extensions like `ANY LENGTH`.

---

## Step 2 — Analyze

```bash
cd pipeline
python analyze.py ../test-codebases/<name>
```

This produces `test-codebases/<name>/_analysis/` with:
- `programs.json` — per-program structural AST (paragraphs, data flows, conditionals)
- `graph.json` — dependency graph (CALL, COPY, FILE edges)
- `stats.json` — summary statistics
- `call_graph.dot` — Graphviz visualization

---

## Step 3 — Pick a Program to Reimplement

Use the dependency graph to find good starting targets:

```python
import json
from pathlib import Path
from graph_context import GraphIndex

codebase = Path('../test-codebases/<name>')
idx = GraphIndex(str(codebase / '_analysis'))
programs = json.loads((codebase / '_analysis/programs.json').read_text())

# Leaf programs (no downstream callers — safe to reimplement first)
for name in idx.leaf_programs()[:20]:
    print(name)

# Readiness scores (higher = more structure extracted, easier to reimplement)
scores = [(p, idx.readiness_score(p)) for p in programs]
scores.sort(key=lambda x: x[1].get('score', 0) if isinstance(x[1], dict) else x[1], reverse=True)
for name, score in scores[:10]:
    s = score.get('score', score) if isinstance(score, dict) else score
    print(f'  {s:.2f}  {name}')
```

**Pick programs that are:**
1. Leaf programs (no downstream callers — no cascading breakage)
2. High readiness score (parser extracted enough structure)
3. Clear inputs/outputs (batch programs with sequential I/O are easiest)
4. Interesting business logic (something worth demonstrating)

---

## Step 4 — Generate a Specification

```python
from spec_generator import generate_program_spec

spec = generate_program_spec("MY-PROGRAM", idx, programs, str(codebase))
print(spec.complexity_grade, spec.readiness_score, spec.migration_wave)
```

The spec tells you the program's complexity grade, what it calls, what data it touches, and how hard it will be to reimplement.

**Tip**: Graph node IDs are uppercase and hyphenated (`MY-PROGRAM`, not `My-Program`). Find the right ID with:
```python
[k for k in idx.nodes if 'MYNAME' in k.upper()]
```

---

## Step 5 — Generate a Python Skeleton

```python
from skeleton_generator import generate_skeleton
from copybook_dict import CopybookDictionary

cbd = CopybookDictionary(str(codebase))
skeleton = generate_skeleton(spec, cbd)
print(skeleton)
```

The skeleton includes:
- Typed `@dataclass` for each copybook (PIC X -> `str`, PIC 9 -> `int`, PIC 9V99 -> `Decimal`)
- Method stubs per paragraph with CICS/file operation comments
- Repository interface stubs for VSAM/sequential file operations

---

## Step 6 — Extract Business Rules

### Structural extraction (offline, no API keys)

```python
from business_rules import extract_structural_rules

rules = extract_structural_rules("MY-PROGRAM", programs["MY-PROGRAM"])
for r in rules:
    print(f'[{r.rule_type}] conf={r.confidence}  {r.claim}')
```

### LLM-powered extraction (requires API keys — deeper semantic understanding)

If you have API keys configured (see README), use the CLI for richer rule extraction:

```bash
cd pipeline
python cli.py
# Inside the REPL:
/switch <name>
/rules MY-PROGRAM
```

The LLM tier uses Google Gemini with RAG context to identify business rules that pattern matching misses — authentication flows, domain-specific routing, implicit constraints. All outputs go through anti-hallucination validation: claims without matching source evidence are rejected.

Rule types: `VALIDATION`, `CALCULATION`, `ROUTING`, `THRESHOLD`, `STATE_TRANSITION`, `ACCESS_CONTROL`, `DATA_TRANSFORM`.

---

## Step 6b — Ask Questions About the Code (LLM-powered)

With API keys configured, use the CLI to ask natural-language questions:

```bash
/switch <name>
> Where do we calculate late fees?
> What happens when a credit card transaction is posted?
> How does the sign-on process work?
```

Every answer cites sources as `file_path:start_line-end_line`. The RAG pipeline retrieves relevant code chunks, expands with graph neighbors (callers, callees, shared copybooks), reranks, and generates a grounded answer.

## Step 6c — Generate a Reimplementation Spec (LLM-powered)

```bash
/spec MY-PROGRAM
```

Produces a full specification document: purpose, inputs/outputs, business rules with evidence, data contracts, dependencies, control flow summary, and reimplementation notes (suggested patterns, type mappings, edge cases).

---

## Step 7 — Write Your Reimplementation

Create `pipeline/reimpl/<program_name>.py`. Convert the COBOL program name to Python snake_case: `MY-PROGRAM` -> `my_program.py`.

Use this structure:

```python
"""
Reimplementation of <PROGRAM-ID>.

COBOL source: test-codebases/<name>/path/to/file.cob
  Program-ID: <PROGRAM-ID> (lines N-M)

Signature (LINKAGE SECTION):
  LK-INPUT    PIC X(N)    -- description
  LK-OUTPUT   PIC 9(N)    -- description
  LK-FAILURE  BINARY-CHAR -- 0 = OK, non-zero = error

Logic:
  1. <paragraph 1 description>
  2. <paragraph 2 description>
"""
from __future__ import annotations
from dataclasses import dataclass
from cobol_decimal import CobolDecimal
from decimal import Decimal

@dataclass
class Result:
    ...

def run(input_value: str) -> Result:
    ...
```

Use `CobolDecimal` for any numeric fields where COBOL's truncation/overflow behavior matters. This is the most common source of reimplementation bugs.

---

## Step 8 — Write Differential Tests

Create `pipeline/reimpl/test_<program_name>.py`:

```python
import pytest
from <program_name> import run, Result

class TestMyProgram:
    def test_happy_path(self):
        """Mirrors EVALUATE WHEN 'OK' branch in MAIN-PARA (line N)."""
        result = run("valid-input")
        assert result.output == "expected"

    def test_missing_required_field(self):
        """Mirrors IF LK-FIELD = SPACES -> MOVE 1 TO LK-FAILURE (line N)."""
        result = run("")
        assert result.failure != 0

    def test_boundary_value(self):
        """Mirrors WHEN OTHER -> fallback logic."""
        ...
```

**Cover these for each program:**
- [ ] Happy path (normal input)
- [ ] Missing/blank required inputs
- [ ] Each branch of the main EVALUATE/IF
- [ ] Boundary values (min, max, zero, empty)
- [ ] Error paths (failure flag set)
- [ ] Realistic domain data

Run: `python -m pytest pipeline/reimpl/test_<program_name>.py -v`

---

## Step 9 — Verify with the Differential Harness

For programs where you have COBOL golden outputs (from running the original):

```python
from differential_harness import DiffVector, run_vectors, render_report_text

vectors = [
    DiffVector(
        vector_id="V001",
        program="MY-PROGRAM",
        inputs={"WS-INPUT": "test-value"},
        expected_outputs={"WS-OUTPUT": "expected-value"},
        actual_outputs={"WS-OUTPUT": my_reimpl_result},
        field_types={"WS-OUTPUT": "str"},
    ),
]
report = run_vectors(vectors)
print(render_report_text(report))
# Confidence: 100.0%
```

The harness uses CobolDecimal-aware comparison for numeric fields — it compares stored values under the same PIC definition, not raw Python floats.

---

## Reference: Existing Reimplementations

Look at `pipeline/reimpl/` for 40 working examples across 7 codebases. Good starting points:

| Program | File | Why it's a good example |
|---------|------|------------------------|
| cc_uuid | `cc_uuid.py` | String processing: UUID formatting, no CICS dependency |
| DBCRFUN | `cbsa_dbcrfun.py` | Calculation: debit/credit engine with CobolDecimal arithmetic |
| EFITA3B8 | `efita3b8.py` | Complex logic: French property tax with nested EVALUATE ALSO |

---

## Common Issues

**`generate_program_spec` returns None**
The program ID isn't in the graph. Graph uses uppercase+hyphenated IDs. List available programs: `[k for k in idx.nodes if k.startswith('PGM:')]`

**Parser extracts 0 paragraphs**
Your codebase is likely free-format COBOL. The parser targets fixed-format. The dependency graph still works — use it for COPY relationships and read the source manually for paragraph logic.

**`CopybookDictionary()` TypeError**
Pass the codebase directory as a string: `CopybookDictionary(str(codebase))`

**`GraphIndex()` TypeError**
Pass the analysis directory: `GraphIndex(str(codebase / '_analysis'))`
