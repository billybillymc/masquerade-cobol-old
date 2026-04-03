# Feature Coverage and Test Summary

Summary of Masquerade's capabilities, each backed by dedicated test suites. See [docs/FEATURES.md](docs/FEATURES.md) for detailed documentation on each feature.

## Offline Analysis Features

| Feature | What it does | Tests |
|---------|-------------|-------|
| **Conditional Logic Extraction** | Extracts IF/EVALUATE/GO TO/PERFORM decision trees from paragraph bodies | 22 |
| **Copybook Field Wiring** | Populates skeleton `@dataclass` stubs with typed fields from `.cpy` definitions | 12 |
| **CobolDecimal Numeric Semantics** | Faithful COBOL arithmetic: PIC precision, silent overflow, COMP-3 storage | 49 |
| **Structural Business Rules** | Deterministic rule extraction from conditionals using field-name pattern matching | 15 |
| **Behavioral Test Generation** | pytest suites from COBOL decision trees with real assertions | 10 |
| **File I/O Repository Mapping** | CICS file operations mapped to typed Python repository interfaces | 14 |
| **BMS Screen API Contracts** | Screen maps converted to Pydantic schemas + FastAPI route stubs | 15 |
| **Multi-Language Skeletons** | Language-neutral IR with Python, Java, and C# renderers | 27 |
| **Differential Test Harness** | Field-by-field equivalence verification with CobolDecimal-aware comparison | 15 |
| **Symbol Table Resolution** | Hierarchical field lookup with qualified names and ambiguity detection | 12 |

## LLM-Powered Features (require API keys)

| Feature | What it does |
|---------|-------------|
| **RAG Q&A** | Natural-language questions about COBOL code, answered with source citations via Gemini + Pinecone + Cohere |
| **Semantic Business Rules** | LLM-assisted rule extraction with anti-hallucination validation |
| **Reimplementation Specs** | Full spec documents from structural analysis + RAG context |
| **Impact Analysis** | Change blast-radius assessment using dependency graph + LLM interpretation |
| **Interactive CLI** | 20+ commands for graph analysis, data exploration, and LLM-powered generation |

**Total pipeline tests**: 502 (across all offline features + parser + graph + specs)

## Reimplementation Coverage

37 COBOL programs reimplemented in Python with differential test suites:

| Codebase | Programs reimplemented | Tests |
|----------|----------------------|-------|
| AWS CardDemo | 31 (all programs) | 62 |
| IBM CBSA | 1 (DBCRFUN) | 8 |
| Star Trek | 1 (full game) | 10 |
| Taxe Fonciere | 1 (EFITA3B8) | 9 |
| CobolCraft | 2 (uuid, json-parse) | 7 |

**Total reimplementation tests**: 58

## Validated Codebases

The parser has been validated against 5 real COBOL codebases totaling 273 programs and 96K lines of code.

## Running All Tests

```bash
python -m pytest pipeline/tests/ pipeline/reimpl/ -v
# 560 tests, all passing
```
