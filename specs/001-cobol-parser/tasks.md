# Tasks: COBOL Parser + Copybook Resolution

**Input**: Design documents from `specs/001-cobol-parser/`
**Prerequisites**: plan.md (required), spec.md (required)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, build tooling, and test codebase preparation

- [ ] T001 Create `services/parser-ir-service/` Java project with Gradle build and JUnit 5 dependency
- [ ] T002 [P] Create JSON schema files in `packages/schemas/` for AST output, parse errors, coverage report, and symbol table
- [ ] T003 [P] Verify CardDemo test codebase is available at `test-codebases/carddemo/` with `.cbl` and `.cpy` files accessible
- [ ] T004 [P] Verify taxe-fonciere test codebase is available at `test-codebases/taxe-fonciere/` with `.cob` and `.cpy` files accessible
- [ ] T005 [P] Create Dockerfile for `parser-ir-service`
- [ ] T006 Configure CI smoke test script at `scripts/ci-smoke.ps1` to compile and run parser unit tests

---

## Phase 2: Parser Selection Research

**Purpose**: Evaluate parser candidates and select the one to integrate

**⚠️ CRITICAL**: Parser selection must complete before any US1 implementation

- [ ] T007 [US0] Benchmark Eclipse che-che4z-lsp-for-cobol against CardDemo — measure parse coverage, AST quality, error recovery
- [ ] T008 [P] [US0] Benchmark proleap-cobol-parser against CardDemo — measure parse coverage, AST quality, error recovery
- [ ] T009 [P] [US0] Benchmark koopa against CardDemo — measure parse coverage, AST quality, error recovery
- [ ] T010 [US0] Write parser selection decision to `specs/001-cobol-parser/research.md` with coverage scores, tradeoffs, and recommendation
- [ ] T011 [US0] Add selected parser as Gradle dependency in `services/parser-ir-service/build.gradle`

**Checkpoint**: Parser selected and integrated as dependency

---

## Phase 3: User Story 1 — Parse COBOL Programs and Produce AST (Priority: P1)

**Goal**: Parse IBM Enterprise COBOL source files into typed ASTs with stable node IDs and source span mappings

**Independent Test**: Point parser at CardDemo `.cbl` files and verify typed AST output

### Tests for User Story 1

> **Write tests FIRST, ensure they FAIL before implementation**

- [ ] T012 [US1] Write failing test: given a valid CardDemo `.cbl` file, parser produces a typed AST with ProgramNode, SectionNode, ParagraphNode — `src/test/java/parser/CardDemoParseTest.java`
- [ ] T013 [P] [US1] Write failing test: every AST node has a non-null SourceSpan with file, start line/col, end line/col — `src/test/java/ast/SourceSpanAccuracyTest.java`
- [ ] T014 [P] [US1] Write failing test: AST node IDs are deterministic (same input → same IDs) — `src/test/java/parser/CardDemoParseTest.java`
- [ ] T015 [P] [US1] Write failing test: given a file with a recoverable syntax issue, parser produces partial AST with error annotation — `src/test/java/parser/ErrorClassificationTest.java`
- [ ] T016 [P] [US1] Write failing test: given a blocking failure, file is marked failed without halting batch — `src/test/java/parser/ErrorClassificationTest.java`

### Implementation for User Story 1

- [ ] T017 [US1] Implement `SourceSpan` model class — `src/main/java/model/SourceSpan.java`
- [ ] T018 [US1] Implement `AstNode` base class and typed subclasses (ProgramNode, SectionNode, ParagraphNode, FieldNode) — `src/main/java/ast/`
- [ ] T019 [US1] Implement `CobolParser` wrapper that invokes selected parser library and produces typed AstNode trees — `src/main/java/parser/CobolParser.java`
- [ ] T020 [US1] Implement stable node ID generation scheme (deterministic hash of file + position) — `src/main/java/ast/AstNode.java`
- [ ] T021 [US1] Implement `ParseError` with error class enum (RECOVERABLE, UNSUPPORTED, BLOCKING), error code, and source span — `src/main/java/diagnostics/ParseError.java`
- [ ] T022 [US1] Implement batch parse mode: iterate files, collect results, continue on individual failures — `src/main/java/parser/CobolParser.java`
- [ ] T023 [US1] Make all US1 tests pass
- [ ] T024 [US1] Run parser against full CardDemo and verify output manually for one representative program

**Checkpoint**: Parser produces typed ASTs for CardDemo. Tests green.

---

## Phase 4: User Story 2 — Copybook Resolution (Priority: P1)

**Goal**: Resolve COPY statements using configured include paths, including transitive resolution, REPLACING, and missing-copybook handling

**Independent Test**: Parse CardDemo files that reference copybooks and verify expanded fields in AST

### Tests for User Story 2

- [ ] T025 [US2] Write failing test: given a program with COPY referencing a copybook in include path, AST contains expanded fields with copybook source spans — `src/test/java/parser/CopybookResolverTest.java`
- [ ] T026 [P] [US2] Write failing test: COPY ... REPLACING produces AST with replaced identifiers and link to original copybook — `src/test/java/parser/CopybookResolverTest.java`
- [ ] T027 [P] [US2] Write failing test: missing copybook produces recoverable error and parser continues — `src/test/java/parser/CopybookResolverTest.java`
- [ ] T028 [P] [US2] Write failing test: transitive copybook resolution (A copies B, B copies C) works up to depth limit — `src/test/java/parser/CopybookResolverTest.java`
- [ ] T029 [P] [US2] Write failing test: circular copybook reference is detected and reported as error — `src/test/java/parser/CopybookResolverTest.java`

### Implementation for User Story 2

- [ ] T030 [US2] Implement `CopybookResolver` with configurable include paths and file-extension search — `src/main/java/parser/CopybookResolver.java`
- [ ] T031 [US2] Implement transitive COPY expansion with configurable depth limit and cycle detection — `src/main/java/parser/CopybookResolver.java`
- [ ] T032 [US2] Implement COPY ... REPLACING text substitution with original-source link preservation — `src/main/java/parser/CopybookResolver.java`
- [ ] T033 [US2] Integrate CopybookResolver into CobolParser pipeline (resolve before or during parse) — `src/main/java/parser/CobolParser.java`
- [ ] T034 [US2] Make all US2 tests pass
- [ ] T035 [US2] Run parser against CardDemo with copybook include path configured and verify all COPY statements resolved

**Checkpoint**: Copybook resolution working end-to-end. All CardDemo copybooks resolve.

---

## Phase 5: User Story 3 — Symbol Table Extraction (Priority: P2)

**Goal**: Extract a complete symbol table from the DATA DIVISION with level numbers, PIC, USAGE, REDEFINES, OCCURS, and group hierarchy

**Independent Test**: Parse a CardDemo program and verify symbol table contains every data item

### Tests for User Story 3

- [ ] T036 [US3] Write failing test: symbol table contains all data items from WORKING-STORAGE with level, PIC, USAGE — `src/test/java/parser/SymbolTableExtractorTest.java`
- [ ] T037 [P] [US3] Write failing test: REDEFINES entries are linked to their targets — `src/test/java/parser/SymbolTableExtractorTest.java`
- [ ] T038 [P] [US3] Write failing test: OCCURS DEPENDING ON captures controlling field reference — `src/test/java/parser/SymbolTableExtractorTest.java`
- [ ] T039 [P] [US3] Write failing test: group/elementary hierarchy is correctly represented — `src/test/java/parser/SymbolTableExtractorTest.java`

### Implementation for User Story 3

- [ ] T040 [US3] Implement `SymbolTable` and `FieldEntry` model classes — `src/main/java/model/SymbolTable.java`
- [ ] T041 [US3] Implement `SymbolTableExtractor` that walks DATA DIVISION AST nodes — `src/main/java/parser/SymbolTableExtractor.java`
- [ ] T042 [US3] Handle REDEFINES cross-references and OCCURS DEPENDING ON — `src/main/java/parser/SymbolTableExtractor.java`
- [ ] T043 [US3] Make all US3 tests pass
- [ ] T044 [US3] Validate symbol table completeness against hand-counted data items in one CardDemo program

**Checkpoint**: Symbol table extraction complete and validated.

---

## Phase 6: User Story 4 — Parse Coverage Report (Priority: P2)

**Goal**: Produce per-file and aggregate parse coverage metrics with error classification

**Independent Test**: Run parser on CardDemo and verify coverage report shows >= 90% aggregate

### Tests for User Story 4

- [ ] T045 [US4] Write failing test: coverage report shows per-file parse success percentage — `src/test/java/diagnostics/CoverageReportTest.java`
- [ ] T046 [P] [US4] Write failing test: errors are classified by type (recoverable/unsupported/blocking) with machine-readable codes — `src/test/java/diagnostics/CoverageReportTest.java`
- [ ] T047 [P] [US4] Write failing test: aggregate coverage computed correctly across multiple files — `src/test/java/diagnostics/CoverageReportTest.java`

### Implementation for User Story 4

- [ ] T048 [US4] Implement `CoverageReport` with per-file and aggregate metrics — `src/main/java/diagnostics/CoverageReport.java`
- [ ] T049 [US4] Wire coverage collection into batch parse pipeline — `src/main/java/parser/CobolParser.java`
- [ ] T050 [US4] Implement JSON serialization of coverage report per `packages/schemas/coverage-report.schema.json`
- [ ] T051 [US4] Make all US4 tests pass
- [ ] T052 [US4] Run against CardDemo and verify >= 90% coverage; run against taxe-fonciere and verify >= 85%

**Checkpoint**: Coverage reporting working. KPI targets met on test codebases.

---

## Phase 7: User Story 5 — SQL and CICS Block Recognition (Priority: P3)

**Goal**: Recognize EXEC SQL and EXEC CICS blocks, link SQL host variables to symbol table

**Independent Test**: Parse CardDemo files with EXEC SQL and verify SQL text captured with host variable links

### Tests for User Story 5

- [ ] T053 [US5] Write failing test: EXEC SQL block captured as SqlNode with query text — `src/test/java/parser/SqlBlockExtractorTest.java`
- [ ] T054 [P] [US5] Write failing test: SQL host variables resolve to symbol table entries — `src/test/java/parser/SqlBlockExtractorTest.java`
- [ ] T055 [P] [US5] Write failing test: EXEC CICS block captured as opaque node — `src/test/java/parser/CicsBlockTest.java`

### Implementation for User Story 5

- [ ] T056 [US5] Implement `SqlNode` AST type and `SqlBlockExtractor` — `src/main/java/parser/SqlBlockExtractor.java`, `src/main/java/ast/SqlNode.java`
- [ ] T057 [US5] Implement host variable resolution against symbol table — `src/main/java/parser/SqlBlockExtractor.java`
- [ ] T058 [US5] Implement EXEC CICS recognition as opaque `CicsNode` — `src/main/java/ast/CicsNode.java`
- [ ] T059 [US5] Make all US5 tests pass

**Checkpoint**: SQL and CICS blocks recognized. Host variables linked.

---

## Phase 8: Service API and Integration

**Purpose**: Wrap parser into an HTTP service, validate end-to-end

- [ ] T060 [P] Implement HTTP endpoint: POST /parse with source directory + include paths → AST + symbol table + coverage — `src/main/java/api/ParserServiceApi.java`
- [ ] T061 [P] Implement JSON serialization for all output types per shared schemas
- [ ] T062 Write integration test: call HTTP endpoint with CardDemo path, verify response matches schema — `src/test/java/api/ParserServiceIntegrationTest.java`
- [ ] T063 Build Docker image and verify service starts and responds to health check
- [ ] T064 Write `specs/001-cobol-parser/quickstart.md` with local run instructions

---

## Phase 9: Polish & Cross-Cutting

- [ ] T065 [P] Write `specs/001-cobol-parser/data-model.md` documenting final AST schema and symbol table model
- [ ] T066 [P] Update `services/parser-ir-service/README.md` with architecture, usage, and contribution notes
- [ ] T067 Run full parse suite against both CardDemo and taxe-fonciere, capture results in `specs/001-cobol-parser/research.md`
- [ ] T068 Verify all JSON output validates against `packages/schemas/` definitions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Research)**: Depends on Phase 1 (need build tooling to benchmark)
- **Phase 3 (US1 Parse)**: Depends on Phase 2 (parser selected)
- **Phase 4 (US2 Copybooks)**: Depends on Phase 3 (parser working)
- **Phase 5 (US3 Symbol Table)**: Depends on Phase 3 (needs AST); can run parallel with Phase 4
- **Phase 6 (US4 Coverage)**: Depends on Phase 3; can run parallel with Phase 4 and 5
- **Phase 7 (US5 SQL/CICS)**: Depends on Phase 3 and Phase 5 (needs AST + symbol table)
- **Phase 8 (API)**: Depends on Phase 3-7 completion
- **Phase 9 (Polish)**: Depends on Phase 8

### Parallel Opportunities

- T002, T003, T004, T005 can all run in parallel (Phase 1)
- T007, T008, T009 can all run in parallel (Phase 2 benchmarks)
- Phase 5 and Phase 6 can start as soon as Phase 3 completes (independent of Phase 4)
- All tests within a phase marked [P] can run in parallel
