# READ THIS LAST — Masquerade COBOL Pipeline: Complete Workflow

This document is the authoritative guide for adding a new COBOL codebase to
Masquerade from scratch: clone → analyze → explore → generate → reimplement →
test. Every step is concrete and runnable. Follow them in order.

---

## What This Project Is

Masquerade is a COBOL intelligence engine. Given any COBOL codebase it:

1. Parses all `.cbl`, `.cob`, `.cpy`, `.bms`, `.jcl` files into a structured AST
2. Builds a dependency graph (CALL, COPY, FILE, CICS_IO edges)
3. Generates specs, skeletons (Python/Java/C#), and business rule catalogs
4. Supports writing Python reimplementations verified by differential test suites

All work lives under `pipeline/`. Tests live in `pipeline/tests/`.
Reimplementations live in `pipeline/reimpl/`.

---

## Step 1 — Clone the Codebase

```bash
git clone --depth=1 <repo-url> test-codebases/<name>
```

Count files and LOC before starting:

```powershell
$files = Get-ChildItem -Recurse -Include "*.cob","*.cbl","*.cpy" test-codebases/<name>
$loc   = ($files | ForEach-Object { (Get-Content $_.FullName -Raw).Split("`n").Count } | Measure-Object -Sum).Sum
Write-Host "Files: $($files.Count)  LOC: $loc"
```

**Parser compatibility note**: The parser (`cobol_parser.py`) targets fixed-format
IBM/mainframe COBOL (COBOL-85, COBOL-2002). It handles:
- `.cbl`, `.cob`, `.cpy`, `.bms` extensions (all auto-discovered)
- Standard column layout (cols 1-6 sequence, 7 indicator, 8-11 area A, 12-72 area B)
- CICS EXEC blocks, JCL, BMS screen maps
- `BINARY-LONG`, `BINARY-LONG-LONG`, `COMP`, `COMP-3`

It does **not** fully handle:
- **Free-format COBOL** (`*>` comments, no fixed columns, GnuCOBOL extensions)
- Nested programs (`END PROGRAM` / multiple `IDENTIFICATION DIVISION` in one file)
- Vendor extensions like `ANY LENGTH`, `EXTERNAL`

CobolCraft (Minecraft server in COBOL) is an example of a free-format codebase.
The parser extracts COPY dependencies correctly but misses most paragraph structure.
This is expected — document it and proceed; COPY graph and business rules still work.

---

## Step 2 — Analyze the Codebase

```bash
cd pipeline
python analyze.py ../test-codebases/<name>
```

This produces `test-codebases/<name>/_analysis/`:
- `programs.json` — per-program AST (paragraphs, data flows, conditionals)
- `graph.json` — full dependency graph (nodes + edges)
- `stats.json` — summary statistics
- `call_graph.dot` — Graphviz visualization

**Expected output** (check these numbers make sense):
```
Artifacts written to ../test-codebases/<name>/_analysis/
  programs.json  — per-program structure (N programs)
  graph.json     — full dependency graph (N nodes, N edges)
  stats.json     — summary statistics
```

---

## Step 3 — Register the Codebase in the CLI

Edit `pipeline/cli.py` — add an entry to `KNOWN_CODEBASES`:

```python
"<name>": {
    "dir": str(_test_codebases / "<name>"),
    "label": "<Description> (N programs, NK LOC)",
    "questions": [
        "What does <key program> do?",
        "How is <core concept> calculated?",
        # ... 8-10 questions that showcase the domain
    ],
},
```

Commit: `git add pipeline/cli.py && git commit -m "Register <name> in CLI codebase menu"`

---

## Step 4 — Graph Exploration

Run graph analysis to understand the codebase structure before picking programs
to reimplement:

```python
import json
from pathlib import Path
from graph_context import GraphIndex

codebase = Path('../test-codebases/<name>')
idx      = GraphIndex(str(codebase / '_analysis'))
programs = json.loads((codebase / '_analysis/programs.json').read_text())
stats    = json.loads((codebase / '_analysis/stats.json').read_text())

# Hub programs (most depended-upon — high change risk)
for name, score in idx.hub_programs(15):
    print(f'  {score}  {name}')

# Leaf programs (no callers — safe reimplementation candidates)
for name in idx.leaf_programs()[:20]:
    print(f'  {name}')

# Readiness scores (0-100; higher = easier to reimplement)
scores = [(p, idx.readiness_score(p)) for p in programs]
scores.sort(key=lambda x: x[1].get('score', 0) if isinstance(x[1], dict) else x[1], reverse=True)
for name, score in scores[:20]:
    s = score.get('score', score) if isinstance(score, dict) else score
    print(f'  {s:.2f}  {name}')

# Dead code
dead = idx.dead_code_analysis()
# Keys: unreachable_paragraphs, orphan_programs, unused_copybooks, summary
```

**What to look for:**
- Hub programs = high copybook fan-in → complex data contracts
- Leaf programs with high readiness = best first reimplement targets
- Programs with many paragraphs + conditional blocks = most interesting business logic
- Orphan programs = utility/batch programs that run standalone (good for differential testing)

---

## Step 5 — Spec Generation

Generate a structured Markdown spec for a chosen program:

```python
from spec_generator import generate_program_spec

# NOTE: graph stores IDs as uppercase+hyphenated: 'MY-PROGRAM' not 'My-Program'
# The programs.json dict may use the original casing. Use the graph-normalized ID.
graph_id = 'MY-PROGRAM'   # must match PGM:<graph_id> node in graph.json
spec = generate_program_spec(graph_id, idx, programs, str(codebase))

if spec is None:
    print('Program not found in graph — check the node ID casing')
    # List PGM: nodes: [k for k in idx.nodes if k.startswith('PGM:')]
else:
    print(spec.complexity_grade, spec.readiness_score, spec.migration_wave)
    spec_md = spec.render_markdown() if hasattr(spec, 'render_markdown') else str(spec)
    Path('_analysis/generated/<program>.spec.md').write_text(spec_md)
```

**Tip**: Find the correct graph node ID:
```python
pgm_nodes = [k for k in idx.nodes if k.startswith('PGM:')]
# Then search: [k for k in pgm_nodes if 'MYNAME' in k.upper()]
```

---

## Step 6 — Skeleton Generation (Python / Java / C#)

```python
from skeleton_generator import generate_skeleton
from skeleton_ir import spec_to_ir, PythonRenderer, JavaRenderer, CSharpRenderer
from copybook_dict import CopybookDictionary

cbd = CopybookDictionary(str(codebase))   # loads all .cpy files

py_code   = generate_skeleton(spec, cbd)
ir        = spec_to_ir(spec)
java_code = JavaRenderer().render(ir)
cs_code   = CSharpRenderer().render(ir)
```

Skeletons include:
- Typed dataclasses from copybooks (PIC X → str, PIC 9 → int, PIC 9V99 → Decimal)
- Method stubs per paragraph with CICS/file operation comments
- Repository interface stubs for VSAM/sequential file operations
- FastAPI route stubs for BMS screen programs

---

## Step 7 — Business Rule Extraction

```python
from business_rules import extract_structural_rules

prog_data = programs['MY-PROGRAM']   # use exact key from programs.json
rules = extract_structural_rules('MY-PROGRAM', prog_data)

for r in rules:
    print(f'[{r.rule_type}] conf={r.confidence}  {r.claim}')
```

Rule types: `VALIDATION`, `CALCULATION`, `ROUTING`, `THRESHOLD`,
`STATE_TRANSITION`, `ACCESS_CONTROL`, `DATA_TRANSFORM`.

Each rule includes:
- `claim`: concise description of the inferred behavior
- `evidence`: source line spans
- `confidence`: HIGH / MEDIUM / LOW
- `rule_type`: classification

---

## Step 8 — Pick a Program to Reimplement

Pick criteria (in priority order):
1. **Readiness score ≥ 70** — parser extracted enough structure
2. **Leaf program** — no downstream callers means no cascading breakage
3. **Has clear inputs/outputs** — batch programs with sequential I/O are easiest
4. **No CICS dependency** — CICS programs need stub injection; skip for first pass
5. **Interesting business logic** — something worth demonstrating

Write the reimplementation to `pipeline/reimpl/<program_name>.py`.

**File naming**: convert COBOL program name to Python snake_case:
- `MY-PROGRAM` → `my_program.py`
- `BLOCKS-PARSE-STATE` → `blocks_parse_state.py`

**Structure template**:
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
  ...
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Result:
    ...

def run(input_value: str) -> Result:
    ...
```

---

## Step 9 — Write Differential Tests

Write tests to `pipeline/tests/test_<name>_reimpl.py`.

**Test structure**: one class per function, one test per behavior boundary.
Map each test to a specific COBOL construct it verifies:

```python
class TestMyProgram:
    def test_happy_path(self):
        """Mirrors EVALUATE WHEN 'OK' branch in MAIN-PARA (line N)."""
        result = run("valid-input")
        assert result.output == "expected"

    def test_missing_required_field(self):
        """Mirrors IF LK-FIELD = SPACES -> MOVE 1 TO LK-FAILURE (line N)."""
        with pytest.raises(ValueError):
            run("")

    def test_boundary_value(self):
        """Mirrors WHEN OTHER -> fallback logic."""
        ...
```

**Coverage checklist for each program**:
- [ ] Happy path (normal input)
- [ ] Missing/blank required inputs
- [ ] Each branch of the main EVALUATE/IF
- [ ] Boundary values (min, max, zero, empty)
- [ ] Error path (failure flag set)
- [ ] Realistic domain data (e.g. actual JSON structure)

Run: `python -m pytest tests/test_<name>_reimpl.py -v`

---

## Step 10 — Commit

```bash
git add pipeline/reimpl/<program>.py pipeline/tests/test_<name>_reimpl.py
git commit -m "Add <name> reimpl: <PROGRAM-ID> with N tests"
```

---

## Quick Reference: Codebase Registry

| Key | Label | Programs | LOC |
|-----|-------|----------|-----|
| `carddemo` | AWS CardDemo — Credit Card Processing | 44 | 30K |
| `cbsa` | IBM CICS Banking Sample Application | 29 | 27K |
| `bankdemo` | Micro Focus CICS Banking Demo | 164 | 34K |
| `legacy-benchmark` | Investment Portfolio Management | 42 | 7K |
| `star-trek` | Classic Star Trek Game | 1 | 1.6K |
| `taxe-fonciere` | French Property Tax | 6 | 2.3K |
| `cnaf` | French Family Allowances Fund | 52 | ~3.5M |
| `cobolcraft` | Minecraft Server in COBOL | 268 | 30K |

---

## Known Parser Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Free-format COBOL (GnuCOBOL style, `*>` comments) | Paragraph extraction fails; COPY graph still works | Accept partial parse; use COPY dependency graph + manual source reading |
| Nested programs (multiple `IDENTIFICATION DIVISION` per file) | Only last program detected | Split files or accept partial extraction |
| `ANY LENGTH` / `EXTERNAL` clauses | Parsed but type info lost | Annotate manually in reimpl docstring |
| Level-78 constants | Not extracted as symbols | Read from source directly |
| `BINARY-LONG-LONG`, `BINARY-SHORT` | Mapped to int | Use `int` in reimpl |
| CICS EXEC blocks | Identified but not deep-parsed | Use stub injection (see `cics_stub.py`) |

---

## Common Failure Modes

**`generate_program_spec` returns None**
→ The program ID isn't in the graph. Graph stores IDs uppercase+hyphenated.
→ List nodes: `[k for k in idx.nodes if k.startswith('PGM:')]`
→ Pass the graph-normalized ID (e.g. `'BLOCKS-PARSE-STATE'` not `'Blocks-Parse-State'`)

**`CopybookDictionary()` TypeError**
→ Requires `codebase_dir` argument: `CopybookDictionary(str(codebase))`

**`GraphIndex()` TypeError**
→ Takes `analysis_dir` string, not a raw graph dict: `GraphIndex(str(codebase / '_analysis'))`

**Parser extracts 0 paragraphs from all programs**
→ Codebase is free-format COBOL. Verify with: `Get-Content file.cob -TotalCount 10`
→ Look for `*>` comments and non-column-aligned code. Accept and proceed.

**Analysis hangs on very large files (>5MB per file)**
→ CobolCraft `chunk-io.cob` (40KB) is fine. CNAF files (14-17MB each) cause hangs.
→ For CNAF-scale files, use `--dry-run` with a per-file timeout.
