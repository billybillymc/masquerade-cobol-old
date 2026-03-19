"""
Data-oriented CLI commands: dict (copybook dictionary), screens (BMS),
jobs (JCL), trace (data flow), xref (cross-reference).
"""

import os
from pathlib import Path


# ── Lazy-loaded indexes ───────────────────────────────────────────────────────

_copybook_dicts: dict[str, object] = {}
_screen_flow_indexes: dict[str, object] = {}
_jcl_indexes: dict[str, object] = {}
_data_flow_indexes: dict[str, object] = {}


def _get_copybook_dict(codebase, known_codebases):
    if codebase not in _copybook_dicts:
        from copybook_dict import CopybookDictionary
        info = known_codebases.get(codebase, {})
        try:
            _copybook_dicts[codebase] = CopybookDictionary(info["dir"])
        except Exception:
            _copybook_dicts[codebase] = None
    return _copybook_dicts[codebase]


def _get_screen_flow(codebase, known_codebases):
    if codebase not in _screen_flow_indexes:
        from bms_parser import ScreenFlowIndex
        info = known_codebases.get(codebase, {})
        try:
            _screen_flow_indexes[codebase] = ScreenFlowIndex(info["dir"])
        except Exception:
            _screen_flow_indexes[codebase] = None
    return _screen_flow_indexes[codebase]


def _get_jcl_index(codebase, known_codebases):
    if codebase not in _jcl_indexes:
        from jcl_parser import JclIndex
        info = known_codebases.get(codebase, {})
        try:
            _jcl_indexes[codebase] = JclIndex(info["dir"])
        except Exception:
            _jcl_indexes[codebase] = None
    return _jcl_indexes[codebase]


def _get_data_flow_index(codebase, known_codebases):
    if codebase not in _data_flow_indexes:
        from graph_context import DataFlowIndex
        analysis_dir = str(Path(known_codebases[codebase]["dir"]) / "_analysis")
        try:
            _data_flow_indexes[codebase] = DataFlowIndex(analysis_dir)
        except FileNotFoundError:
            _data_flow_indexes[codebase] = None
    return _data_flow_indexes[codebase]


# ── /dict ─────────────────────────────────────────────────────────────────────

def cmd_dict(arg, active, known_codebases):
    cbd = _get_copybook_dict(active, known_codebases)
    if not cbd:
        print(f"  \033[38;5;196mNo copybook files found for {active}.\033[0m")
        return

    W, R, D, H, B = "\033[1m", "\033[0m", "\033[38;5;240m", "\033[38;5;214m", "\033[38;5;39m"

    if not arg:
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


# ── /screens ──────────────────────────────────────────────────────────────────

def cmd_screens(arg, active, known_codebases):
    sfi = _get_screen_flow(active, known_codebases)
    if not sfi:
        print(f"  \033[38;5;196mNo BMS map files found for {active}.\033[0m")
        return

    W, R, D, H, B, G = "\033[1m", "\033[0m", "\033[38;5;240m", "\033[38;5;214m", "\033[38;5;39m", "\033[38;5;40m"

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


# ── /jobs ─────────────────────────────────────────────────────────────────────

def cmd_jobs(arg, active, known_codebases):
    jcl = _get_jcl_index(active, known_codebases)
    if not jcl:
        print(f"  \033[38;5;196mNo JCL files found for {active}.\033[0m")
        return

    W, R, D, H, B, G = "\033[1m", "\033[0m", "\033[38;5;240m", "\033[38;5;214m", "\033[38;5;39m", "\033[38;5;40m"

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

    detail = jcl.job_detail(arg.upper())
    if not detail:
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


# ── /trace ────────────────────────────────────────────────────────────────────

def cmd_trace(arg, active, known_codebases):
    if not arg:
        print("  \033[38;5;196mUsage: /trace <field_name>\033[0m")
        print("  \033[38;5;240mExamples: /trace WS-RETURN-MSG, /trace ACCT-BALANCE\033[0m")
        return

    dfi = _get_data_flow_index(active, known_codebases)
    if not dfi:
        print(f"  \033[38;5;196mNo analysis data found for {active}. Run analyze.py first.\033[0m")
        return

    field = arg.upper()
    trace = dfi.trace_field(field, direction="both", max_depth=3)

    W, R, D, H, G, B = "\033[1m", "\033[0m", "\033[38;5;240m", "\033[38;5;214m", "\033[38;5;40m", "\033[38;5;39m"

    programs = trace["programs_touching"]
    if not programs and not trace["forward_trace"] and not trace["backward_trace"]:
        print(f"  \033[38;5;196mField '{field}' not found in any data flow.\033[0m")
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

    defs = dfi.field_definition(field)
    if defs:
        print(f"\n  {H}Definitions:{R}")
        for d in defs[:5]:
            pic_str = f" PIC {d['picture']}" if d['picture'] else ""
            occ_str = f" OCCURS {d['occurs']}" if d.get('occurs') else ""
            print(f"    {B}{d['program']}{R}: {W}level-{d['level']:02d}{R} {d['name']}{pic_str}{occ_str}")

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

    bindings = dfi.cross_program_bindings(field)
    if bindings:
        print(f"\n  {H}Cross-Program CALL USING Bindings:{R}")
        for b in bindings[:10]:
            print(f"    {W}{b['caller']}{R} -> {W}{b['callee']}{R}  {D}(passes: {', '.join(b['all_args'][:5])}){R}")
    print()


# ── /xref ─────────────────────────────────────────────────────────────────────

def cmd_xref(arg, active, known_codebases):
    if not arg:
        print("  \033[38;5;196mUsage: /xref <field_name>\033[0m")
        print("  \033[38;5;240mExamples: /xref ACCT-NUM, /xref WS-RETURN-MSG\033[0m")
        print("  \033[38;5;240mSupports partial matching: /xref ACCT\033[0m")
        return

    dfi = _get_data_flow_index(active, known_codebases)
    if not dfi:
        print(f"  \033[38;5;196mNo analysis data found for {active}. Run analyze.py first.\033[0m")
        return

    W, R, D, H, B, G = "\033[1m", "\033[0m", "\033[38;5;240m", "\033[38;5;214m", "\033[38;5;39m", "\033[38;5;40m"
    RED, Y = "\033[38;5;196m", "\033[38;5;220m"

    field = arg.upper()
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
    print(
        f"  {D}Programs: {R}{xref['total_programs']}    "
        f"{D}Writes: {R}{xref['total_writes']}    "
        f"{D}Reads: {R}{xref['total_reads']}    "
        f"{D}CALL refs: {R}{xref['total_call_refs']}\n"
    )

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
        print()

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
