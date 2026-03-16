# Implementation Plan: COBOL Parser + Copybook Resolution

**Branch**: `001-cobol-parser` | **Date**: 2026-03-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-cobol-parser/spec.md`

## Summary

Build a COBOL parsing service that ingests IBM Enterprise COBOL source files and copybooks, produces typed ASTs with stable node IDs and lossless source span mappings, extracts symbol tables from the DATA DIVISION, and reports parse coverage metrics. The service extends an existing open-source COBOL parser rather than building one from scratch, following the best-effort failure policy (partial results on recoverable errors, never silent drops).

## Technical Context

**Language/Version**: Java 17+ (Kotlin optional for DSL-heavy utilities)  
**Primary Dependencies**: Existing open-source COBOL parser (candidates: Eclipse COBOL Parser / che-che4z-lsp-for-cobol, koopa, or proleap-cobol-parser — final selection after Phase 0 benchmark), Gradle or Maven build  
**Storage**: File-based AST artifact output (JSON), streamed to object store in later features  
**Testing**: JUnit 5 + AssertJ for unit/contract tests, pytest for integration smoke tests against the service API  
**Target Platform**: Linux server (Docker container), Windows dev support  
**Project Type**: Library + service (parser core as library, HTTP/gRPC wrapper as service)  
**Performance Goals**: Parse CardDemo (19K LOC, 28 files) in < 30 seconds; parse taxe-fonciere (2.3K LOC) in < 5 seconds  
**Constraints**: Memory < 2GB for CardDemo-scale codebases; deterministic output (same input → same AST + IDs)  
**Scale/Scope**: MVP targets 500K LOC benchmark; must handle file counts in the hundreds

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Evidence-Grounded Analysis | PASS | AST nodes carry lossless source spans; all downstream claims can cite exact locations |
| II. Test-First Development | PASS | Parser integration tests written before implementation; characterization tests on CardDemo before extending parser |
| III. Verified Modernization | N/A | This feature produces parser output, not modernization output |
| IV. Graceful Degradation | PASS | Best-effort policy: partial AST on recoverable errors, unknown nodes preserved, coverage metrics reported |
| V. Structured Outputs with Provenance | PASS | AST output is structured JSON with stable IDs and source spans |
| VI. Resumable and Idempotent Pipelines | PASS | Parser is stateless per-file; batch processing is idempotent (same files → same output) |
| VII. Single Dialect Focus | PASS | Targets IBM Enterprise COBOL only; unsupported constructs documented and reported |

## Project Structure

### Documentation (this feature)

```text
specs/001-cobol-parser/
├── plan.md              # This file
├── research.md          # Phase 0: parser candidate evaluation
├── data-model.md        # Phase 1: AST schema and symbol table model
├── quickstart.md        # Phase 1: how to run the parser locally
├── contracts/           # Phase 1: API contracts for parser output
└── tasks.md             # Phase 2: actionable task breakdown
```

### Source Code (repository root)

```text
services/parser-ir-service/
├── src/main/java/
│   ├── parser/
│   │   ├── CobolParser.java          # Parser integration wrapper
│   │   ├── CopybookResolver.java     # Include-path resolution and expansion
│   │   ├── SymbolTableExtractor.java  # DATA DIVISION extraction
│   │   └── SqlBlockExtractor.java     # EXEC SQL recognition
│   ├── ast/
│   │   ├── AstNode.java              # Base typed AST node with source span
│   │   ├── ProgramNode.java          # Top-level program
│   │   ├── SectionNode.java          # Division sections
│   │   ├── ParagraphNode.java        # Procedure division paragraphs
│   │   ├── FieldNode.java            # Data items
│   │   └── SqlNode.java              # EXEC SQL blocks
│   ├── diagnostics/
│   │   ├── ParseError.java           # Error with class, code, span
│   │   └── CoverageReport.java       # Per-file and aggregate coverage
│   ├── model/
│   │   ├── SymbolTable.java          # Field catalog
│   │   └── SourceSpan.java           # File + line/col range
│   └── api/
│       └── ParserServiceApi.java     # HTTP/gRPC endpoint definitions
├── src/test/java/
│   ├── parser/
│   │   ├── CardDemoParseTest.java    # Characterization tests on CardDemo
│   │   ├── TaxeFonciereParseTest.java
│   │   ├── CopybookResolverTest.java
│   │   └── ErrorClassificationTest.java
│   ├── ast/
│   │   └── SourceSpanAccuracyTest.java
│   └── diagnostics/
│       └── CoverageReportTest.java
├── build.gradle          # or pom.xml
├── Dockerfile
├── pyproject.toml        # for integration test runner
└── README.md

packages/schemas/
├── ast-output.schema.json       # JSON schema for AST artifacts
├── parse-error.schema.json      # JSON schema for diagnostics
├── coverage-report.schema.json  # JSON schema for coverage
└── symbol-table.schema.json     # JSON schema for symbol table
```

**Structure Decision**: Follows the existing `services/parser-ir-service/` location from the repo structure. Parser core is a library within the service; API wrapper is thin. Shared schemas live in `packages/schemas/` for cross-service consumption.

## Phase 0: Research and Parser Selection

**Duration**: 1-2 days  
**Output**: `specs/001-cobol-parser/research.md`

Evaluate candidate open-source COBOL parsers against these criteria:

| Criterion | Weight | Notes |
|-----------|--------|-------|
| IBM Enterprise COBOL coverage | High | Must handle COPY, REPLACING, REDEFINES, OCCURS, EXEC SQL |
| AST quality and node typing | High | Typed nodes with source positions, not just parse trees |
| Extensibility | Medium | Can we add custom node types for unknown constructs? |
| Active maintenance | Medium | Recent commits, responsive to issues |
| License compatibility | High | Must be compatible with our distribution model |
| Java/Kotlin ecosystem | High | Must integrate into our JVM stack |

Candidates to benchmark:
1. **Eclipse che-che4z-lsp-for-cobol** — Broadcom/Eclipse LSP, active, IBM dialect focus
2. **proleap-cobol-parser** — ANTLR-based, Java, good AST, less active
3. **koopa** — Adaptive parser, Java, research-grade

Benchmark method: parse full CardDemo and taxe-fonciere, measure coverage, check AST completeness, assess error recovery.

## Phase 1: Design and Contracts

**Duration**: 1-2 days  
**Output**: `data-model.md`, `quickstart.md`, `contracts/`

1. Define AST node type hierarchy and stable ID generation scheme
2. Define symbol table schema (level, PIC, USAGE, REDEFINES, OCCURS)
3. Define parse error taxonomy (recoverable / unsupported / blocking)
4. Define coverage report schema
5. Define service API contract (input: source files + include paths → output: AST + symbol table + diagnostics)
6. Write contract tests that validate schema compliance

## Phase 2: Implementation

**Duration**: 3-4 days  
**Output**: Working parser service

### Step 1: Parser Integration (TDD)
- Write failing tests against CardDemo files expecting typed AST output
- Integrate selected parser library
- Implement `CobolParser` wrapper that produces typed `AstNode` trees
- Make tests green

### Step 2: Copybook Resolution (TDD)
- Write failing tests for COPY expansion with configured include paths
- Implement `CopybookResolver` with transitive resolution and cycle detection
- Write failing tests for COPY ... REPLACING
- Implement replacement logic
- Write failing tests for missing copybooks (recoverable error)
- Make all tests green

### Step 3: Symbol Table Extraction (TDD)
- Write failing tests for DATA DIVISION extraction on CardDemo programs
- Implement `SymbolTableExtractor`
- Cover: level numbers, PIC, USAGE, REDEFINES, OCCURS, group hierarchy
- Make tests green

### Step 4: Error Classification and Coverage (TDD)
- Write failing tests for error classification and coverage computation
- Implement diagnostics module
- Verify best-effort policy: partial AST produced for recoverable errors
- Make tests green

### Step 5: SQL and CICS Block Recognition (TDD)
- Write failing tests for EXEC SQL host variable linking
- Implement `SqlBlockExtractor`
- Write tests for EXEC CICS as opaque nodes
- Make tests green

### Step 6: Service API
- Wrap parser library in HTTP endpoint
- Write integration tests against running service
- Dockerize

## Complexity Tracking

No constitution violations. The structure follows the established repo layout and uses a single service with a library core.
