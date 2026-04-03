# Contributing to Masquerade

## Setup

```bash
git clone https://github.com/billybillymc/masquerade-cobol.git
cd masquerade-cobol
pip install -r pipeline/requirements.txt
python -m pytest pipeline/tests/ pipeline/reimpl/ -v  # should be 560 passing
```

Requires Python 3.11+.

For LLM-powered features (RAG Q&A, semantic rules, spec generation), create `pipeline/.env` with API keys:

```bash
GOOGLE_API_KEY=...        # Google Gemini 2.5 Flash
OPENAI_API_KEY=...        # OpenAI embeddings (text-embedding-3-small)
PINECONE_API_KEY=...      # Pinecone vector database
COHERE_API_KEY=...        # Cohere reranking (optional)
```

## Working with a Coding Agent

This repo is designed to be operated by a coding agent (Claude Code, Cursor, etc.). Point your agent at `READ_THIS_LAST.md` — it's a step-by-step workflow guide that works as an agent prompt. The structured JSON artifacts, spec contracts in `specs/`, and 560 deterministic tests make agent-driven reimplementation effective.

## Ways to Contribute

### Add a new COBOL codebase

1. Place the codebase under `test-codebases/<name>/`
2. Run `cd pipeline && python analyze.py ../test-codebases/<name>`
3. Verify `_analysis/programs.json` looks reasonable
4. Register it in `pipeline/cli.py` under `KNOWN_CODEBASES`
5. Submit a PR with the analysis results and a note about parse coverage

### Add a Python reimplementation

1. Pick a program (see the [workflow guide](READ_THIS_LAST.md) for how to choose)
2. Write the reimplementation in `pipeline/reimpl/<program_name>.py`
3. Write tests in `pipeline/reimpl/test_<program_name>.py`
4. Ensure all existing tests still pass: `python -m pytest pipeline/tests/ pipeline/reimpl/ -v`
5. Submit a PR

Good reimplementation PRs include:
- A docstring referencing the original COBOL source file and line numbers
- Tests covering each branch of the main EVALUATE/IF
- Use of `CobolDecimal` for numeric fields where precision matters
- Boundary value and error path tests

### Improve the parser

The parser (`pipeline/cobol_parser.py`) currently handles fixed-format COBOL-85/2002. Areas that need work:

- **Free-format COBOL support** — GnuCOBOL style with `*>` comments
- **Nested programs** — multiple `IDENTIFICATION DIVISION` per file
- **Deeper CICS parsing** — currently identifies EXEC CICS blocks but doesn't parse all options
- **Additional dialects** — Micro Focus, ACUCOBOL extensions

Parser changes need tests in `pipeline/tests/test_cobol_parser*.py`.

### Improve CobolDecimal

`pipeline/cobol_decimal.py` covers the core PIC numeric semantics. Areas that need work:

- Additional USAGE types (BINARY-SHORT, BINARY-DOUBLE)
- OCCURS DEPENDING ON length-dependent storage
- NATIONAL/DBCS character handling
- Performance optimization for batch processing scenarios

## Running Tests

```bash
# Pipeline tests only
python -m pytest pipeline/tests/ -v

# Reimplementation tests only
python -m pytest pipeline/reimpl/ -v

# Everything
python -m pytest pipeline/tests/ pipeline/reimpl/ -v

# Specific module
python -m pytest pipeline/tests/test_cobol_decimal.py -v
```

## Code Style

- Follow existing patterns in the codebase
- Include docstrings for public functions referencing COBOL source where applicable
- Test each branch of COBOL conditional logic in reimplementations
- Use `CobolDecimal` instead of raw `Decimal` or `float` for COBOL numeric fields

## Commit Messages

Use clear, descriptive commit messages:
- `Add <codebase> reimpl: <PROGRAM-ID> with N tests`
- `Fix parser handling of <construct>`
- `Add <codebase> to test codebases (N programs, NK LOC)`
