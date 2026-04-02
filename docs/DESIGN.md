# Design Decisions

Key architectural and design choices in Masquerade, with rationale.

---

## Parse, Don't Translate

Masquerade is a structural analysis and verification tool, not a line-by-line translator. The insight: LLMs can generate passable modern code from COBOL, but nobody trusts it without verification. The bottleneck is proving behavioral equivalence, not generating code.

The pipeline therefore focuses on:
1. Extracting enough structure to understand the program
2. Generating typed skeletons to accelerate manual reimplementation
3. Providing differential testing to verify the result

---

## Evidence Contract

Every claim the system makes about COBOL code is anchored to source evidence:
- Business rules include source line spans
- Skeleton methods reference the paragraph they came from
- Test scenarios reference the conditional branch they test

This applies to LLM-assisted features too: the business rule extraction LLM tier validates that every claimed evidence span actually exists in the source. Claims without matching evidence are rejected.

---

## CobolDecimal Over Native Types

Python's `Decimal` doesn't match COBOL arithmetic. COBOL has:
- Silent left-truncation on overflow (no exception)
- Specific intermediate precision rules per operation (ADD uses `max(d1,d2)+1` digits)
- Implied decimal points that aren't stored
- Packed decimal (COMP-3) storage with specific byte sizes

Rather than document these differences and hope reimplementers get it right, `CobolDecimal` encodes the rules directly. You define the PIC, and all arithmetic follows COBOL semantics automatically.

---

## Structural + LLM Two-Tier Extraction

Business rule extraction has two tiers:
1. **Structural** (deterministic): pattern-matches on field names and conditional structure. Always available, no API keys needed, deterministic results.
2. **LLM** (optional): uses a prompt template for richer semantic interpretation. Outputs go through the same `BusinessRule` schema with evidence validation.

The structural tier is the default and handles the majority of cases. The LLM tier is opt-in for when you need deeper semantic understanding. Both produce the same output format.

---

## Skeleton IR for Language Neutrality

The structural mapping from COBOL to modern code (paragraph -> method, copybook -> data class, PERFORM -> method call) is language-independent. Rather than duplicate this logic per language, the pipeline generates a language-neutral `IRModule` that pluggable renderers convert to Python, Java, or C#.

Python is the primary target (and the only language with full reimplementation + differential testing support), but the IR means Java/C# skeletons come for free.

---

## Readiness Scores for Prioritization

Not all programs are equally easy to reimplement. The `readiness_score` combines:
- Parser coverage (how much structure was extracted)
- Dependency isolation (fewer callers = safer to change)
- Complexity grade (cyclomatic complexity, nesting depth)

This lets you prioritize: start with high-readiness leaf programs, build confidence, then tackle the complex hub programs.

---

## Differential Testing Over Translation Confidence

Most COBOL modernization tools report "translation confidence" — a number that means nothing because it's not grounded in behavioral testing. Masquerade's differential harness compares actual field values:

- Run the original COBOL (or use captured golden outputs)
- Run your Python reimplementation
- Compare field by field with CobolDecimal-aware numerics
- Get a confidence score backed by evidence

A 95% confidence score means 95% of output fields matched exactly. The 5% that didn't are listed with expected vs actual values.

---

## Fixed-Format Parser, Not Universal

The parser targets fixed-format IBM Enterprise COBOL. It does not attempt to handle every COBOL dialect. This is intentional:
- Fixed-format IBM COBOL represents the vast majority of production COBOL
- Attempting universal parsing leads to a parser that handles everything poorly
- For free-format codebases (like CobolCraft), the dependency graph still works even when paragraph extraction fails

The parser degrades gracefully: partial results are still useful.

---

## Agent-First Design

The entire pipeline is designed to be operated by a coding agent as effectively as by a human:

**Structured, machine-readable artifacts**: `programs.json` and `graph.json` are JSON — agents parse them natively. No scraping HTML reports or parsing prose.

**Spec-driven contracts**: Every feature has a specification in `specs/` with explicit inputs, outputs, and acceptance criteria. Agents follow these as implementation contracts rather than interpreting vague instructions.

**Step-by-step workflow guide**: `READ_THIS_LAST.md` reads as an agent prompt: concrete commands, expected outputs, decision criteria for what to pick next. An agent can follow it end-to-end without improvising.

**Deterministic verification**: 625 tests mean an agent can make changes and immediately verify nothing broke. No manual inspection needed between steps.

**Evidence contract**: Every claim anchored to source line spans. Agents get grounded context, not summaries they might hallucinate on top of.

This isn't an afterthought — the structured artifacts, step-by-step guide, and deterministic tests were designed so that a human-agent pair can reimplement COBOL programs faster than either could alone. The human provides domain judgment; the agent handles the volume.

---

## Two-Layer Intelligence: Offline + LLM

The pipeline has two complementary layers:

**Offline layer** (no API keys, fully deterministic): parsing, graph building, skeleton generation, structural business rules, behavioral test generation, CobolDecimal, differential testing. This is the foundation — everything an agent needs to do structural analysis and verification.

**LLM layer** (requires API keys): RAG Q&A, semantic business rule extraction, reimplementation spec generation, impact analysis. This uses Google Gemini for LLM inference, OpenAI for embeddings, Pinecone for vector search, and optionally Cohere for reranking.

The LLM layer builds on the offline layer's artifacts, not the other way around. You can reimplement COBOL programs using only the offline layer. The LLM layer accelerates understanding — especially for the initial "what does this program actually do?" question that's hardest to answer from structure alone.

Cohere reranking degrades gracefully (falls back to vector scores). The structural business rule tier provides an offline alternative to LLM-powered extraction. The system is usable at every tier.
