"""
Generation and export CLI commands: spec (RAG), rules (RAG), spec-gen,
skeleton, test-gen, export, report, eval, complexity, estimate.
"""

import os
import sys
from pathlib import Path


# ── /spec ─────────────────────────────────────────────────────────────────────

def cmd_spec(arg, active, known_codebases, get_graph_fn, suggest_similar_fn, print_sources_fn):
    if not arg:
        print("  \033[38;5;196mUsage: /spec <program_name>\033[0m")
        return

    graph = get_graph_fn(active)
    target = arg.upper()

    if graph and target not in graph.program_names():
        print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
        suggest_similar_fn(target, graph)
        return

    print(f"\n  \033[38;5;214mGenerating reimplementation spec for {target}...\033[0m\n")

    structural_parts = []
    if graph:
        enrichment = graph.enrichment_for(target)
        readiness = graph.readiness_score(target)
        node = graph.nodes.get(f"PGM:{target}", {})
        meta = node.get("metadata", {})
        structural_parts += [
            f"Program: {target}",
            f"Code lines: {meta.get('code_lines', 'unknown')}",
            f"Paragraphs: {meta.get('paragraph_count', 'unknown')}",
            f"Readiness score: {readiness['composite']}/100",
        ]
        if enrichment["callers"]:
            structural_parts.append(f"Called by: {', '.join(enrichment['callers'])}")
        if enrichment["callees"]:
            structural_parts.append(f"Calls: {', '.join(enrichment['callees'])}")
        if enrichment["copybooks"]:
            structural_parts.append(f"Copybooks: {', '.join(enrichment['copybooks'])}")
        if enrichment["programs_sharing_copybooks"]:
            structural_parts.append(f"Shares copybooks with: {', '.join(enrichment['programs_sharing_copybooks'][:5])}")
        file_edges = [
            e for e in graph.edges
            if e["source"] == f"PGM:{target}" and e["type"] in ("READS_FILE", "CICS_IO")
        ]
        if file_edges:
            files = {
                f"{graph.nodes.get(e['target'], {}).get('name', e['target'])} ({e['type']})"
                for e in file_edges
            }
            structural_parts.append(f"File/dataset I/O: {', '.join(sorted(files))}")
        has_cics = any(e["type"] == "CICS_IO" for e in graph.edges if e["source"] == f"PGM:{target}")
        structural_parts.append(f"Type: {'CICS Online' if has_cics else 'Batch'}")

    from synthesis.chain import _retrieve_and_prepare, _get_llm, _build_sources, _print_timing
    from synthesis.prompts import SPEC_PROMPT_TEMPLATE
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    import time

    question = f"Show all code for program {target}: PROCEDURE DIVISION, DATA DIVISION, all paragraphs, CICS operations, file I/O, and business logic"
    start = time.perf_counter()
    reranked, code_context, timing = _retrieve_and_prepare(question, codebase_filter=active)

    prompt = ChatPromptTemplate.from_template(SPEC_PROMPT_TEMPLATE)
    chain = prompt | _get_llm() | StrOutputParser()

    t4 = time.perf_counter()
    sys.stdout.write("  ")
    answer_parts = []
    for token in chain.stream({
        "structural_context": "\n".join(structural_parts),
        "code_context": code_context,
        "program": target,
    }):
        answer_parts.append(token)
        sys.stdout.write(token)
        sys.stdout.flush()
    timing["llm_ms"] = (time.perf_counter() - t4) * 1000
    timing["total_ms"] = (time.perf_counter() - start) * 1000
    _print_timing(timing)

    from rag_models import QueryResult
    result = QueryResult(
        query=question,
        answer="".join(answer_parts),
        sources=_build_sources(reranked),
        latency_ms=timing["total_ms"],
    )
    print_sources_fn(result)
    print()


# ── /rules ────────────────────────────────────────────────────────────────────

def cmd_rules(arg, active, known_codebases, get_graph_fn, suggest_similar_fn, print_sources_fn):
    if not arg:
        print("  \033[38;5;196mUsage: /rules <program_name>\033[0m")
        return

    graph = get_graph_fn(active)
    target = arg.upper()

    if graph and target not in graph.program_names():
        print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
        suggest_similar_fn(target, graph)
        return

    print(f"\n  \033[38;5;214mExtracting business rules from {target}...\033[0m\n")

    from synthesis.chain import _retrieve_and_prepare, _get_llm, _build_sources, _print_timing
    from synthesis.prompts import RULES_PROMPT_TEMPLATE
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from rag_models import QueryResult
    import time

    question = f"Show all the code for program {target}, including all paragraphs, PROCEDURE DIVISION, and DATA DIVISION"
    start = time.perf_counter()
    reranked, context, timing = _retrieve_and_prepare(question, codebase_filter=active)

    prompt = ChatPromptTemplate.from_template(RULES_PROMPT_TEMPLATE)
    chain = prompt | _get_llm() | StrOutputParser()

    t4 = time.perf_counter()
    sys.stdout.write("  ")
    answer_parts = []
    for token in chain.stream({"context": context, "program": target}):
        answer_parts.append(token)
        sys.stdout.write(token)
        sys.stdout.flush()
    timing["llm_ms"] = (time.perf_counter() - t4) * 1000
    timing["total_ms"] = (time.perf_counter() - start) * 1000
    _print_timing(timing)

    result = QueryResult(
        query=question,
        answer="".join(answer_parts),
        sources=_build_sources(reranked),
        latency_ms=timing["total_ms"],
    )
    print_sources_fn(result)
    print()


# ── /spec-gen ─────────────────────────────────────────────────────────────────

def cmd_spec_gen(arg, active, known_codebases, get_graph_fn, suggest_similar_fn):
    info = known_codebases.get(active, {})
    codebase_dir = info.get("dir", "")
    if not codebase_dir:
        print(f"  \033[38;5;196mCodebase directory not found for {active}.\033[0m")
        return

    from spec_generator import generate_all_specs, generate_program_spec, render_spec_markdown, _load_program_data
    analysis_dir = os.path.join(codebase_dir, "_analysis")

    if arg:
        target = arg.upper()
        graph = get_graph_fn(active)
        if not graph:
            print(f"  \033[38;5;196mNo analysis graph found for {active}.\033[0m")
            return
        if target not in graph.program_names():
            print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
            suggest_similar_fn(target, graph)
            return
        print(f"  \033[38;5;214mGenerating behavioral spec for {target}...\033[0m\n")
        program_data = _load_program_data(Path(analysis_dir))
        spec = generate_program_spec(target, graph, program_data, codebase_dir)
        if spec:
            md = render_spec_markdown(spec)
            specs_dir = os.path.join(analysis_dir, "specs")
            os.makedirs(specs_dir, exist_ok=True)
            path = os.path.join(specs_dir, f"{target}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(md)
            print(md)
            print(f"\n  \033[38;5;40mSpec written to:\033[0m {path}\n")
        else:
            print(f"  \033[38;5;196mCould not generate spec for {target}.\033[0m")
    else:
        print(f"  \033[38;5;214mGenerating behavioral specs for all programs in {active}...\033[0m")
        results = generate_all_specs(codebase_dir)
        specs_dir = os.path.join(analysis_dir, "specs")
        print(f"  \033[38;5;40mGenerated {len(results)} specs in:\033[0m {specs_dir}")
        print(f"  \033[38;5;245mSee INDEX.md for the full listing.\033[0m\n")


# ── /skeleton ─────────────────────────────────────────────────────────────────

def cmd_skeleton(arg, active, known_codebases, get_graph_fn, suggest_similar_fn):
    info = known_codebases.get(active, {})
    codebase_dir = info.get("dir", "")
    if not codebase_dir:
        print(f"  \033[38;5;196mCodebase directory not found for {active}.\033[0m")
        return

    from skeleton_generator import generate_all_skeletons, generate_skeleton, _cobol_name_to_python
    from spec_generator import generate_program_spec, _load_program_data
    analysis_dir = os.path.join(codebase_dir, "_analysis")

    if arg:
        target = arg.upper()
        graph = get_graph_fn(active)
        if not graph:
            print(f"  \033[38;5;196mNo analysis graph found for {active}.\033[0m")
            return
        if target not in graph.program_names():
            print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
            suggest_similar_fn(target, graph)
            return
        print(f"  \033[38;5;214mGenerating Python skeleton for {target}...\033[0m\n")
        program_data = _load_program_data(Path(analysis_dir))
        spec = generate_program_spec(target, graph, program_data, codebase_dir)
        if spec:
            code = generate_skeleton(spec)
            skeletons_dir = os.path.join(analysis_dir, "skeletons")
            os.makedirs(skeletons_dir, exist_ok=True)
            path = os.path.join(skeletons_dir, f"{_cobol_name_to_python(target)}.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            print(code)
            print(f"\n  \033[38;5;40mSkeleton written to:\033[0m {path}\n")
        else:
            print(f"  \033[38;5;196mCould not generate skeleton for {target}.\033[0m")
    else:
        print(f"  \033[38;5;214mGenerating Python skeletons for all programs in {active}...\033[0m")
        results = generate_all_skeletons(codebase_dir)
        skeletons_dir = os.path.join(analysis_dir, "skeletons")
        print(f"  \033[38;5;40mGenerated {len(results)} skeletons in:\033[0m {skeletons_dir}")
        print(f"  \033[38;5;245mEach .py file is a compilable Python module stub.\033[0m\n")


# ── /test-gen ─────────────────────────────────────────────────────────────────

def cmd_test_gen(arg, active, known_codebases, get_graph_fn, suggest_similar_fn):
    info = known_codebases.get(active, {})
    codebase_dir = info.get("dir", "")
    if not codebase_dir:
        print(f"  \033[38;5;196mCodebase directory not found for {active}.\033[0m")
        return

    from test_generator import generate_all_test_suites, generate_test_suite
    from spec_generator import generate_program_spec, _load_program_data
    from skeleton_generator import _cobol_name_to_python
    analysis_dir = os.path.join(codebase_dir, "_analysis")

    if arg:
        target = arg.upper()
        graph = get_graph_fn(active)
        if not graph:
            print(f"  \033[38;5;196mNo analysis graph found for {active}.\033[0m")
            return
        if target not in graph.program_names():
            print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
            suggest_similar_fn(target, graph)
            return
        print(f"  \033[38;5;214mGenerating test suite for {target}...\033[0m\n")
        program_data = _load_program_data(Path(analysis_dir))
        spec = generate_program_spec(target, graph, program_data, codebase_dir)
        if spec:
            code = generate_test_suite(spec)
            tests_dir = os.path.join(analysis_dir, "generated_tests")
            os.makedirs(tests_dir, exist_ok=True)
            path = os.path.join(tests_dir, f"test_{_cobol_name_to_python(target)}.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            print(code)
            print(f"\n  \033[38;5;40mTest suite written to:\033[0m {path}\n")
        else:
            print(f"  \033[38;5;196mCould not generate tests for {target}.\033[0m")
    else:
        print(f"  \033[38;5;214mGenerating test suites for all programs in {active}...\033[0m")
        results = generate_all_test_suites(codebase_dir)
        total = sum(r.test_count for r in results.values())
        tests_dir = os.path.join(analysis_dir, "generated_tests")
        print(f"  \033[38;5;40mGenerated {len(results)} test files ({total} test cases) in:\033[0m {tests_dir}\n")


# ── /export ───────────────────────────────────────────────────────────────────

def cmd_export(active, known_codebases):
    info = known_codebases.get(active, {})
    codebase_dir = info.get("dir", "")
    if not codebase_dir:
        print(f"  \033[38;5;196mCodebase directory not found for {active}.\033[0m")
        return

    print(f"  \033[38;5;214mExporting analysis data for {active}...\033[0m")
    from export import export_all
    try:
        result = export_all(codebase_dir)
        print(f"  \033[38;5;40mExported {result['programs']} programs:\033[0m")
        print(f"    CSV:  {result['csv']}")
        print(f"    JSON: {result['json']}")
        print(f"  \033[38;5;245mCSV is importable into Excel/JIRA. JSON has full analysis data.\033[0m\n")
    except Exception as e:
        print(f"  \033[38;5;196mError: {e}\033[0m")


# ── /report ───────────────────────────────────────────────────────────────────

def cmd_report(active, known_codebases):
    info = known_codebases.get(active, {})
    codebase_dir = info.get("dir", "")
    if not codebase_dir:
        print(f"  \033[38;5;196mCodebase directory not found for {active}.\033[0m")
        return

    print(f"  \033[38;5;214mGenerating analysis report for {active}...\033[0m")
    from render_report import generate_report
    try:
        path = generate_report(codebase_dir)
        print(f"  \033[38;5;40mReport written to:\033[0m {path}")
        print(f"  \033[38;5;245mOpen in a browser to view.\033[0m\n")
    except Exception as e:
        print(f"  \033[38;5;196mError: {e}\033[0m")


# ── /eval ─────────────────────────────────────────────────────────────────────

def cmd_eval(arg, active):
    from evals.runner import run_all, print_report, save_results
    scores = run_all() if arg == "all" else run_all(codebase_filter=active)
    print_report(scores)
    save_results(scores)


# ── /complexity ───────────────────────────────────────────────────────────────

def cmd_complexity(arg, active, known_codebases):
    info = known_codebases.get(active, {})
    codebase_dir = info.get("dir", "")
    if not codebase_dir:
        print(f"  \033[38;5;196mCodebase directory not found for {active}.\033[0m")
        return

    from complexity import compute_all, compute_complexity, complexity_grade
    W, R, D, H, B = "\033[1m", "\033[0m", "\033[38;5;240m", "\033[38;5;214m", "\033[38;5;39m"
    G, Y, RED = "\033[38;5;40m", "\033[38;5;220m", "\033[38;5;196m"

    if arg:
        target = arg.upper()
        for cbl in Path(codebase_dir).rglob("*.cbl"):
            if cbl.stem.upper() == target:
                r = compute_complexity(str(cbl))
                if r:
                    grade = complexity_grade(r.cyclomatic, 500)
                    gc = G if grade == "LOW" else (Y if grade == "MODERATE" else RED)
                    print(f"\n  {H}Complexity: {r.program}{R}")
                    print(f"    Cyclomatic:    {W}{r.cyclomatic}{R} {gc}({grade}){R}")
                    print(f"    Max nesting:   {W}{r.max_nesting}{R}")
                    print(f"    Decisions:     {W}{r.decision_points}{R}")
                    print(f"    Paragraphs:    {W}{r.paragraphs}{R}")
                    print(f"    Avg/paragraph: {W}{r.avg_complexity_per_paragraph}{R}")
                    if r.hotspot_paragraphs:
                        print(f"\n    {H}Complex Paragraphs:{R}")
                        for hp in r.hotspot_paragraphs[:8]:
                            print(f"      {B}{hp['paragraph']}{R}: {hp['decisions']} decisions (CC={hp['complexity']})")
                    print()
                    return
        print(f"  \033[38;5;196mProgram '{arg}' not found.\033[0m")
        return

    results = compute_all(codebase_dir)
    results.sort(key=lambda r: -r.cyclomatic)
    total_cc = sum(r.cyclomatic for r in results)
    avg_cc = total_cc / len(results) if results else 0
    max_r = results[0] if results else None

    print(f"\n  {H}Cyclomatic Complexity: {active}{R}")
    print(f"  {D}{'-' * 55}{R}")
    print(f"    Programs analyzed: {W}{len(results)}{R}")
    print(f"    Total complexity:  {W}{total_cc}{R}")
    print(f"    Average per program: {W}{avg_cc:.1f}{R}")
    if max_r:
        print(f"    Most complex:      {W}{max_r.program}{R} (CC={max_r.cyclomatic}, nest={max_r.max_nesting})")
    print()
    print(f"  {D}{'Program':<14} {'CC':>4} {'Nest':>4} {'Decs':>5} {'Paras':>5} {'Grade':<10}{R}")
    print(f"  {D}{'-' * 48}{R}")
    for r in results:
        grade = complexity_grade(r.cyclomatic, 500)
        gc = G if grade == "LOW" else (Y if grade == "MODERATE" else RED)
        print(f"  {r.program:<14} {r.cyclomatic:>4} {r.max_nesting:>4} {r.decision_points:>5} {r.paragraphs:>5} {gc}{grade:<10}{R}")
    print()


# ── /estimate ─────────────────────────────────────────────────────────────────

def cmd_estimate(active, known_codebases, get_graph_fn):
    gi = get_graph_fn(active)
    if not gi:
        print(f"  \033[38;5;196mNo analysis data found for {active}. Run analyze.py first.\033[0m")
        return

    from effort_estimator import estimate_estate
    W, R, D, H, B = "\033[1m", "\033[0m", "\033[38;5;240m", "\033[38;5;214m", "\033[38;5;39m"
    G, Y, RED = "\033[38;5;40m", "\033[38;5;220m", "\033[38;5;196m"

    readiness = gi.readiness_ranking()
    dead = gi.dead_code_analysis()
    result = estimate_estate(readiness, dead)
    s = result["summary"]

    print(f"\n  {H}Migration Effort Estimate: {active}{R}")
    print(f"  {D}{'=' * 55}{R}\n")
    print(f"  {W}Estate Overview{R}")
    print(f"    Programs:        {W}{s['total_programs']}{R}")
    print(f"    Total code LOC:  {W}{s['total_loc']:,}{R}")
    print(f"    Dead code LOC:   {D}{s['dead_code_loc']:,} (can skip){R}")
    print()
    print(f"  {W}Effort Estimate{R}")
    print(f"    Total:           {W}{s['total_effort_days']:.0f} person-days{R} ({s['total_effort_weeks']:.1f} weeks / {s['total_effort_months']:.1f} months)")
    print(f"    Batch programs:  {B}{s['batch_effort_days']:.0f} days{R}")
    print(f"    CICS programs:   {Y}{s['cics_effort_days']:.0f} days{R}")
    print()
    print(f"  {W}Risk Distribution{R}")
    print(f"    Low risk:        {G}{s['low_risk_count']}{R}")
    print(f"    High risk:       {RED}{s['high_risk_count']}{R}")
    print(f"    Quick wins:      {G}{s['quick_win_count']}{R}")
    print()
    print(f"  {W}Migration Waves{R}")
    for wave in result["waves"]:
        if wave["program_count"] == 0:
            continue
        print(f"    {H}{wave['name']}{R}")
        print(f"      {wave['program_count']} programs, {wave['effort_days']:.0f} person-days")
        pgm_list = ", ".join(wave["programs"][:8])
        if wave["program_count"] > 8:
            pgm_list += f" +{wave['program_count'] - 8}"
        print(f"      {D}{pgm_list}{R}")
        print()

    if result["quick_wins"]:
        print(f"  {G}Recommended Starting Points (Quick Wins):{R}")
        for pgm in result["quick_wins"][:5]:
            est = next((e for e in result["estimates"] if e.program == pgm), None)
            if est:
                print(f"    {B}{pgm}{R}: {est.effort_days:.1f} days, {est.code_lines} LOC [{est.category}]")
        print()

    print(f"  {W}Per-Program Breakdown:{R}")
    print(f"  {D}{'Program':<14} {'LOC':>5} {'Type':<12} {'Ready':>5} {'Days':>6} {'Risk':<8}{R}")
    print(f"  {D}{'-' * 56}{R}")
    for est in sorted(result["estimates"], key=lambda e: -e.effort_days):
        risk_color = G if est.risk_level == "LOW" else (Y if est.risk_level == "MEDIUM" else RED)
        print(f"  {est.program:<14} {est.code_lines:>5} {est.category:<12} {est.readiness_score:>5.0f} {est.effort_days:>6.1f} {risk_color}{est.risk_level:<8}{R}")
        if est.notes:
            print(f"  {D}{'':14} {', '.join(est.notes)}{R}")

    print(f"\n  {D}Note: Estimates cover analysis + design + coding + unit testing.")
    print(f"  Integration testing, UAT, data migration, and deployment are not included.{R}\n")
