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
"""

import argparse
import sys
import os
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
}


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
    for i, (name, info) in enumerate(KNOWN_CODEBASES.items(), 1):
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


def _get_graph(codebase):
    from synthesis.chain import get_graph_for_codebase
    return get_graph_for_codebase(codebase)


def _cmd_impact(arg, active):
    """Blast-radius analysis: walk the graph and use RAG to explain each dependency."""
    if not arg:
        print("  \033[38;5;196mUsage: /impact <program_name|copybook_name>\033[0m")
        return

    graph = _get_graph(active)
    if not graph:
        print(f"  \033[38;5;196mNo analysis graph found for {active}. Run analyze.py first.\033[0m")
        return

    target = arg.upper()

    node_id = None
    if target in graph.program_names():
        node_id = f"PGM:{target}"
    elif target in graph.copybook_names():
        node_id = f"CPY:{target}"
    else:
        for nid, node in graph.nodes.items():
            if node["name"].upper() == target:
                node_id = nid
                break

    if not node_id:
        print(f"  \033[38;5;196mNode '{target}' not found in graph.\033[0m")
        _suggest_similar(target, graph)
        return

    impact = graph.impact_of(node_id, max_depth=3)
    node_type = graph.nodes[node_id]["type"]

    print(f"\n  \033[38;5;214mImpact Analysis: {target} ({node_type})\033[0m")
    print(f"  \033[38;5;240m{'—' * 50}\033[0m")

    if not impact:
        print(f"  No upstream dependencies found. This node is not depended upon.")
        return

    print(f"  \033[38;5;245m{len(impact)} programs affected:\033[0m\n")

    for name, distance in impact:
        risk = "\033[38;5;196mHIGH\033[0m" if distance == 1 else (
            "\033[38;5;214mMEDIUM\033[0m" if distance == 2 else "\033[38;5;245mLOW\033[0m"
        )
        enrichment = graph.enrichment_for(name)
        detail_parts = []
        if enrichment["callers"]:
            detail_parts.append(f"called by: {', '.join(enrichment['callers'][:3])}")
        if enrichment["callees"]:
            detail_parts.append(f"calls: {', '.join(enrichment['callees'][:3])}")
        if enrichment["copybooks"]:
            shared_with_target = [
                cb for cb in enrichment["copybooks"]
                if target in [u.upper() for u in graph.copybook_users(cb)]
                or cb.upper() == target
            ]
            if shared_with_target:
                detail_parts.append(f"shared copybooks: {', '.join(shared_with_target[:3])}")

        detail = f"  \033[38;5;240m{' | '.join(detail_parts)}\033[0m" if detail_parts else ""
        bar = "█" * min(distance, 5)
        print(f"    {risk}  dist={distance}  {bar}  \033[1m{name}\033[0m")
        if detail:
            print(f"    {detail}")

    # Follow up with RAG explanation
    print(f"\n  \033[38;5;245mGenerating explanation...\033[0m\n")
    affected_names = ", ".join(n for n, _ in impact[:5])
    question = f"What is the relationship between {target} and these programs: {affected_names}? How would a change to {target} affect them?"

    from synthesis.chain import query_stream
    sys.stdout.write("  ")
    result = None
    for token in query_stream(question, codebase_filter=active):
        if isinstance(token, str):
            sys.stdout.write(token)
            sys.stdout.flush()
        else:
            result = token
    if result:
        _print_sources(result)
        print(f"\n  \033[38;5;240m[{result.latency_ms:.0f}ms]\033[0m")
    print()


def _cmd_deps(arg, active):
    """Show dependency tree for a program."""
    if not arg:
        print("  \033[38;5;196mUsage: /deps <program_name>\033[0m")
        return

    graph = _get_graph(active)
    if not graph:
        print(f"  \033[38;5;196mNo analysis graph found for {active}. Run analyze.py first.\033[0m")
        return

    target = arg.upper()
    if target not in graph.program_names():
        print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
        _suggest_similar(target, graph)
        return

    tree = graph.dependency_tree(target, max_depth=3)
    callers = graph.callers(target)

    print(f"\n  \033[38;5;214mDependency Tree: {target}\033[0m")
    print(f"  \033[38;5;240m{'—' * 50}\033[0m")

    if callers:
        print(f"\n  \033[38;5;245mCalled by:\033[0m")
        for c in callers:
            print(f"    ← \033[38;5;39m{c}\033[0m")

    print(f"\n  \033[38;5;245mCall tree (outgoing):\033[0m")
    _print_tree(tree, indent=4)

    copybooks = graph.copybooks_of(target)
    if copybooks:
        print(f"\n  \033[38;5;245mCopybooks ({len(copybooks)}):\033[0m")
        for cb in copybooks:
            users = graph.copybook_users(cb)
            others = [u for u in users if u != target]
            shared = f" \033[38;5;240m(also: {', '.join(others[:3])})\033[0m" if others else ""
            print(f"    📋 {cb}{shared}")

    enrichment = graph.enrichment_for(target)
    print(f"\n  \033[38;5;245mHub score: {enrichment['hub_score']:.1f}\033[0m")
    print()


def _print_tree(node, indent=0, prefix=""):
    name = node["name"]
    copybook_count = len(node.get("copybooks", []))
    cb_info = f" \033[38;5;240m[{copybook_count} copybooks]\033[0m" if copybook_count else ""
    print(f"{' ' * indent}{prefix}\033[1m{name}\033[0m{cb_info}")

    children = node.get("calls", [])
    for i, child in enumerate(children):
        is_last = (i == len(children) - 1)
        child_prefix = "└── " if is_last else "├── "
        _print_tree(child, indent + 4, child_prefix)


def _cmd_hotspots(active):
    """Show hub programs with highest connectivity — highest change risk."""
    graph = _get_graph(active)
    if not graph:
        print(f"  \033[38;5;196mNo analysis graph found for {active}. Run analyze.py first.\033[0m")
        return

    hubs = graph.hub_programs(top_n=15)

    print(f"\n  \033[38;5;214mHotspot Programs — {active}\033[0m")
    print(f"  \033[38;5;240mPrograms with highest connectivity (change risk)\033[0m")
    print(f"  \033[38;5;240m{'—' * 60}\033[0m\n")
    print(f"  {'Program':<20s} {'Score':>6s}  {'Callers':>8s}  {'Callees':>8s}  {'Copybooks':>10s}")
    print(f"  {'—'*20} {'—'*6}  {'—'*8}  {'—'*8}  {'—'*10}")

    for name, score in hubs:
        callers = len(graph.callers(name))
        callees = len(graph.callees(name))
        copybooks = len(graph.copybooks_of(name))
        bar_len = int(score * 2)
        bar = "\033[38;5;196m" + "█" * min(bar_len, 30) + "\033[0m"
        print(f"  \033[1m{name:<20s}\033[0m {score:>6.1f}  {callers:>8d}  {callees:>8d}  {copybooks:>10d}  {bar}")

    print()


def _cmd_isolated(active):
    """Show leaf programs with no callees — reimplementation candidates."""
    graph = _get_graph(active)
    if not graph:
        print(f"  \033[38;5;196mNo analysis graph found for {active}. Run analyze.py first.\033[0m")
        return

    leaves = graph.leaf_programs()
    components = graph.connected_components()

    print(f"\n  \033[38;5;214mIsolated Programs — {active}\033[0m")
    print(f"  \033[38;5;240mLeaf programs with no outgoing calls (reimplementation candidates)\033[0m")
    print(f"  \033[38;5;240m{'—' * 60}\033[0m\n")
    print(f"  {'Program':<20s} {'Callers':>8s}  {'Copybooks':>10s}  {'Hub Score':>10s}  Notes")
    print(f"  {'—'*20} {'—'*8}  {'—'*10}  {'—'*10}  {'—'*20}")

    for name in leaves:
        callers = graph.callers(name)
        copybooks = graph.copybooks_of(name)
        score = graph.degree_centrality(name)
        notes = []
        if not callers:
            notes.append("no callers (standalone)")
        elif len(callers) == 1:
            notes.append(f"single caller: {callers[0]}")
        shared = graph.programs_sharing_copybooks_with(name)
        if not shared:
            notes.append("no shared copybooks")

        note_str = "; ".join(notes) if notes else ""
        print(f"  \033[1m{name:<20s}\033[0m {len(callers):>8d}  {len(copybooks):>10d}  {score:>10.1f}  \033[38;5;240m{note_str}\033[0m")

    print(f"\n  \033[38;5;245m{len(leaves)} leaf programs out of {len(graph.program_names())} total\033[0m")
    print(f"  \033[38;5;245m{len(components)} connected components in call graph\033[0m\n")


_copybook_dicts: dict[str, object] = {}

def _get_copybook_dict(codebase):
    if codebase not in _copybook_dicts:
        from copybook_dict import CopybookDictionary
        info = KNOWN_CODEBASES.get(codebase, {})
        try:
            _copybook_dicts[codebase] = CopybookDictionary(info["dir"])
        except Exception:
            _copybook_dicts[codebase] = None
    return _copybook_dicts[codebase]


def _cmd_dict(arg, active):
    """Copybook data dictionary — lookup fields, search, or inspect a copybook."""
    cbd = _get_copybook_dict(active)
    if not cbd:
        print(f"  \033[38;5;196mNo copybook files found for {active}.\033[0m")
        return

    W = "\033[1m"
    R = "\033[0m"
    D = "\033[38;5;240m"
    H = "\033[38;5;214m"
    B = "\033[38;5;39m"

    if not arg:
        # Show summary
        s = cbd.summary()
        print(f"\n  {H}Copybook Data Dictionary: {active}{R}")
        print(f"  {D}{'-' * 55}{R}")
        print(f"    Copybooks parsed:  {W}{s['total_copybooks']}{R}")
        print(f"    Total fields:      {W}{s['total_fields']}{R}")
        print(f"    Total conditions:  {W}{s['total_conditions']}{R}")
        print(f"    Largest copybook:  {W}{s['largest_copybook']}{R} ({s['largest_field_count']} fields)")
        print(f"\n  {D}Usage: /dict <field_name> or /dict <copybook_name>{R}")
        print()
        return

    target = arg.upper()

    # Check if it's a copybook name
    detail = cbd.copybook_detail(target)
    if detail:
        print(f"\n  {H}Copybook: {target}{R}")
        print(f"  {D}{detail['source_file']}{R}")
        print(f"  {D}{detail['field_count']} fields, {detail['condition_count']} conditions{R}\n")

        for f in detail['fields']:
            indent = "  " * max(0, (f['level'] // 5) - 1) if f['level'] > 1 else ""
            pic_str = f" PIC {f['picture']}" if f['picture'] else ""
            type_str = f" {D}[{f['type']}]{R}" if f['type'] != 'group' else f" {D}[group]{R}"
            size_str = f" {D}{f['size_bytes']}B{R}" if f['size_bytes'] else ""
            redef_str = f" {D}REDEFINES {f['redefines']}{R}" if f['redefines'] else ""
            occ_str = f" {D}OCCURS {f['occurs']}{R}" if f['occurs'] else ""

            if f['level'] == 88:
                vals = ', '.join(f"'{v}'" for _, v in f['conditions'])
                print(f"    {indent}{D}88{R} {f['name']} {D}VALUE {vals}{R}")
            else:
                print(f"    {indent}{W}{f['level']:02d}{R} {B}{f['name']}{R}{pic_str}{type_str}{size_str}{redef_str}{occ_str}")
        print()
        return

    # Field lookup
    results = cbd.lookup_field(target)
    if results:
        print(f"\n  {H}Field: {target}{R}")
        print(f"  {D}Found in {len(results)} copybook(s){R}\n")
        for r in results:
            pic_str = f"PIC {r['picture']}" if r['picture'] else "(group)"
            usage_str = f" {r['usage']}" if r['usage'] else ""
            print(f"    {B}{r['copybook']}{R}: level-{r['level']:02d} {pic_str}{usage_str} [{r['type']}] {r['size_bytes']}B")
            if r['conditions']:
                for name, val in r['conditions']:
                    print(f"      {D}88 {name} VALUE '{val}'{R}")
            if r['redefines']:
                print(f"      {D}REDEFINES {r['redefines']}{R}")
        print()
        return

    # Search by partial match
    results = cbd.search_fields(target)
    if results:
        print(f"\n  {H}Search: '{target}'{R}")
        print(f"  {D}{len(results)} matching fields{R}\n")
        seen = set()
        for r in results[:25]:
            key = (r['copybook'], r['name'])
            if key in seen:
                continue
            seen.add(key)
            pic_str = f"PIC {r['picture']}" if r['picture'] else "(group)"
            print(f"    {B}{r['copybook']}{R}.{W}{r['name']}{R}: {pic_str} [{r['type']}]")
        if len(results) > 25:
            print(f"    {D}... +{len(results) - 25} more{R}")
        print()
        return

    print(f"  \033[38;5;196mNo field or copybook matching '{target}' found.\033[0m\n")


_screen_flow_indexes: dict[str, object] = {}

def _get_screen_flow(codebase):
    if codebase not in _screen_flow_indexes:
        from bms_parser import ScreenFlowIndex
        info = KNOWN_CODEBASES.get(codebase, {})
        try:
            _screen_flow_indexes[codebase] = ScreenFlowIndex(info["dir"])
        except Exception:
            _screen_flow_indexes[codebase] = None
    return _screen_flow_indexes[codebase]


def _cmd_screens(arg, active):
    """CICS screen flow — show screens, fields, navigation, ASCII render."""
    sfi = _get_screen_flow(active)
    if not sfi:
        print(f"  \033[38;5;196mNo BMS map files found for {active}.\033[0m")
        return

    W = "\033[1m"
    R = "\033[0m"
    D = "\033[38;5;240m"
    H = "\033[38;5;214m"
    B = "\033[38;5;39m"
    G = "\033[38;5;40m"

    if not arg:
        s = sfi.summary()
        print(f"\n  {H}CICS Screen Flow: {active}{R}")
        print(f"  {D}{'-' * 55}{R}")
        print(f"    Mapsets (screens):  {W}{s['total_mapsets']}{R}")
        print(f"    Total fields:      {W}{s['total_fields']}{R}")
        print(f"    Input fields:      {W}{s['total_input_fields']}{R}")
        print(f"    Programs w/screens:{W}{s['programs_with_screens']}{R}")
        print(f"    Screen transitions:{W}{s['screen_transitions']}{R}")

        flow = sfi.screen_flow()
        if flow["edges"]:
            print(f"\n  {H}Screen Navigation:{R}")
            for e in flow["edges"]:
                arrow = f"{D}--{e['type']}-->{R}"
                print(f"    {B}{e['from']}{R} {arrow} {B}{e['to']}{R}")

        print(f"\n  {D}Usage: /screens <mapset> for detail, /screens render <mapset> for ASCII{R}\n")
        return

    # Sub-command: /screens render <name>
    if arg.lower().startswith("render "):
        mapset = arg[7:].strip().upper()
        ascii_art = sfi.render_screen_ascii(mapset)
        if ascii_art:
            print(f"\n  {H}Screen: {mapset}{R}\n")
            for line in ascii_art.split("\n"):
                print(f"  {D}{line}{R}")
            print()
        else:
            print(f"  \033[38;5;196mMapset '{mapset}' not found.\033[0m")
        return

    # Screen detail
    detail = sfi.screen_detail(arg.upper())
    if not detail:
        matches = [n for n in sfi.mapsets if arg.upper() in n]
        if matches:
            print(f"\n  {H}Mapsets matching '{arg}':{R}")
            for m in sorted(matches):
                ms = sfi.mapsets[m]
                print(f"    {B}{m}{R} {D}{ms.description}{R}")
            print()
        else:
            print(f"  \033[38;5;196mMapset '{arg}' not found.\033[0m")
        return

    print(f"\n  {H}Screen: {detail['name']}{R}")
    if detail["description"]:
        print(f"  {D}{detail['description']}{R}")
    print(f"  {D}{detail['source_file']}{R}")
    print(f"  Programs: {', '.join(detail['programs'])}")

    for m in detail["maps"]:
        print(f"\n  {W}Map: {m['name']}{R} ({m['rows']}x{m['cols']})")

        if m["input_fields"]:
            print(f"\n    {G}Input Fields:{R}")
            for f in m["input_fields"]:
                color = f" {D}{f['color']}{R}" if f["color"] else ""
                print(f"      {B}{f['name'] or '(unnamed)'}{R} at ({f['row']},{f['col']}) len={f['length']}{color}")

        if m["output_fields"]:
            print(f"\n    {H}Output Fields:{R}")
            for f in m["output_fields"][:15]:
                print(f"      {B}{f['name']}{R} at ({f['row']},{f['col']}) len={f['length']}")
            if len(m["output_fields"]) > 15:
                print(f"      {D}+{len(m['output_fields']) - 15} more{R}")

        if m["labels"]:
            print(f"\n    {D}Labels:{R}")
            for lb in m["labels"][:10]:
                print(f"      ({lb['row']},{lb['col']}): {lb['text'][:50]}")
            if len(m["labels"]) > 10:
                print(f"      {D}+{len(m['labels']) - 10} more{R}")
    print()


_jcl_indexes: dict[str, object] = {}

def _get_jcl_index(codebase):
    if codebase not in _jcl_indexes:
        from jcl_parser import JclIndex
        info = KNOWN_CODEBASES.get(codebase, {})
        try:
            _jcl_indexes[codebase] = JclIndex(info["dir"])
        except Exception:
            _jcl_indexes[codebase] = None
    return _jcl_indexes[codebase]


def _cmd_jobs(arg, active):
    """JCL batch job flow — show jobs, steps, data flows, execution order."""
    jcl = _get_jcl_index(active)
    if not jcl:
        print(f"  \033[38;5;196mNo JCL files found for {active}.\033[0m")
        return

    W = "\033[1m"
    R = "\033[0m"
    D = "\033[38;5;240m"
    H = "\033[38;5;214m"
    B = "\033[38;5;39m"
    G = "\033[38;5;40m"

    if not arg:
        s = jcl.summary()
        print(f"\n  {H}Batch Job Flow: {active}{R}")
        print(f"  {D}{'-' * 55}{R}")
        print(f"    Total jobs:       {W}{s['total_jobs']}{R}")
        print(f"    Total steps:      {W}{s['total_steps']}{R}")
        print(f"    COBOL programs:   {W}{len(s['cobol_programs'])}{R}")
        print(f"    Utility programs: {W}{len(s['utility_programs'])}{R}")
        print(f"    Datasets:         {W}{s['total_datasets']}{R}")

        flows = jcl.dataset_flow()
        if flows:
            print(f"\n  {H}Cross-Job Data Flows:{R}")
            for f in flows:
                ds_short = f["dataset"].split(".")[-2] + "." + f["dataset"].split(".")[-1] if "." in f["dataset"] else f["dataset"]
                print(f"    {B}{f['producer']}{R} {D}-->{R} {B}{f['consumer']}{R} {D}via {ds_short}{R}")

        layers = jcl.execution_order()
        if layers:
            print(f"\n  {H}Execution Order ({len(layers)} layers):{R}")
            for i, layer in enumerate(layers):
                parallel = f" {D}(parallel){R}" if len(layer) > 1 else ""
                jobs_str = ", ".join(layer[:8])
                if len(layer) > 8:
                    jobs_str += f" +{len(layer) - 8}"
                print(f"    {G}Layer {i}{R}: {jobs_str}{parallel}")

        print(f"\n  {D}Usage: /jobs <job_name> for details, /jobs pgm <program> to find jobs{R}\n")
        return

    # Sub-command: /jobs pgm <name>
    if arg.lower().startswith("pgm "):
        pgm = arg[4:].strip().upper()
        jobs = jcl.jobs_for_program(pgm)
        if not jobs:
            print(f"  \033[38;5;196mNo jobs found that execute {pgm}.\033[0m")
            return
        print(f"\n  {H}Jobs executing {pgm}:{R}")
        for j in sorted(set(jobs)):
            detail = jcl.job_detail(j)
            desc = detail["description"][:60] if detail else ""
            print(f"    {B}{j}{R} {D}{desc}{R}")
        print()
        return

    # Job detail
    detail = jcl.job_detail(arg.upper())
    if not detail:
        # Try partial match
        matches = [n for n in jcl.jobs if arg.upper() in n]
        if matches:
            print(f"\n  {H}Jobs matching '{arg}':{R}")
            for m in sorted(matches):
                d = jcl.job_detail(m)
                print(f"    {B}{m}{R} {D}{d['description'][:60] if d else ''}{R}")
            print()
        else:
            print(f"  \033[38;5;196mJob '{arg}' not found. Use /jobs for a list.\033[0m")
        return

    print(f"\n  {H}Job: {detail['name']}{R}")
    if detail["description"]:
        print(f"  {D}{detail['description']}{R}")
    print(f"  {D}{detail['source_file']}{R}\n")

    for i, step in enumerate(detail["steps"]):
        is_util = step["is_utility"]
        pgm_color = D if is_util else G
        util_tag = f" {D}[utility]{R}" if is_util else ""
        cond_tag = f" {D}COND=({step['condition']}){R}" if step["condition"] else ""
        print(f"  {W}Step {i+1}: {step['name']}{R} -> {pgm_color}{step['program']}{R}{util_tag}{cond_tag}")
        for inp in step["inputs"]:
            ds_short = inp.split(".")[-1] if "." in inp else inp
            print(f"    {D}IN:  {ds_short}{R}")
        for out in step["outputs"]:
            ds_short = out.split(".")[-1] if "." in out else out
            print(f"    {B}OUT: {ds_short}{R}")
    print()


def _cmd_files(active):
    """File/dataset contract mapping — which programs share which files."""
    graph = _get_graph(active)
    if not graph:
        print(f"  \033[38;5;196mNo analysis graph found for {active}. Run analyze.py first.\033[0m")
        return

    W = "\033[1m"
    R = "\033[0m"
    D = "\033[38;5;240m"
    H = "\033[38;5;214m"
    B = "\033[38;5;39m"
    G = "\033[38;5;40m"

    # Collect file nodes and their program edges
    file_nodes = {
        nid: node for nid, node in graph.nodes.items()
        if node["type"] == "FILE"
    }
    map_nodes = {
        nid: node for nid, node in graph.nodes.items()
        if node["type"] == "MAP"
    }

    # Build file -> programs mapping with operation types
    file_programs: dict[str, list[dict]] = {}
    for edge in graph.edges:
        if edge["type"] in ("READS_FILE", "CICS_IO") and edge["target"].startswith("FILE:"):
            file_name = graph.nodes.get(edge["target"], {}).get("name", edge["target"])
            src_name = graph.nodes.get(edge["source"], {}).get("name", "")
            if not src_name or "::PARA:" in edge["source"]:
                continue
            evidence = edge.get("evidence", [{}])
            op = evidence[0].get("operation", "FILE_IO") if evidence else "FILE_IO"
            file_programs.setdefault(file_name, []).append({
                "program": src_name,
                "operation": op,
                "edge_type": edge["type"],
            })

    # Build map -> programs mapping
    map_programs: dict[str, list[dict]] = {}
    for edge in graph.edges:
        if edge["type"] == "CICS_IO" and edge["target"].startswith("MAP:"):
            map_name = graph.nodes.get(edge["target"], {}).get("name", edge["target"])
            src_name = graph.nodes.get(edge["source"], {}).get("name", "")
            if not src_name or "::PARA:" in edge["source"]:
                continue
            evidence = edge.get("evidence", [{}])
            op = evidence[0].get("operation", "SEND/RECEIVE") if evidence else "SEND/RECEIVE"
            map_programs.setdefault(map_name, []).append({
                "program": src_name,
                "operation": op,
            })

    print(f"\n  {H}File/Dataset Contract Map: {active}{R}")
    print(f"  {D}{'-' * 60}{R}")

    # Files/datasets
    if file_programs:
        print(f"\n  {H}Files & Datasets ({len(file_programs)}){R}")
        for file_name in sorted(file_programs.keys()):
            progs = file_programs[file_name]
            node = file_nodes.get(f"FILE:{file_name.upper()}", {})
            meta = node.get("metadata", {})
            org = meta.get("organization", "")
            org_str = f" [{org}]" if org else ""

            unique_progs = {}
            for p in progs:
                key = p["program"]
                if key not in unique_progs:
                    unique_progs[key] = set()
                unique_progs[key].add(p["operation"])

            shared = len(unique_progs) > 1
            sharing_marker = f" {H}** SHARED **{R}" if shared else ""

            print(f"\n    {W}{file_name}{R}{D}{org_str}{R}{sharing_marker}")
            for pgm_name, ops in sorted(unique_progs.items()):
                ops_str = ", ".join(sorted(ops))
                print(f"      {B}{pgm_name:<20s}{R} {D}{ops_str}{R}")

    # CICS Maps
    if map_programs:
        print(f"\n  {H}CICS Maps ({len(map_programs)}){R}")
        for map_name in sorted(map_programs.keys()):
            progs = map_programs[map_name]
            node = map_nodes.get(f"MAP:{map_name.upper()}", {})
            meta = node.get("metadata", {})
            mapset = meta.get("mapset", "")
            mapset_str = f" (mapset: {mapset})" if mapset else ""

            unique_progs = {}
            for p in progs:
                key = p["program"]
                if key not in unique_progs:
                    unique_progs[key] = set()
                unique_progs[key].add(p["operation"])

            print(f"\n    {W}{map_name}{R}{D}{mapset_str}{R}")
            for pgm_name, ops in sorted(unique_progs.items()):
                ops_str = ", ".join(sorted(ops))
                print(f"      {G}{pgm_name:<20s}{R} {D}{ops_str}{R}")

    # Summary
    shared_files = [
        f for f, p in file_programs.items()
        if len({pp["program"] for pp in p}) > 1
    ]
    if shared_files:
        print(f"\n  {H}Shared Files (data boundary risks){R}")
        print(f"  {D}These files are accessed by multiple programs — record layout changes affect all users.{R}")
        for f in sorted(shared_files):
            progs = {p["program"] for p in file_programs[f]}
            print(f"    {W}{f}{R}: {', '.join(sorted(progs))}")

    print()


def _cmd_dead(active):
    """Dead code detection — unreachable paragraphs, orphan programs, unused copybooks."""
    graph = _get_graph(active)
    if not graph:
        print(f"  \033[38;5;196mNo analysis graph found for {active}. Run analyze.py first.\033[0m")
        return

    result = graph.dead_code_analysis()
    s = result["summary"]

    W = "\033[1m"
    R = "\033[0m"
    D = "\033[38;5;240m"
    H = "\033[38;5;214m"
    RED = "\033[38;5;196m"

    print(f"\n  {H}Dead Code Analysis: {active}{R}")
    print(f"  {D}{'-' * 55}{R}")

    # Summary
    print(f"\n  {H}Summary{R}")
    print(f"    Unreachable paragraphs:  {W}{s['unreachable_count']}{R} / {s['total_paragraphs']}")
    print(f"    Orphan programs:         {W}{s['orphan_count']}{R} / {s['total_programs']}")
    print(f"    Unused copybooks:        {W}{s['unused_count']}{R} / {s['total_copybooks']}")

    if s['total_paragraphs'] > 0:
        dead_pct = s['unreachable_count'] / s['total_paragraphs'] * 100
        print(f"    Dead paragraph ratio:    {W}{dead_pct:.1f}%{R}")

    # Unreachable paragraphs grouped by program
    unreachable = result["unreachable_paragraphs"]
    if unreachable:
        print(f"\n  {H}Unreachable Paragraphs ({len(unreachable)}){R}")
        by_pgm: dict[str, list] = {}
        for p in unreachable:
            by_pgm.setdefault(p["program"], []).append(p)

        for pgm, paras in sorted(by_pgm.items(), key=lambda x: -len(x[1])):
            print(f"\n    {W}{pgm}{R} ({len(paras)} unreachable):")
            for p in paras[:10]:
                flags = []
                if p["has_calls"]:
                    flags.append("calls")
                if p["has_cics"]:
                    flags.append("CICS")
                flag_str = f" {D}[{', '.join(flags)}]{R}" if flags else ""
                print(f"      {RED}x{R} {p['paragraph']}{D} L{p['start_line']}-{p['end_line']}{R}{flag_str}")
            if len(paras) > 10:
                print(f"      {D}... +{len(paras) - 10} more{R}")

    # Orphan programs
    orphans = result["orphan_programs"]
    if orphans:
        print(f"\n  {H}Orphan Programs (no callers) ({len(orphans)}){R}")
        print(f"  {D}These may be entry points (JCL/CICS) or truly unused.{R}")
        for o in sorted(orphans, key=lambda x: -x["code_lines"]):
            pgm_type = "CICS" if o["has_cics"] else "Batch"
            callees = o["callees"]
            callee_str = f" calls: {', '.join(callees[:3])}" if callees else " (leaf)"
            print(f"    {W}{o['program']:<20s}{R} {o['code_lines']:>5d} LOC  {pgm_type:<5s}{D}{callee_str}{R}")

    # Unused copybooks
    unused = result["unused_copybooks"]
    if unused:
        print(f"\n  {H}Unused Copybooks ({len(unused)}){R}")
        for cb in unused:
            print(f"    {RED}x{R} {cb}")

    print()


def _get_data_flow_index(codebase):
    from graph_context import DataFlowIndex
    analysis_dir = str(Path(KNOWN_CODEBASES[codebase]["dir"]) / "_analysis")
    try:
        return DataFlowIndex(analysis_dir)
    except FileNotFoundError:
        return None


def _cmd_trace(arg, active):
    """Trace a data field through MOVE/COMPUTE/CALL USING assignments."""
    if not arg:
        print("  \033[38;5;196mUsage: /trace <field_name>\033[0m")
        print("  \033[38;5;240mExamples: /trace WS-RETURN-MSG, /trace ACCT-BALANCE\033[0m")
        return

    dfi = _get_data_flow_index(active)
    if not dfi:
        print(f"  \033[38;5;196mNo analysis data found for {active}. Run analyze.py first.\033[0m")
        return

    field = arg.upper()
    trace = dfi.trace_field(field, direction="both", max_depth=3)

    W = "\033[1m"
    R = "\033[0m"
    D = "\033[38;5;240m"
    H = "\033[38;5;214m"
    G = "\033[38;5;40m"
    B = "\033[38;5;39m"

    programs = trace["programs_touching"]
    if not programs and not trace["forward_trace"] and not trace["backward_trace"]:
        print(f"  \033[38;5;196mField '{field}' not found in any data flow.\033[0m")
        # Try fuzzy match
        all_fields = set()
        for pgm_flows in dfi._program_flows.values():
            for f in pgm_flows:
                all_fields.update(f["sources"])
                all_fields.update(f["targets"])
        similar = [f for f in all_fields if field[:4] in f or f[:4] in field]
        if similar:
            print(f"  {D}Similar fields: {', '.join(sorted(similar)[:8])}{R}")
        return

    print(f"\n  {H}Data Flow Trace: {field}{R}")
    print(f"  {D}{'-' * 55}{R}")
    print(f"\n  {D}Touched by {len(programs)} programs: {', '.join(programs)}{R}")

    # Field definitions
    defs = dfi.field_definition(field)
    if defs:
        print(f"\n  {H}Definitions:{R}")
        for d in defs[:5]:
            pic_str = f" PIC {d['picture']}" if d['picture'] else ""
            occ_str = f" OCCURS {d['occurs']}" if d.get('occurs') else ""
            print(f"    {B}{d['program']}{R}: {W}level-{d['level']:02d}{R} {d['name']}{pic_str}{occ_str}")

    # Backward trace (where does it come from?)
    backward = trace["backward_trace"]
    if backward:
        print(f"\n  {H}Sources (where does {field} come from?):{R}")
        seen = set()
        for entry in backward:
            key = (entry["field"], entry["program"], entry["paragraph"])
            if key in seen:
                continue
            seen.add(key)
            depth_marker = "  " * entry["depth"]
            print(
                f"    {depth_marker}{G}<-{R} {W}{entry['field']}{R}"
                f"  {D}in {entry['program']}::{entry['paragraph']}"
                f" L{entry['line']} [{entry['flow_type']}]{R}"
            )

    # Forward trace (where does it go?)
    forward = trace["forward_trace"]
    if forward:
        print(f"\n  {H}Targets (where does {field} flow to?):{R}")
        seen = set()
        for entry in forward:
            key = (entry["field"], entry["program"], entry["paragraph"])
            if key in seen:
                continue
            seen.add(key)
            depth_marker = "  " * entry["depth"]
            print(
                f"    {depth_marker}{B}->{R} {W}{entry['field']}{R}"
                f"  {D}in {entry['program']}::{entry['paragraph']}"
                f" L{entry['line']} [{entry['flow_type']}]{R}"
            )

    # Cross-program bindings
    bindings = dfi.cross_program_bindings(field)
    if bindings:
        print(f"\n  {H}Cross-Program CALL USING Bindings:{R}")
        for b in bindings[:10]:
            print(f"    {W}{b['caller']}{R} -> {W}{b['callee']}{R}  {D}(passes: {', '.join(b['all_args'][:5])}){R}")

    print()


def _cmd_spec(arg, active):
    """Generate a reimplementation specification for a program."""
    if not arg:
        print("  \033[38;5;196mUsage: /spec <program_name>\033[0m")
        return

    graph = _get_graph(active)
    target = arg.upper()

    if graph and target not in graph.program_names():
        print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
        if graph:
            _suggest_similar(target, graph)
        return

    print(f"\n  \033[38;5;214mGenerating reimplementation spec for {target}...\033[0m\n")

    # Gather structural context from graph
    structural_parts = []
    if graph:
        enrichment = graph.enrichment_for(target)
        readiness = graph.readiness_score(target)
        node_id = f"PGM:{target}"
        node = graph.nodes.get(node_id, {})
        meta = node.get("metadata", {})

        structural_parts.append(f"Program: {target}")
        structural_parts.append(f"Code lines: {meta.get('code_lines', 'unknown')}")
        structural_parts.append(f"Paragraphs: {meta.get('paragraph_count', 'unknown')}")
        structural_parts.append(f"Readiness score: {readiness['composite']}/100")

        if enrichment["callers"]:
            structural_parts.append(f"Called by: {', '.join(enrichment['callers'])}")
        if enrichment["callees"]:
            structural_parts.append(f"Calls: {', '.join(enrichment['callees'])}")
        if enrichment["copybooks"]:
            structural_parts.append(f"Copybooks: {', '.join(enrichment['copybooks'])}")
        if enrichment["programs_sharing_copybooks"]:
            structural_parts.append(f"Shares copybooks with: {', '.join(enrichment['programs_sharing_copybooks'][:5])}")

        # File I/O
        file_edges = [
            e for e in graph.edges
            if e["source"] == node_id and e["type"] in ("READS_FILE", "CICS_IO")
        ]
        if file_edges:
            files = set()
            for e in file_edges:
                tgt_node = graph.nodes.get(e["target"], {})
                files.add(f"{tgt_node.get('name', e['target'])} ({e['type']})")
            structural_parts.append(f"File/dataset I/O: {', '.join(sorted(files))}")

        has_cics = any(e["type"] == "CICS_IO" for e in graph.edges if e["source"] == node_id)
        structural_parts.append(f"Type: {'CICS Online' if has_cics else 'Batch'}")

    # Data flow summary
    dfi = _get_data_flow_index(active)
    if dfi:
        flow_summary = dfi.program_flow_summary(target)
        if flow_summary["total_flows"] > 0:
            structural_parts.append(f"Data flows: {flow_summary['total_flows']} assignments")
            structural_parts.append(f"Fields written: {len(flow_summary['fields_written'])}")
            structural_parts.append(f"Fields read: {len(flow_summary['fields_read'])}")

    structural_context = "\n".join(structural_parts)

    # RAG retrieval for code context
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
        "structural_context": structural_context,
        "code_context": code_context,
        "program": target,
    }):
        answer_parts.append(token)
        sys.stdout.write(token)
        sys.stdout.flush()
    t5 = time.perf_counter()

    timing["llm_ms"] = (t5 - t4) * 1000
    timing["total_ms"] = (time.perf_counter() - start) * 1000
    _print_timing(timing)

    from rag_models import QueryResult
    result = QueryResult(
        query=question,
        answer="".join(answer_parts),
        sources=_build_sources(reranked),
        latency_ms=timing["total_ms"],
    )
    _print_sources(result)
    print()


def _cmd_rules(arg, active):
    """Extract structured business rules from a program."""
    if not arg:
        print("  \033[38;5;196mUsage: /rules <program_name>\033[0m")
        return

    graph = _get_graph(active)
    target = arg.upper()

    if graph and target not in graph.program_names():
        print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
        if graph:
            _suggest_similar(target, graph)
        return

    print(f"\n  \033[38;5;214mExtracting business rules from {target}...\033[0m\n")

    from synthesis.chain import _retrieve_and_prepare, _get_llm, _build_sources, _print_timing
    from synthesis.prompts import RULES_PROMPT_TEMPLATE
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
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
    t5 = time.perf_counter()

    timing["llm_ms"] = (t5 - t4) * 1000
    timing["total_ms"] = (time.perf_counter() - start) * 1000
    _print_timing(timing)

    # Print sources
    from rag_models import QueryResult
    result = QueryResult(
        query=question,
        answer="".join(answer_parts),
        sources=_build_sources(reranked),
        latency_ms=timing["total_ms"],
    )
    _print_sources(result)
    print()


def _cmd_complexity(arg, active):
    """Cyclomatic complexity analysis for the codebase."""
    info = KNOWN_CODEBASES.get(active, {})
    codebase_dir = info.get("dir", "")
    if not codebase_dir:
        print(f"  \033[38;5;196mCodebase directory not found for {active}.\033[0m")
        return

    from complexity import compute_all, compute_complexity, complexity_grade

    W = "\033[1m"
    R = "\033[0m"
    D = "\033[38;5;240m"
    H = "\033[38;5;214m"
    B = "\033[38;5;39m"
    G = "\033[38;5;40m"
    Y = "\033[38;5;220m"
    RED = "\033[38;5;196m"

    if arg:
        # Single program detail
        from pathlib import Path
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


def _cmd_estimate(active):
    """Migration effort estimation for the entire estate."""
    gi = _get_graph(active)
    if not gi:
        print(f"  \033[38;5;196mNo analysis data found for {active}. Run analyze.py first.\033[0m")
        return

    from effort_estimator import estimate_estate

    W = "\033[1m"
    R = "\033[0m"
    D = "\033[38;5;240m"
    H = "\033[38;5;214m"
    B = "\033[38;5;39m"
    G = "\033[38;5;40m"
    Y = "\033[38;5;220m"
    RED = "\033[38;5;196m"

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

    # Wave breakdown
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

    # Quick wins
    if result["quick_wins"]:
        print(f"  {G}Recommended Starting Points (Quick Wins):{R}")
        for pgm in result["quick_wins"][:5]:
            est = next((e for e in result["estimates"] if e.program == pgm), None)
            if est:
                print(f"    {B}{pgm}{R}: {est.effort_days:.1f} days, {est.code_lines} LOC [{est.category}]")
        print()

    # Per-program table
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


def _cmd_xref(arg, active):
    """Cross-reference a field across all programs."""
    if not arg:
        print("  \033[38;5;196mUsage: /xref <field_name>\033[0m")
        print("  \033[38;5;240mExamples: /xref ACCT-NUM, /xref WS-RETURN-MSG\033[0m")
        print("  \033[38;5;240mSupports partial matching: /xref ACCT\033[0m")
        return

    dfi = _get_data_flow_index(active)
    if not dfi:
        print(f"  \033[38;5;196mNo analysis data found for {active}. Run analyze.py first.\033[0m")
        return

    W = "\033[1m"
    R = "\033[0m"
    D = "\033[38;5;240m"
    H = "\033[38;5;214m"
    B = "\033[38;5;39m"
    G = "\033[38;5;40m"
    RED = "\033[38;5;196m"
    Y = "\033[38;5;220m"

    field = arg.upper()

    # Check if exact match or search
    matches = dfi.search_fields(field)
    if not matches:
        print(f"  {RED}No fields matching '{field}' found.{R}")
        return

    if len(matches) == 1 or field in matches:
        target_field = field if field in matches else matches[0]
    elif len(matches) <= 15:
        print(f"\n  {H}Fields matching '{field}':{R}\n")
        for i, m in enumerate(matches, 1):
            print(f"    {B}{i:2}.{R} {m}")
        print(f"\n  {D}Showing cross-reference for: {matches[0]}{R}\n")
        target_field = matches[0]
    else:
        print(f"\n  {H}{len(matches)} fields match '{field}'{R} — showing first 15:\n")
        for i, m in enumerate(matches[:15], 1):
            print(f"    {B}{i:2}.{R} {m}")
        print(f"    {D}... and {len(matches) - 15} more{R}")
        print(f"\n  {D}Narrow your search for a specific cross-reference.{R}\n")
        return

    xref = dfi.cross_reference(target_field)

    print(f"\n  {H}{'═' * 60}{R}")
    print(f"  {H}Cross-Reference: {W}{xref['field']}{R}")
    print(f"  {H}{'═' * 60}{R}\n")

    print(f"  {D}Programs: {R}{xref['total_programs']}    "
          f"{D}Writes: {R}{xref['total_writes']}    "
          f"{D}Reads: {R}{xref['total_reads']}    "
          f"{D}CALL refs: {R}{xref['total_call_refs']}\n")

    for pgm, info in xref["by_program"].items():
        total_refs = info["write_count"] + info["read_count"] + len(info["call_passing"])
        print(f"  {B}{pgm}{R}  {D}({total_refs} references){R}")

        for w in info["writes"][:5]:
            sources = ", ".join(w["sources"][:3]) or "literal"
            print(f"    {RED}W{R}  {w['flow_type']} {sources} -> {G}{xref['field']}{R}"
                  f"  {D}[{w['paragraph'] or 'top-level'}:{w['line']}]{R}")

        for r in info["reads"][:5]:
            targets = ", ".join(r["targets"][:3]) or "?"
            print(f"    {G}R{R}  {r['flow_type']} {G}{xref['field']}{R} -> {targets}"
                  f"  {D}[{r['paragraph'] or 'top-level'}:{r['line']}]{R}")

        for c in info["call_passing"]:
            print(f"    {Y}C{R}  CALL {c['callee']} USING (arg #{c['position']})"
                  f"  {D}[passed as parameter]{R}")

        overflow = total_refs - min(info["write_count"], 5) - min(info["read_count"], 5) - len(info["call_passing"])
        if overflow > 0:
            print(f"    {D}... +{overflow} more references{R}")
        print()

    # Trace summary
    trace = dfi.trace_field(target_field, direction="both", max_depth=2)
    if trace["forward_trace"]:
        print(f"  {H}Forward trace{R} (where does {target_field} flow to?):")
        for step in trace["forward_trace"][:8]:
            targets = ", ".join(step.get("targets", [])[:3])
            print(f"    -> {targets}  {D}[{step.get('program', '')}:{step.get('paragraph', '')}]{R}")
        print()

    if trace["backward_trace"]:
        print(f"  {H}Backward trace{R} (where does {target_field} come from?):")
        for step in trace["backward_trace"][:8]:
            sources = ", ".join(step.get("sources", [])[:3])
            print(f"    <- {sources}  {D}[{step.get('program', '')}:{step.get('paragraph', '')}]{R}")
        print()


def _cmd_test_gen(arg, active):
    """Generate pytest test stubs from COBOL structural analysis."""
    info = KNOWN_CODEBASES.get(active, {})
    codebase_dir = info.get("dir", "")
    if not codebase_dir:
        print(f"  \033[38;5;196mCodebase directory not found for {active}.\033[0m")
        return

    from test_generator import generate_all_test_suites, generate_test_suite
    from spec_generator import generate_program_spec, _load_program_data
    from graph_context import GraphIndex

    analysis_dir = os.path.join(codebase_dir, "_analysis")

    if arg:
        target = arg.upper()
        graph = _get_graph(active)
        if not graph:
            print(f"  \033[38;5;196mNo analysis graph found for {active}.\033[0m")
            return
        if target not in graph.program_names():
            print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
            _suggest_similar(target, graph)
            return

        print(f"  \033[38;5;214mGenerating test suite for {target}...\033[0m\n")
        program_data = _load_program_data(Path(analysis_dir))
        spec = generate_program_spec(target, graph, program_data, codebase_dir)
        if spec:
            code = generate_test_suite(spec)
            tests_dir = os.path.join(analysis_dir, "generated_tests")
            os.makedirs(tests_dir, exist_ok=True)
            from skeleton_generator import _cobol_name_to_python
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


def _cmd_skeleton(arg, active):
    """Generate Python skeletons from COBOL structural analysis."""
    info = KNOWN_CODEBASES.get(active, {})
    codebase_dir = info.get("dir", "")
    if not codebase_dir:
        print(f"  \033[38;5;196mCodebase directory not found for {active}.\033[0m")
        return

    from skeleton_generator import generate_all_skeletons, generate_skeleton
    from spec_generator import generate_program_spec, _load_program_data
    from graph_context import GraphIndex

    analysis_dir = os.path.join(codebase_dir, "_analysis")

    if arg:
        target = arg.upper()
        graph = _get_graph(active)
        if not graph:
            print(f"  \033[38;5;196mNo analysis graph found for {active}.\033[0m")
            return
        if target not in graph.program_names():
            print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
            _suggest_similar(target, graph)
            return

        print(f"  \033[38;5;214mGenerating Python skeleton for {target}...\033[0m\n")
        program_data = _load_program_data(Path(analysis_dir))
        spec = generate_program_spec(target, graph, program_data, codebase_dir)
        if spec:
            code = generate_skeleton(spec)
            skeletons_dir = os.path.join(analysis_dir, "skeletons")
            os.makedirs(skeletons_dir, exist_ok=True)
            from skeleton_generator import _cobol_name_to_python
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


def _cmd_spec_gen(arg, active):
    """Generate behavioral specs for all or one program (static analysis only, no API keys)."""
    info = KNOWN_CODEBASES.get(active, {})
    codebase_dir = info.get("dir", "")
    if not codebase_dir:
        print(f"  \033[38;5;196mCodebase directory not found for {active}.\033[0m")
        return

    from spec_generator import generate_all_specs, generate_program_spec, render_spec_markdown, _load_program_data
    from graph_context import GraphIndex

    analysis_dir = os.path.join(codebase_dir, "_analysis")

    if arg:
        target = arg.upper()
        graph = _get_graph(active)
        if not graph:
            print(f"  \033[38;5;196mNo analysis graph found for {active}.\033[0m")
            return
        if target not in graph.program_names():
            print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
            _suggest_similar(target, graph)
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


def _cmd_export(active):
    """Export analysis to CSV and JSON."""
    info = KNOWN_CODEBASES.get(active, {})
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


def _cmd_report(active):
    """Generate a comprehensive HTML analysis report."""
    info = KNOWN_CODEBASES.get(active, {})
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


def _cmd_eval(arg, active):
    """Run the evaluation suite."""
    from evals.runner import run_all, print_report, save_results

    if arg == "all":
        scores = run_all()
    else:
        scores = run_all(codebase_filter=active)

    print_report(scores)
    save_results(scores)


def _cmd_readiness(arg, active):
    """Per-module reimplementation readiness scoring."""
    graph = _get_graph(active)
    if not graph:
        print(f"  \033[38;5;196mNo analysis graph found for {active}. Run analyze.py first.\033[0m")
        return

    if arg:
        target = arg.upper()
        if target not in graph.program_names():
            print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
            _suggest_similar(target, graph)
            return

        score = graph.readiness_score(target)
        d = score["details"]

        print(f"\n  \033[38;5;214mReadiness Assessment: {target}\033[0m")
        print(f"  \033[38;5;240m{'—' * 55}\033[0m\n")

        composite = score["composite"]
        if composite >= 70:
            grade = "\033[38;5;40mGOOD CANDIDATE\033[0m"
        elif composite >= 45:
            grade = "\033[38;5;214mMODERATE\033[0m"
        else:
            grade = "\033[38;5;196mCOMPLEX\033[0m"

        print(f"  Overall Readiness:  \033[1m{composite:.0f}/100\033[0m  {grade}\n")

        def _bar(val, label, width=30):
            filled = int(val / 100 * width)
            if val >= 70:
                color = "\033[38;5;40m"
            elif val >= 45:
                color = "\033[38;5;214m"
            else:
                color = "\033[38;5;196m"
            bar = color + "█" * filled + "\033[38;5;240m" + "░" * (width - filled) + "\033[0m"
            print(f"  {label:<22s} {val:>5.0f}  {bar}")

        _bar(score["isolation"], "Isolation")
        _bar(score["simplicity"], "Simplicity")
        _bar(score["dependency_clarity"], "Dependency Clarity")
        _bar(score["testability"], "Testability")

        print(f"\n  \033[38;5;245mDetails:\033[0m")
        print(f"    Code lines:          {d['code_lines']}")
        print(f"    Paragraphs:          {d['paragraph_count']}")
        print(f"    Callers (inbound):   {d['callers']}")
        print(f"    Callees (outbound):  {d['callees']}")
        print(f"    Copybooks:           {d['copybooks']}")
        print(f"    Shared with:         {d['shared_peers']} other programs")
        print(f"    CICS online:         {'Yes' if d['has_cics'] else 'No'}")

        if d["unresolved_copybooks"]:
            print(f"    \033[38;5;196mUnresolved copybooks: {', '.join(d['unresolved_copybooks'])}\033[0m")
        if d["unresolved_calls"]:
            print(f"    \033[38;5;196mUnresolved calls: {', '.join(d['unresolved_calls'])}\033[0m")

        print()
        return

    # No argument — show ranked table
    ranking = graph.readiness_ranking()

    print(f"\n  \033[38;5;214mReimplementation Readiness — {active}\033[0m")
    print(f"  \033[38;5;240mPrograms ranked by readiness score (higher = better candidate)\033[0m")
    print(f"  \033[38;5;240m{'—' * 75}\033[0m\n")
    print(f"  {'Program':<20s} {'Score':>5s}  {'Iso':>4s} {'Sim':>4s} {'Dep':>4s} {'Test':>4s}  {'LOC':>5s}  {'Type':<6s}  Grade")
    print(f"  {'—'*20} {'—'*5}  {'—'*4} {'—'*4} {'—'*4} {'—'*4}  {'—'*5}  {'—'*6}  {'—'*14}")

    for score in ranking:
        d = score["details"]
        composite = score["composite"]
        pgm_type = "CICS" if d["has_cics"] else "Batch"

        if composite >= 70:
            grade = "\033[38;5;40mGOOD\033[0m"
        elif composite >= 45:
            grade = "\033[38;5;214mMODERATE\033[0m"
        else:
            grade = "\033[38;5;196mCOMPLEX\033[0m"

        print(
            f"  \033[1m{score['program']:<20s}\033[0m"
            f" {composite:>5.0f}"
            f"  {score['isolation']:>4.0f}"
            f" {score['simplicity']:>4.0f}"
            f" {score['dependency_clarity']:>4.0f}"
            f" {score['testability']:>4.0f}"
            f"  {d['code_lines']:>5d}"
            f"  {pgm_type:<6s}"
            f"  {grade}"
        )

    good = sum(1 for s in ranking if s["composite"] >= 70)
    moderate = sum(1 for s in ranking if 45 <= s["composite"] < 70)
    complex_ = sum(1 for s in ranking if s["composite"] < 45)
    print(f"\n  \033[38;5;245m{good} good candidates, {moderate} moderate, {complex_} complex — out of {len(ranking)} programs\033[0m\n")


def _cmd_summary(active):
    """Estate-level codebase overview."""
    graph = _get_graph(active)
    if not graph:
        print(f"  \033[38;5;196mNo analysis graph found for {active}. Run analyze.py first.\033[0m")
        return

    s = graph.summary()
    W = "\033[1m"
    R = "\033[0m"
    D = "\033[38;5;240m"
    H = "\033[38;5;214m"
    G = "\033[38;5;40m"
    B = "\033[38;5;39m"

    print(f"\n  {H}{'═' * 60}{R}")
    print(f"  {H}  CODEBASE SUMMARY: {active.upper()}{R}")
    print(f"  {H}{'═' * 60}{R}")

    # Size
    print(f"\n  {H}Size{R}")
    print(f"    Programs:       {W}{s['total_programs']}{R}  ({len(s['cics_programs'])} CICS online, {len(s['batch_programs'])} batch)")
    print(f"    Copybooks:      {W}{s['total_copybooks']}{R}")
    print(f"    Total LOC:      {W}{s['total_loc']:,}{R}  ({s['total_code_lines']:,} code, {s['total_comment_lines']:,} comments)")
    print(f"    Paragraphs:     {W}{s['total_paragraphs']}{R}")

    # Graph topology
    print(f"\n  {H}Graph Topology{R}")
    print(f"    Total edges:    {W}{s['total_edges']}{R}")
    for etype, count in sorted(s["edge_types"].items(), key=lambda x: -x[1]):
        print(f"      {etype:<15s} {count}")

    # Components
    components = s["components"]
    print(f"\n  {H}Connected Components{R}")
    print(f"    {W}{len(components)}{R} components")
    for i, comp in enumerate(components[:5]):
        size = len(comp)
        members = sorted(comp)[:6]
        more = f" +{size - 6} more" if size > 6 else ""
        print(f"    {D}[{i+1}]{R} {W}{size}{R} programs: {', '.join(members)}{D}{more}{R}")

    # Program classification
    if s["cics_programs"]:
        print(f"\n  {H}CICS Online Programs ({len(s['cics_programs'])}){R}")
        for pgm in sorted(s["cics_programs"]):
            enrichment = graph.enrichment_for(pgm)
            score = enrichment["hub_score"]
            print(f"    {B}{pgm}{R}  {D}hub={score:.0f}{R}")

    if s["batch_programs"]:
        print(f"\n  {H}Batch Programs ({len(s['batch_programs'])}){R}")
        for pgm in sorted(s["batch_programs"]):
            enrichment = graph.enrichment_for(pgm)
            score = enrichment["hub_score"]
            print(f"    {G}{pgm}{R}  {D}hub={score:.0f}{R}")

    # Shared copybooks (coupling indicators)
    shared = s["shared_copybooks"]
    if shared:
        print(f"\n  {H}Most Shared Copybooks (coupling indicators){R}")
        for cb, user_count, users in shared[:10]:
            user_list = ", ".join(users[:4])
            more = f" +{user_count - 4}" if user_count > 4 else ""
            bar = "\033[38;5;214m" + "█" * min(user_count, 20) + R
            print(f"    {W}{cb:<16s}{R} {user_count:>2d} programs  {bar}  {D}{user_list}{more}{R}")

    # Hotspots
    hubs = s["hub_programs"]
    if hubs:
        print(f"\n  {H}Top Hotspots (change risk){R}")
        for name, score in hubs[:5]:
            callers = len(graph.callers(name))
            callees = len(graph.callees(name))
            cbs = len(graph.copybooks_of(name))
            print(f"    {W}{name:<20s}{R} score={score:.0f}  in={callers} out={callees} copy={cbs}")

    # Leaf programs
    leaves = s["leaf_programs"]
    if leaves:
        standalone = [p for p in leaves if not graph.callers(p)]
        called_leaves = [p for p in leaves if graph.callers(p)]
        print(f"\n  {H}Leaf Programs ({len(leaves)} total){R}")
        if standalone:
            print(f"    {D}Standalone (no callers, no callees):{R}")
            for p in standalone[:8]:
                print(f"      {p}")
        if called_leaves:
            print(f"    {D}Called but don't call others:{R}")
            for p in called_leaves[:8]:
                callers = graph.callers(p)
                print(f"      {p}  {D}← {', '.join(callers[:3])}{R}")

    # Unresolved references
    unresolved_cbs = s["unresolved_copybooks"]
    unresolved_calls = s["unresolved_calls"]
    if unresolved_cbs or unresolved_calls:
        print(f"\n  {H}Unresolved External References{R}")
        if unresolved_cbs:
            print(f"    Copybooks ({len(unresolved_cbs)}): {D}{', '.join(unresolved_cbs[:8])}{R}")
        if unresolved_calls:
            print(f"    Call targets ({len(unresolved_calls)}): {D}{', '.join(unresolved_calls[:8])}{R}")

    # Parse coverage
    if s["total_programs"] > 0 and s["total_loc"] > 0:
        comment_ratio = s["total_comment_lines"] / s["total_loc"] * 100 if s["total_loc"] else 0
        print(f"\n  {H}Parse Coverage{R}")
        print(f"    Programs parsed: {W}{s['total_programs']}{R}")
        print(f"    Comment ratio:   {W}{comment_ratio:.1f}%{R}")
        parse_coverage = (s['total_programs'] / (s['total_programs'] + len(unresolved_calls))) * 100 if unresolved_calls else 100
        print(f"    Resolved calls:  {W}{parse_coverage:.0f}%{R} ({len(unresolved_calls)} unresolved)")

    print(f"\n  {H}{'═' * 60}{R}\n")


def _suggest_similar(target, graph):
    """Suggest similar names from the graph when a lookup fails."""
    all_names = graph.program_names() + graph.copybook_names()
    similar = [n for n in all_names if target[:3] in n or n[:3] in target]
    if similar:
        print(f"  \033[38;5;245mDid you mean: {', '.join(similar[:5])}\033[0m")


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
            continue

        if user_input == "/suggest":
            _print_suggestions(active)
            continue

        if user_input.startswith("/complexity"):
            arg = user_input[len("/complexity"):].strip()
            _cmd_complexity(arg, active)
            continue

        if user_input == "/estimate":
            _cmd_estimate(active)
            continue

        if user_input == "/export":
            _cmd_export(active)
            continue

        if user_input == "/report":
            _cmd_report(active)
            continue

        if user_input.startswith("/eval"):
            arg = user_input[len("/eval"):].strip()
            _cmd_eval(arg, active)
            continue

        if user_input == "/summary":
            _cmd_summary(active)
            continue

        if user_input.startswith("/screens"):
            arg = user_input[len("/screens"):].strip()
            _cmd_screens(arg, active)
            continue

        if user_input.startswith("/jobs"):
            arg = user_input[len("/jobs"):].strip()
            _cmd_jobs(arg, active)
            continue

        if user_input.startswith("/dict"):
            arg = user_input[len("/dict"):].strip()
            _cmd_dict(arg, active)
            continue

        if user_input == "/dead":
            _cmd_dead(active)
            continue

        if user_input == "/files":
            _cmd_files(active)
            continue

        if user_input.startswith("/trace"):
            arg = user_input[len("/trace"):].strip()
            _cmd_trace(arg, active)
            continue

        if user_input.startswith("/xref"):
            arg = user_input[len("/xref"):].strip()
            _cmd_xref(arg, active)
            continue

        if user_input.startswith("/test-gen"):
            arg = user_input[len("/test-gen"):].strip()
            _cmd_test_gen(arg, active)
            continue

        if user_input.startswith("/skeleton"):
            arg = user_input[len("/skeleton"):].strip()
            _cmd_skeleton(arg, active)
            continue

        if user_input.startswith("/spec-gen"):
            arg = user_input[len("/spec-gen"):].strip()
            _cmd_spec_gen(arg, active)
            continue

        if user_input.startswith("/spec"):
            arg = user_input[len("/spec"):].strip()
            _cmd_spec(arg, active)
            continue

        if user_input.startswith("/rules"):
            arg = user_input[len("/rules"):].strip()
            _cmd_rules(arg, active)
            continue

        if user_input.startswith("/readiness"):
            arg = user_input[len("/readiness"):].strip()
            _cmd_readiness(arg, active)
            continue

        if user_input.startswith("/impact"):
            arg = user_input[len("/impact"):].strip()
            _cmd_impact(arg, active)
            continue

        if user_input.startswith("/deps"):
            arg = user_input[len("/deps"):].strip()
            _cmd_deps(arg, active)
            continue

        if user_input == "/hotspots":
            _cmd_hotspots(active)
            continue

        if user_input == "/isolated":
            _cmd_isolated(active)
            continue

        if user_input == "/switch":
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
            continue

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
