"""
Graph-based CLI commands: impact, deps, hotspots, isolated, summary,
readiness, dead code detection, file contract map.

All functions receive (active, KNOWN_CODEBASES) and print directly.
"""

import sys
from pathlib import Path


# ── Lazy-loaded graph cache ───────────────────────────────────────────────────

_graphs: dict[str, object] = {}


def get_graph(codebase, known_codebases):
    if codebase not in _graphs:
        from synthesis.chain import get_graph_for_codebase
        _graphs[codebase] = get_graph_for_codebase(codebase)
    return _graphs[codebase]


def suggest_similar(target, graph):
    all_names = graph.program_names() + graph.copybook_names()
    similar = [n for n in all_names if target[:3] in n or n[:3] in target]
    if similar:
        print(f"  \033[38;5;245mDid you mean: {', '.join(similar[:5])}\033[0m")


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


# ── /impact ──────────────────────────────────────────────────────────────────

def cmd_impact(arg, active, known_codebases):
    if not arg:
        print("  \033[38;5;196mUsage: /impact <program_name|copybook_name>\033[0m")
        return

    graph = get_graph(active, known_codebases)
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
        suggest_similar(target, graph)
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
            shared = [
                cb for cb in enrichment["copybooks"]
                if target in [u.upper() for u in graph.copybook_users(cb)]
                or cb.upper() == target
            ]
            if shared:
                detail_parts.append(f"shared copybooks: {', '.join(shared[:3])}")

        detail = f"  \033[38;5;240m{' | '.join(detail_parts)}\033[0m" if detail_parts else ""
        bar = "█" * min(distance, 5)
        print(f"    {risk}  dist={distance}  {bar}  \033[1m{name}\033[0m")
        if detail:
            print(f"    {detail}")

    print(f"\n  \033[38;5;245mGenerating explanation...\033[0m\n")
    affected_names = ", ".join(n for n, _ in impact[:5])
    question = (
        f"What is the relationship between {target} and these programs: {affected_names}? "
        f"How would a change to {target} affect them?"
    )

    from synthesis.chain import query_stream
    from cli import _print_sources  # shared helper
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


# ── /deps ─────────────────────────────────────────────────────────────────────

def cmd_deps(arg, active, known_codebases):
    if not arg:
        print("  \033[38;5;196mUsage: /deps <program_name>\033[0m")
        return

    graph = get_graph(active, known_codebases)
    if not graph:
        print(f"  \033[38;5;196mNo analysis graph found for {active}. Run analyze.py first.\033[0m")
        return

    target = arg.upper()
    if target not in graph.program_names():
        print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
        suggest_similar(target, graph)
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


# ── /hotspots ─────────────────────────────────────────────────────────────────

def cmd_hotspots(active, known_codebases):
    graph = get_graph(active, known_codebases)
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


# ── /isolated ─────────────────────────────────────────────────────────────────

def cmd_isolated(active, known_codebases):
    graph = get_graph(active, known_codebases)
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
        print(
            f"  \033[1m{name:<20s}\033[0m {len(callers):>8d}  {len(copybooks):>10d}"
            f"  {score:>10.1f}  \033[38;5;240m{note_str}\033[0m"
        )

    print(f"\n  \033[38;5;245m{len(leaves)} leaf programs out of {len(graph.program_names())} total\033[0m")
    print(f"  \033[38;5;245m{len(components)} connected components in call graph\033[0m\n")


# ── /dead ─────────────────────────────────────────────────────────────────────

def cmd_dead(active, known_codebases):
    graph = get_graph(active, known_codebases)
    if not graph:
        print(f"  \033[38;5;196mNo analysis graph found for {active}. Run analyze.py first.\033[0m")
        return

    result = graph.dead_code_analysis()
    s = result["summary"]

    W, R, D, H = "\033[1m", "\033[0m", "\033[38;5;240m", "\033[38;5;214m"
    RED = "\033[38;5;196m"

    print(f"\n  {H}Dead Code Analysis: {active}{R}")
    print(f"  {D}{'-' * 55}{R}")
    print(f"\n  {H}Summary{R}")
    print(f"    Unreachable paragraphs:  {W}{s['unreachable_count']}{R} / {s['total_paragraphs']}")
    print(f"    Orphan programs:         {W}{s['orphan_count']}{R} / {s['total_programs']}")
    print(f"    Unused copybooks:        {W}{s['unused_count']}{R} / {s['total_copybooks']}")
    if s['total_paragraphs'] > 0:
        dead_pct = s['unreachable_count'] / s['total_paragraphs'] * 100
        print(f"    Dead paragraph ratio:    {W}{dead_pct:.1f}%{R}")

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

    orphans = result["orphan_programs"]
    if orphans:
        print(f"\n  {H}Orphan Programs (no callers) ({len(orphans)}){R}")
        print(f"  {D}These may be entry points (JCL/CICS) or truly unused.{R}")
        for o in sorted(orphans, key=lambda x: -x["code_lines"]):
            pgm_type = "CICS" if o["has_cics"] else "Batch"
            callees = o["callees"]
            callee_str = f" calls: {', '.join(callees[:3])}" if callees else " (leaf)"
            print(f"    {W}{o['program']:<20s}{R} {o['code_lines']:>5d} LOC  {pgm_type:<5s}{D}{callee_str}{R}")

    unused = result["unused_copybooks"]
    if unused:
        print(f"\n  {H}Unused Copybooks ({len(unused)}){R}")
        for cb in unused:
            print(f"    {RED}x{R} {cb}")
    print()


# ── /files ────────────────────────────────────────────────────────────────────

def cmd_files(active, known_codebases):
    graph = get_graph(active, known_codebases)
    if not graph:
        print(f"  \033[38;5;196mNo analysis graph found for {active}. Run analyze.py first.\033[0m")
        return

    W, R, D, H, B, G = "\033[1m", "\033[0m", "\033[38;5;240m", "\033[38;5;214m", "\033[38;5;39m", "\033[38;5;40m"

    file_nodes = {nid: node for nid, node in graph.nodes.items() if node["type"] == "FILE"}
    map_nodes = {nid: node for nid, node in graph.nodes.items() if node["type"] == "MAP"}

    file_programs: dict[str, list] = {}
    for edge in graph.edges:
        if edge["type"] in ("READS_FILE", "CICS_IO") and edge["target"].startswith("FILE:"):
            file_name = graph.nodes.get(edge["target"], {}).get("name", edge["target"])
            src_name = graph.nodes.get(edge["source"], {}).get("name", "")
            if not src_name or "::PARA:" in edge["source"]:
                continue
            evidence = edge.get("evidence", [{}])
            op = evidence[0].get("operation", "FILE_IO") if evidence else "FILE_IO"
            file_programs.setdefault(file_name, []).append({"program": src_name, "operation": op, "edge_type": edge["type"]})

    map_programs: dict[str, list] = {}
    for edge in graph.edges:
        if edge["type"] == "CICS_IO" and edge["target"].startswith("MAP:"):
            map_name = graph.nodes.get(edge["target"], {}).get("name", edge["target"])
            src_name = graph.nodes.get(edge["source"], {}).get("name", "")
            if not src_name or "::PARA:" in edge["source"]:
                continue
            evidence = edge.get("evidence", [{}])
            op = evidence[0].get("operation", "SEND/RECEIVE") if evidence else "SEND/RECEIVE"
            map_programs.setdefault(map_name, []).append({"program": src_name, "operation": op})

    print(f"\n  {H}File/Dataset Contract Map: {active}{R}")
    print(f"  {D}{'-' * 60}{R}")

    if file_programs:
        print(f"\n  {H}Files & Datasets ({len(file_programs)}){R}")
        for file_name in sorted(file_programs.keys()):
            progs = file_programs[file_name]
            node = file_nodes.get(f"FILE:{file_name.upper()}", {})
            org = node.get("metadata", {}).get("organization", "")
            org_str = f" [{org}]" if org else ""
            unique_progs: dict[str, set] = {}
            for p in progs:
                unique_progs.setdefault(p["program"], set()).add(p["operation"])
            shared = len(unique_progs) > 1
            sharing_marker = f" {H}** SHARED **{R}" if shared else ""
            print(f"\n    {W}{file_name}{R}{D}{org_str}{R}{sharing_marker}")
            for pgm_name, ops in sorted(unique_progs.items()):
                print(f"      {B}{pgm_name:<20s}{R} {D}{', '.join(sorted(ops))}{R}")

    if map_programs:
        print(f"\n  {H}CICS Maps ({len(map_programs)}){R}")
        for map_name in sorted(map_programs.keys()):
            progs = map_programs[map_name]
            node = map_nodes.get(f"MAP:{map_name.upper()}", {})
            mapset = node.get("metadata", {}).get("mapset", "")
            mapset_str = f" (mapset: {mapset})" if mapset else ""
            unique_progs: dict[str, set] = {}
            for p in progs:
                unique_progs.setdefault(p["program"], set()).add(p["operation"])
            print(f"\n    {W}{map_name}{R}{D}{mapset_str}{R}")
            for pgm_name, ops in sorted(unique_progs.items()):
                print(f"      {G}{pgm_name:<20s}{R} {D}{', '.join(sorted(ops))}{R}")

    shared_files = [f for f, p in file_programs.items() if len({pp["program"] for pp in p}) > 1]
    if shared_files:
        print(f"\n  {H}Shared Files (data boundary risks){R}")
        print(f"  {D}Record layout changes affect all users.{R}")
        for f in sorted(shared_files):
            progs = {p["program"] for p in file_programs[f]}
            print(f"    {W}{f}{R}: {', '.join(sorted(progs))}")
    print()


# ── /readiness ────────────────────────────────────────────────────────────────

def cmd_readiness(arg, active, known_codebases):
    graph = get_graph(active, known_codebases)
    if not graph:
        print(f"  \033[38;5;196mNo analysis graph found for {active}. Run analyze.py first.\033[0m")
        return

    if arg:
        target = arg.upper()
        if target not in graph.program_names():
            print(f"  \033[38;5;196mProgram '{target}' not found.\033[0m")
            suggest_similar(target, graph)
            return

        score = graph.readiness_score(target)
        d = score["details"]

        print(f"\n  \033[38;5;214mReadiness Assessment: {target}\033[0m")
        print(f"  \033[38;5;240m{'—' * 55}\033[0m\n")

        composite = score["composite"]
        grade = (
            "\033[38;5;40mGOOD CANDIDATE\033[0m" if composite >= 70
            else "\033[38;5;214mMODERATE\033[0m" if composite >= 45
            else "\033[38;5;196mCOMPLEX\033[0m"
        )
        print(f"  Overall Readiness:  \033[1m{composite:.0f}/100\033[0m  {grade}\n")

        def _bar(val, label, width=30):
            filled = int(val / 100 * width)
            color = "\033[38;5;40m" if val >= 70 else "\033[38;5;214m" if val >= 45 else "\033[38;5;196m"
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
        grade = (
            "\033[38;5;40mGOOD\033[0m" if composite >= 70
            else "\033[38;5;214mMODERATE\033[0m" if composite >= 45
            else "\033[38;5;196mCOMPLEX\033[0m"
        )
        print(
            f"  \033[1m{score['program']:<20s}\033[0m {composite:>5.0f}"
            f"  {score['isolation']:>4.0f} {score['simplicity']:>4.0f}"
            f" {score['dependency_clarity']:>4.0f} {score['testability']:>4.0f}"
            f"  {d['code_lines']:>5d}  {pgm_type:<6s}  {grade}"
        )

    good = sum(1 for s in ranking if s["composite"] >= 70)
    moderate = sum(1 for s in ranking if 45 <= s["composite"] < 70)
    complex_ = sum(1 for s in ranking if s["composite"] < 45)
    print(f"\n  \033[38;5;245m{good} good candidates, {moderate} moderate, {complex_} complex — out of {len(ranking)} programs\033[0m\n")


# ── /summary ──────────────────────────────────────────────────────────────────

def cmd_summary(active, known_codebases):
    graph = get_graph(active, known_codebases)
    if not graph:
        print(f"  \033[38;5;196mNo analysis graph found for {active}. Run analyze.py first.\033[0m")
        return

    s = graph.summary()
    W, R, D, H, G, B = "\033[1m", "\033[0m", "\033[38;5;240m", "\033[38;5;214m", "\033[38;5;40m", "\033[38;5;39m"

    print(f"\n  {H}{'═' * 60}{R}")
    print(f"  {H}  CODEBASE SUMMARY: {active.upper()}{R}")
    print(f"  {H}{'═' * 60}{R}")

    print(f"\n  {H}Size{R}")
    print(f"    Programs:       {W}{s['total_programs']}{R}  ({len(s['cics_programs'])} CICS online, {len(s['batch_programs'])} batch)")
    print(f"    Copybooks:      {W}{s['total_copybooks']}{R}")
    print(f"    Total LOC:      {W}{s['total_loc']:,}{R}  ({s['total_code_lines']:,} code, {s['total_comment_lines']:,} comments)")
    print(f"    Paragraphs:     {W}{s['total_paragraphs']}{R}")

    print(f"\n  {H}Graph Topology{R}")
    print(f"    Total edges:    {W}{s['total_edges']}{R}")
    for etype, count in sorted(s["edge_types"].items(), key=lambda x: -x[1]):
        print(f"      {etype:<15s} {count}")

    components = s["components"]
    print(f"\n  {H}Connected Components{R}")
    print(f"    {W}{len(components)}{R} components")
    for i, comp in enumerate(components[:5]):
        members = sorted(comp)[:6]
        more = f" +{len(comp) - 6} more" if len(comp) > 6 else ""
        print(f"    {D}[{i+1}]{R} {W}{len(comp)}{R} programs: {', '.join(members)}{D}{more}{R}")

    if s["cics_programs"]:
        print(f"\n  {H}CICS Online Programs ({len(s['cics_programs'])}){R}")
        for pgm in sorted(s["cics_programs"]):
            score = graph.enrichment_for(pgm)["hub_score"]
            print(f"    {B}{pgm}{R}  {D}hub={score:.0f}{R}")

    if s["batch_programs"]:
        print(f"\n  {H}Batch Programs ({len(s['batch_programs'])}){R}")
        for pgm in sorted(s["batch_programs"]):
            score = graph.enrichment_for(pgm)["hub_score"]
            print(f"    {G}{pgm}{R}  {D}hub={score:.0f}{R}")

    shared = s["shared_copybooks"]
    if shared:
        print(f"\n  {H}Most Shared Copybooks (coupling indicators){R}")
        for cb, user_count, users in shared[:10]:
            user_list = ", ".join(users[:4])
            more = f" +{user_count - 4}" if user_count > 4 else ""
            bar = "\033[38;5;214m" + "█" * min(user_count, 20) + R
            print(f"    {W}{cb:<16s}{R} {user_count:>2d} programs  {bar}  {D}{user_list}{more}{R}")

    hubs = s["hub_programs"]
    if hubs:
        print(f"\n  {H}Top Hotspots (change risk){R}")
        for name, score in hubs[:5]:
            callers = len(graph.callers(name))
            callees = len(graph.callees(name))
            cbs = len(graph.copybooks_of(name))
            print(f"    {W}{name:<20s}{R} score={score:.0f}  in={callers} out={callees} copy={cbs}")

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

    unresolved_cbs = s["unresolved_copybooks"]
    unresolved_calls = s["unresolved_calls"]
    if unresolved_cbs or unresolved_calls:
        print(f"\n  {H}Unresolved External References{R}")
        if unresolved_cbs:
            print(f"    Copybooks ({len(unresolved_cbs)}): {D}{', '.join(unresolved_cbs[:8])}{R}")
        if unresolved_calls:
            print(f"    Call targets ({len(unresolved_calls)}): {D}{', '.join(unresolved_calls[:8])}{R}")

    if s["total_programs"] > 0 and s["total_loc"] > 0:
        comment_ratio = s["total_comment_lines"] / s["total_loc"] * 100
        parse_coverage = (s['total_programs'] / (s['total_programs'] + len(unresolved_calls))) * 100 if unresolved_calls else 100
        print(f"\n  {H}Parse Coverage{R}")
        print(f"    Programs parsed: {W}{s['total_programs']}{R}")
        print(f"    Comment ratio:   {W}{comment_ratio:.1f}%{R}")
        print(f"    Resolved calls:  {W}{parse_coverage:.0f}%{R} ({len(unresolved_calls)} unresolved)")

    print(f"\n  {H}{'═' * 60}{R}\n")
