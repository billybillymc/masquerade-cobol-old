# Feature Coverage and Test Summary

Summary of Masquerade's capabilities, each backed by dedicated test suites. See [docs/FEATURES.md](docs/FEATURES.md) for detailed documentation on each feature.

## Features

| Feature | What it does | Tests |
|---------|-------------|-------|
| **Conditional Logic Extraction** | Extracts IF/EVALUATE/GO TO/PERFORM decision trees from paragraph bodies | 22 |
| **Copybook Field Wiring** | Populates skeleton `@dataclass` stubs with typed fields from `.cpy` definitions | 12 |
| **CobolDecimal Numeric Semantics** | Faithful COBOL arithmetic: PIC precision, silent overflow, COMP-3 storage | 49 |
| **Business Rule Extraction** | Evidence-anchored rules from conditionals (structural + optional LLM tier) | 15 |
| **Behavioral Test Generation** | pytest suites from COBOL decision trees with real assertions | 10 |
| **File I/O Repository Mapping** | CICS file operations mapped to typed Python repository interfaces | 14 |
| **BMS Screen API Contracts** | Screen maps converted to Pydantic schemas + FastAPI route stubs | 15 |
| **Multi-Language Skeletons** | Language-neutral IR with Python, Java, and C# renderers | 27 |
| **Differential Test Harness** | Field-by-field equivalence verification with CobolDecimal-aware comparison | 15 |
| **Symbol Table Resolution** | Hierarchical field lookup with qualified names and ambiguity detection | 12 |

**Total pipeline tests**: 512 (across all features above + parser + graph + specs)

## Reimplementation Coverage

40 COBOL programs reimplemented in Python with differential test suites:

| Codebase | Programs reimplemented | Tests |
|----------|----------------------|-------|
| AWS CardDemo | 31 (all programs) | 62 |
| IBM CBSA | 1 (DBCRFUN) | 8 |
| Star Trek | 1 (full game) | 10 |
| Taxe Fonciere | 1 (EFITA3B8) | 9 |
| Rocket BankDemo | 2 (UDATECNV, UTWOSCMP) | 12 |
| Legacy Benchmark | 1 (RTNCDE00) | 5 |
| CobolCraft | 2 (uuid, json-parse) | 7 |

**Total reimplementation tests**: 113

## Validated Codebases

The parser has been validated against 8 real COBOL codebases totaling 906 programs and 222K lines of code. The NIST COBOL-85 validation suite achieves a 98.6% pass rate (7,757 pass / 111 fail).

## Running All Tests

```bash
python -m pytest pipeline/tests/ pipeline/reimpl/ -v
# 625 tests, all passing
```
