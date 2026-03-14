The actual problem is comprehension and modernization of codebases that are 30-50

 years old, millions of lines, undocumented, and written by people who are retired or dead.



 That's arguably a harder and more commercially relevant problem.



 What This Actually Looks Like



 The Core Problem



 A bank has 4 million lines of COBOL running on a mainframe. Nobody fully understands it. They're paying $500k+/year in mainframe licensing. They want to modernize but they're terrified because:



 - No documentation

 - No tests

 - Business logic is buried in copybooks, JCL, and paragraph names like PROC-X47-RECON

 - Data flows through VSAM files, DB2 tables, and flat files with implicit schemas

 - One wrong change can misroute millions of dollars



 Your Tool: A COBOL Codebase Intelligence Engine



 Layer 1 — Parse and model the entire environment

 - COBOL parser (not trivial — dialects vary across IBM, Micro Focus, ACUCOBOL)

 - JCL parser (job control — this defines how programs connect)

 - Copybook resolver (shared data structures, like header files)

 - Build a full dependency graph: programs → copybooks → files → DB2 tables → JCL jobs → schedules



 Layer 2 — AI-powered semantic analysis

 - Take each COBOL paragraph/section and produce a plain-English explanation of what it does

 - Infer business rules: "If customer type is 'P' and balance exceeds 10000, apply rate schedule 3"

 - Detect dead code (paragraphs never PERFORM'd, branches that can't trigger)

 - Identify data lineage: trace a field from input file through transformations to output

 - Cluster related programs into "business domains" (payments, reconciliation, reporting)



 Layer 3 — Interactive exploration UI

 - Visual dependency graph (programs, files, tables, jobs)

 - Click any paragraph → see AI-generated explanation + original code side by side

 - Search by business concept ("where do we calculate late fees?") not by code symbol

 - Data flow visualization: pick a field, see every program that touches it and how it transforms

 - Impact analysis: "if I change this copybook field, what breaks?"



 Layer 4 — The impressive part: verified modernization

 - Generate equivalent Python/Java/TypeScript for a selected COBOL module

 - Automatically generate test cases from the COBOL logic (input → expected output pairs)

 - Run both COBOL and modern code against the same test cases and diff the results

 - Produce a confidence score: "97% equivalent, 3 edge cases to review manually"



 6-Week Scoping



 ┌──────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐

 │ Week │                                                                                      Milestone                                                                                       │

 ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤

 │ 1    │ COBOL parser + copybook resolution working on real code. Find open-source COBOL codebases (there are several on GitHub — GnuCOBOL test suites, AWS mainframe modernization samples). │

 ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤

 │ 2    │ Dependency graph extraction + basic web UI to explore it. JCL parsing if time allows.                                                                                                │

 ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤

 │ 3    │ AI semantic analysis pipeline — paragraph-level explanations, business rule extraction. This is where the LLM integration gets deep.                                                 │

 ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤

 │ 4    │ Data lineage tracing + natural language search ("where do we calculate interest?").                                                                                                  │

 ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤

 │ 5    │ Modernization output — generate equivalent code for a module + auto-generated test harness.                                                                                          │

 ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤

 │ 6    │ Polish, demo scenarios, impact analysis feature, write-up.                                                                                                                           │

 └──────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘



 Why This Is a Strong Capstone



 - Technically deep — parsing COBOL dialects, building program analysis graphs, data flow tracing. This is real compiler/PL work.

 - AI is load-bearing — the semantic analysis and modernization layers genuinely need LLMs and aren't gimmicks. Traditional tools can parse COBOL but they can't tell you what it means.

 - The demo is visceral — throw a gnarly 2000-line COBOL program at it and watch it produce a navigable, comprehensible map of business logic. Evaluators will get it instantly.

 - Commercially real — this is a multi-billion dollar problem. IBM, Accenture, and a dozen startups are chasing it. You're not building a toy.

 - Differentiated — most AI+COBOL efforts are "translate this file." Yours is "understand this entire system, then translate with verification." The system-level thinking is what separates it.



 The main risk is the parser. COBOL has ugly dialects. Mitigate this by targeting one dialect (IBM Enterprise COBOL) and using/extending an existing open-source parser rather than writing one from scratch.



  Primary Demo Codebases



  1. Wenzel/CNAF — 26 files, 3.5M LOC



  The French national family allowances fund. This is real government production COBOL that calculates welfare benefits. It's the single most impressive thing you can point your tool at. If your system can

  make sense of this, the demo sells itself. The sheer scale forces you to build real dependency analysis, not toy pattern matching.



  2. aws-samples/aws-mainframe-modernization-carddemo — 28 files, 19K LOC



  AWS's official credit card transaction processing demo for their mainframe modernization service. Well-structured, realistic business logic (transactions, accounts, reports), includes CICS, VSAM, DB2. This

  is your "clean demo" codebase — complex enough to be interesting, small enough to walk through in a presentation.



  3. etalab/taxe-fonciere — 6 files, 2.3K LOC



  French property tax calculation, published by the French government's open data agency. Real tax law encoded in COBOL. Small enough to verify your tool's output by hand, dense enough in business rules to

  show the AI comprehension layer working.



  Supporting Codebases



  4. RocketSoftwareCOBOLandMainframe/BankDemo — 65 files, 18K LOC



  Full banking application from Micro Focus/Rocket. Good for showing your tool handles a different COBOL dialect and a different domain (banking vs. government).



  5. cicsdev/cics-genapp — 31 files, 9K LOC



  IBM's general insurance application. CICS transactions, multiple programs calling each other. Tests your inter-program dependency graph and data flow analysis.



  6. fgregg/tax\_extension — 70 files, 37K LOC



  US tax extension code. Pairs nicely with the French tax code to show cross-domain generalization.



  Why These Six



  ┌────────────────────────┬──────────────────────────┬──────────────────────────────────────────────────────────────────────┐

  │          Role          │         Codebase         │                                 Why                                  │

  ├────────────────────────┼──────────────────────────┼──────────────────────────────────────────────────────────────────────┤

  │ Showstopper demo       │ CNAF (3.5M LOC)          │ "My tool made sense of 3.5 million lines of French government COBOL" │

  ├────────────────────────┼──────────────────────────┼──────────────────────────────────────────────────────────────────────┤

  │ Walkthrough demo       │ CardDemo (19K LOC)       │ Clean, well-documented, perfect for live demo                        │

  ├────────────────────────┼──────────────────────────┼──────────────────────────────────────────────────────────────────────┤

  │ Precision validation   │ taxe-fonciere (2.3K LOC) │ Small enough to verify AI output is correct                          │

  ├────────────────────────┼──────────────────────────┼──────────────────────────────────────────────────────────────────────┤

  │ Breadth proof          │ BankDemo (18K LOC)       │ Different dialect, different domain                                  │

  ├────────────────────────┼──────────────────────────┼──────────────────────────────────────────────────────────────────────┤

  │ Integration complexity │ cics-genapp (9K LOC)     │ Multi-program CICS interactions                                      │

  ├────────────────────────┼──────────────────────────┼──────────────────────────────────────────────────────────────────────┤

  │ Scale test             │ tax\_extension (37K LOC)  │ Mid-size, tests performance                                          │

  └────────────────────────┴──────────────────────────┴──────────────────────────────────────────────────────────────────────┘



  Skip the parser test suites (koopa, proleap-cobol-parser, tree-sitter-cobol, opensourcecobol4j) — they have huge LOC counts but it's mostly test fixtures, not real business logic. Also skip

  INFINITE-TECHNOLOGY/COBOL for the same reason.



  Start with CardDemo in week 1 (manageable, well-documented, you'll get your pipeline working fast), then point it at CNAF by week 4 to stress-test everything.

