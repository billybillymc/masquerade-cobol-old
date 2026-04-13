# Background: Research Notes

Early research and scoping notes that informed Masquerade's design. Preserved for historical context.

## The Core Insight

The actual problem is comprehension and modernization of codebases that are 30-50 years old, millions of lines, undocumented, and written by people who are retired or dead.

A bank has 4 million lines of COBOL running on a mainframe. Nobody fully understands it. They want to modernize but they're terrified because:
- No documentation
- No tests
- Business logic is buried in copybooks, JCL, and paragraph names like `PROC-X47-RECON`
- Data flows through VSAM files, DB2 tables, and flat files with implicit schemas
- One wrong change can misroute millions of dollars

## What Masquerade Does About It

### Layer 1 — Parse and model the entire environment
- COBOL programs, copybooks, BMS screens, JCL jobs
- Produce a structured AST with full conditional logic extraction
- Build a cross-program dependency graph

### Layer 2 — Semantic analysis
- Business rule extraction (deterministic + optional LLM)
- Complexity grading and readiness scoring
- Dead code detection and impact analysis

### Layer 3 — Code generation
- Python skeletons with typed copybook fields
- Behavioral test suites from COBOL decision trees
- Repository interfaces from CICS file operations
- API contracts from BMS screen maps

### Layer 4 — Verification
- Differential test harness for behavioral equivalence
- CobolDecimal for faithful numeric semantics
- Confidence scoring with field-by-field evidence

## Key Decision: Verification Over Translation

Most COBOL modernization tools focus on translation — generating modern code from COBOL. This approach fails because:
1. Generated code is untrusted without verification
2. COBOL numeric semantics don't match any modern language defaults
3. Enterprise stakeholders need evidence, not confidence

Masquerade focuses on **verified reimplementation**: understand the program, generate a skeleton, write the reimplementation manually (using the skeleton and business rules as guides), then prove equivalence through differential testing.
