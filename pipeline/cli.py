"""
CLI agent for querying COBOL codebases via RAG.

Usage:
    python cli.py

Registers all known codebases under test-codebases/ automatically.
Switch between them with /switch, or use graph-powered commands:
    /impact <name>  — blast-radius analysis
    /deps <name>    — dependency tree
    /hotspots       — hub programs (highest change risk)
    /isolated       — leaf programs (reimplementation candidates)

Command implementations live in:
    cli_graph.py    — impact, deps, hotspots, isolated, summary, readiness, dead, files
    cli_data.py     — dict, screens, jobs, trace, xref
    cli_generate.py — spec, rules, spec-gen, skeleton, test-gen, export, report, eval, complexity, estimate
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_config import register_codebase, PINECONE_INDEX_NAME, CODEBASES
from rag_models import QueryResult

_project_root = Path(__file__).resolve().parent.parent
_test_codebases = _project_root / "test-codebases"

KNOWN_CODEBASES = {
    "carddemo": {
        "dir": str(_test_codebases / "carddemo"),
        "label": "CardDemo — AWS Credit Card Processing (44 programs, 30K LOC)",
        "questions": [
            "Where do we calculate interest on accounts?",
            "What happens when a credit card transaction is posted?",
            "Which programs read or write to the TRANSACT file?",
            "How does the sign-on process work?",
            "What CICS operations does the account update program perform?",
            "What copybooks are shared across the most programs?",
            "How does the batch statement generation work?",
        ],
    },
    "star-trek": {
        "dir": str(_test_codebases / "star-trek"),
        "label": "Star Trek — Classic COBOL Game (1 program, 1.6K LOC)",
        "questions": [
            "How does the game initialize the galaxy quadrant map?",
            "What happens when a torpedo is fired?",
            "How is damage to the Enterprise tracked and repaired?",
            "What determines if Klingons attack and how much damage they deal?",
            "How does the short-range sensor scan work?",
        ],
    },
    "taxe-fonciere": {
        "dir": str(_test_codebases / "taxe-fonciere"),
        "label": "Taxe Foncière — French Property Tax (6 programs, 2.3K LOC)",
        "questions": [
            "How is the cotisation communale (municipal tax) calculated?",
            "What are the different frais (fee) rates and how are they split?",
            "How does the year dispatcher route to the right calculator?",
            "What is the CAAA (Chambre d'Agriculture d'Alsace) special case?",
            "How are tax rates retrieved from the TAUDIS file?",
            "What is the 1-euro rebalancing rule for frais?",
            "What are the OM (ordures ménagères) zone rate categories?",
        ],
    },
    "legacy-benchmark": {
        "dir": str(_test_codebases / "legacy-benchmark"),
        "label": "COBOL Legacy Benchmark — Investment Portfolio Management (42 programs, 7K LOC)",
        "questions": [
            "How does PORTTRAN validate and apply a transaction to a portfolio position?",
            "What is the call chain from INQONLN down to the DB2 layer?",
            "How does ERRPROC handle errors — what copybooks and data structures does it use?",
            "Which programs are responsible for batch position updates and what is the sequence?",
            "How does SECMGR enforce security checks for the online inquiry system?",
            "What copybooks are shared across the most programs and what do they define?",
            "How does the batch checkpoint/restart logic (CKPRST) work?",
            "What is the audit trail mechanism — which programs write to AUDITLOG?",
        ],
    },
    "bankdemo": {
        "dir": str(_test_codebases / "bankdemo"),
        "label": "BankDemo — Micro Focus CICS Banking Demo (164 files, 34K LOC)",
        "questions": [
            "How does the bank menu program route to different transaction screens?",
            "What is the account inquiry and update flow?",
            "How are VSAM file reads and writes structured across the programs?",
            "Which programs handle credit and debit operations?",
            "How does the transfer funds operation work end-to-end?",
            "What copybooks define the core account and customer data structures?",
        ],
    },
    "cbsa": {
        "dir": str(_test_codebases / "cbsa"),
        "label": "CBSA — IBM CICS Banking Sample Application (29 programs, 27K LOC)",
        "questions": [
            "How does CREACC create a new account and what validations does it apply?",
            "What is the debit/credit (DBCRFUN) logic and how does it update balances?",
            "How do the CRDTAGY1-5 credit agency programs work — what do they simulate?",
            "What is the full call chain for a customer inquiry (INQCUST)?",
            "How does XFRFUN handle fund transfers between accounts?",
            "Which copybooks define the core data structures shared across all programs?",
            "How does DELCUS handle cascading deletion of a customer and their accounts?",
        ],
    },
}


# ── Shared helpers ────────────────────────────────────────────────────────────

def _register_all():
    for name, info in KNOWN_CODEBASES.items():
        if os.path.isdir(info["dir"]):
            register_codebase(name, info["dir"])


def _print_header():
    print("\033[38;5;39m")
    print(r"  __  __                                          _      ")
    print(r" |  \/  | __ _ ___  __ _ _   _  ___ _ __ __ _  __| | ___ ")
    print(r" | |\/| |/ _` / __|/ _` | | | |/ _ \ '__/ _` |/ _` |/ _ \\")
    print(r" | |  | | (_| \__ \ (_| | |_| |  __/ | | (_| | (_| |  __/")
    print(r" |_|  |_|\__,_|___/\__, |\__,_|\___|_|  \__,_|\__,_|\___|")
    print(r"                      |_|     COBOL Intelligence Engine  ")
    print("\033[0m")


def _print_codebase_menu():
    print("  \033[38;5;214mAvailable codebases:\033[0m")
    for name, info in KNOWN_CODEBASES.items():
        marker = "\033[38;5;40m●\033[0m" if os.path.isdir(info["dir"]) else "\033[38;5;240m○\033[0m"
        print(f"    {marker} \033[1m{name}\033[0m — {info['label']}")
    print()


def _print_active(active):
    info = KNOWN_CODEBASES.get(active, {})
    print(f"  \033[38;5;40mActive:\033[0m \033[1m{active}\033[0m — {info.get('label', '')}")
    print(f"  Type a question, a number for a suggestion, or /help for commands.\n")


def _print_suggestions(active):
    info = KNOWN_CODEBASES.get(active, {})
    questions = info.get("questions", [])
    if questions:
        print(f"  \033[38;5;240mSuggested questions for {active}:\033[0m")
        for i, q in enumerate(questions, 1):
            print(f"    \033[38;5;245m{i}.\033[0m {q}")
        print()


def _print_sources(result: QueryResult):
    if not result.sources:
        return
    print(f"\n  \033[38;5;240m--- Sources ({len(result.sources)}) ---\033[0m")
    for i, s in enumerate(result.sources[:5], 1):
        c = s.chunk
        score_pct = int(s.score * 20)
        score_bar = "\033[38;5;40m" + "█" * score_pct + "\033[38;5;240m" + "░" * (20 - score_pct) + "\033[0m"
        label = c.file_path
        if c.program_name:
            label += f" ({c.program_name}"
            if c.paragraph_name:
                label += f"::{c.paragraph_name}"
            label += ")"
        print(f"  {i}. {score_bar} {s.score:.3f}  {label}:{c.start_line}-{c.end_line}")
        extras = []
        if c.calls: extras.append(f"calls={','.join(c.calls[:3])}")
        if c.performs: extras.append(f"performs={','.join(c.performs[:3])}")
        if c.cics_ops: extras.append(f"cics={','.join(c.cics_ops[:3])}")
        if extras:
            print(f"     \033[38;5;240m{' | '.join(extras)}\033[0m")


def _print_help():
    print("  \033[38;5;214mCommands:\033[0m")
    print("    /switch          — change active codebase")
    print("    /suggest         — show suggested questions")
    print("    /all             — query across all codebases")
    print("    /help            — show this help")
    print("    /quit            — exit")
    print("    1-7              — run a suggested question")
    print()
    print("  \033[38;5;214mGraph Commands:\033[0m")
    print("    /summary         — estate-level codebase overview")
    print("    /readiness       — ranked reimplementation readiness scores")
    print("    /readiness <pgm> — detailed readiness assessment for one program")
    print("    /impact <name>   — blast-radius analysis for a program or copybook")
    print("    /deps <name>     — show dependency tree for a program")
    print("    /trace <field>   — trace a data field through MOVE/COMPUTE/CALL chains")
    print("    /spec <pgm>      — generate reimplementation specification")
    print("    /rules <pgm>     — extract structured business rules with evidence")
    print("    /hotspots        — hub programs with highest connectivity (change risk)")
    print("    /isolated        — leaf programs with no callees (reimplementation candidates)")
    print("    /dead            — dead code detection (unreachable paragraphs, orphans)")
    print("    /screens          — CICS screen flow summary & navigation")
    print("    /screens <map>   — screen detail (input/output fields)")
    print("    /screens render <map> — ASCII terminal rendering")
    print("    /jobs             — batch job flow summary")
    print("    /jobs <name>     — job detail (steps, datasets)")
    print("    /jobs pgm <name> — find jobs that execute a program")
    print("    /dict             — copybook data dictionary summary")
    print("    /dict <name>     — lookup a field or inspect a copybook")
    print("    /complexity      — cyclomatic complexity for all programs")
    print("    /complexity <pgm>— detail for a single program")
    print("    /files           — file/dataset contract mapping (shared data boundaries)")
    print()
    print("  \033[38;5;214mExport & Estimation:\033[0m")
    print("    /estimate        — migration effort estimation (person-days, waves, risk)")
    print("    /spec-gen [pgm]  — generate behavioral specs (no API keys needed)")
    print("    /skeleton [pgm]  — generate Python module skeletons from COBOL")
    print("    /test-gen [pgm]  — generate pytest test stubs for modernized code")
    print("    /xref <field>    — cross-reference a field across all programs")
    print("    /export          — export CSV + JSON (for Excel/JIRA/tooling)")
    print("    /report          — generate shareable HTML analysis report")
    print("    /eval            — run eval suite for active codebase")
    print("    /eval all        — run eval suite for all codebases")
    print()


# ── Import submodule helpers ──────────────────────────────────────────────────

from cli_graph import (
    get_graph as _get_graph_impl,
    suggest_similar as _suggest_similar,
    cmd_impact, cmd_deps, cmd_hotspots, cmd_isolated,
    cmd_dead, cmd_files, cmd_readiness, cmd_summary,
)
from cli_data import (
    cmd_dict, cmd_screens, cmd_jobs, cmd_trace, cmd_xref,
)
from cli_generate import (
    cmd_spec, cmd_rules, cmd_spec_gen, cmd_skeleton, cmd_test_gen,
    cmd_export, cmd_report, cmd_eval, cmd_complexity, cmd_estimate,
)


def _get_graph(active):
    return _get_graph_impl(active, KNOWN_CODEBASES)


# ── REPL ──────────────────────────────────────────────────────────────────────

def main():
    _register_all()

    from synthesis.chain import query_stream

    _print_header()
    _print_codebase_menu()

    available = [name for name, info in KNOWN_CODEBASES.items() if os.path.isdir(info["dir"])]
    if not available:
        print("  No codebases found. Run ingest.py first.")
        return

    active = available[0]
    _print_active(active)
    _print_suggestions(active)

    while True:
        try:
            prompt_label = f"\033[38;5;245m[{active}]\033[0m \033[38;5;39m>\033[0m "
            user_input = input(f"  {prompt_label}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye.")
            break

        if not user_input:
            continue

        if user_input in ("/quit", "/exit", "/q"):
            print("  Goodbye.")
            break

        if user_input == "/help":
            _print_help()
        elif user_input == "/suggest":
            _print_suggestions(active)
        elif user_input.startswith("/complexity"):
            cmd_complexity(user_input[len("/complexity"):].strip(), active, KNOWN_CODEBASES)
        elif user_input == "/estimate":
            cmd_estimate(active, KNOWN_CODEBASES, _get_graph)
        elif user_input == "/export":
            cmd_export(active, KNOWN_CODEBASES)
        elif user_input == "/report":
            cmd_report(active, KNOWN_CODEBASES)
        elif user_input.startswith("/eval"):
            cmd_eval(user_input[len("/eval"):].strip(), active)
        elif user_input == "/summary":
            cmd_summary(active, KNOWN_CODEBASES)
        elif user_input.startswith("/screens"):
            cmd_screens(user_input[len("/screens"):].strip(), active, KNOWN_CODEBASES)
        elif user_input.startswith("/jobs"):
            cmd_jobs(user_input[len("/jobs"):].strip(), active, KNOWN_CODEBASES)
        elif user_input.startswith("/dict"):
            cmd_dict(user_input[len("/dict"):].strip(), active, KNOWN_CODEBASES)
        elif user_input == "/dead":
            cmd_dead(active, KNOWN_CODEBASES)
        elif user_input == "/files":
            cmd_files(active, KNOWN_CODEBASES)
        elif user_input.startswith("/trace"):
            cmd_trace(user_input[len("/trace"):].strip(), active, KNOWN_CODEBASES)
        elif user_input.startswith("/xref"):
            cmd_xref(user_input[len("/xref"):].strip(), active, KNOWN_CODEBASES)
        elif user_input.startswith("/test-gen"):
            cmd_test_gen(user_input[len("/test-gen"):].strip(), active, KNOWN_CODEBASES, _get_graph, _suggest_similar)
        elif user_input.startswith("/skeleton"):
            cmd_skeleton(user_input[len("/skeleton"):].strip(), active, KNOWN_CODEBASES, _get_graph, _suggest_similar)
        elif user_input.startswith("/spec-gen"):
            cmd_spec_gen(user_input[len("/spec-gen"):].strip(), active, KNOWN_CODEBASES, _get_graph, _suggest_similar)
        elif user_input.startswith("/spec"):
            cmd_spec(user_input[len("/spec"):].strip(), active, KNOWN_CODEBASES, _get_graph, _suggest_similar, _print_sources)
        elif user_input.startswith("/rules"):
            cmd_rules(user_input[len("/rules"):].strip(), active, KNOWN_CODEBASES, _get_graph, _suggest_similar, _print_sources)
        elif user_input.startswith("/readiness"):
            cmd_readiness(user_input[len("/readiness"):].strip(), active, KNOWN_CODEBASES)
        elif user_input.startswith("/impact"):
            cmd_impact(user_input[len("/impact"):].strip(), active, KNOWN_CODEBASES)
        elif user_input.startswith("/deps"):
            cmd_deps(user_input[len("/deps"):].strip(), active, KNOWN_CODEBASES)
        elif user_input == "/hotspots":
            cmd_hotspots(active, KNOWN_CODEBASES)
        elif user_input == "/isolated":
            cmd_isolated(active, KNOWN_CODEBASES)
        elif user_input == "/switch":
            print()
            for i, name in enumerate(available, 1):
                marker = "\033[38;5;40m>\033[0m" if name == active else " "
                print(f"    {marker} {i}. {name}")
            print()
            try:
                choice = input("    Pick a number: ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(available):
                    active = available[idx]
                    print()
                    _print_active(active)
                    _print_suggestions(active)
                else:
                    print("    Invalid choice.")
            except (ValueError, EOFError, KeyboardInterrupt):
                pass
        else:
            # RAG query (or /all shortcut)
            codebase_filter = active
            if user_input == "/all":
                print("  \033[38;5;245mQuerying all codebases. Enter your question:\033[0m")
                try:
                    user_input = input(f"  \033[38;5;39m>\033[0m ").strip()
                except (EOFError, KeyboardInterrupt):
                    continue
                if not user_input:
                    continue
                codebase_filter = None

            info = KNOWN_CODEBASES.get(active, {})
            questions = info.get("questions", [])
            if user_input.isdigit() and 1 <= int(user_input) <= len(questions):
                user_input = questions[int(user_input) - 1]
                print(f"  \033[38;5;245m{user_input}\033[0m")

            print()
            result = None
            sys.stdout.write("  ")
            for token in query_stream(user_input, codebase_filter=codebase_filter):
                if isinstance(token, str):
                    sys.stdout.write(token)
                    sys.stdout.flush()
                else:
                    result = token

            if result:
                _print_sources(result)
                print(f"\n  \033[38;5;240m[{result.latency_ms:.0f}ms]\033[0m\n")


if __name__ == "__main__":
    main()
