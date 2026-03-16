"""
Main entry point: scans a COBOL codebase directory, parses all sources,
builds dependency graph, and outputs JSON artifacts + summary.

Usage:
    python analyze.py <codebase_dir> [--output <output_dir>]
"""

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from collections import defaultdict

from cobol_parser import (
    parse_cobol_file, CobolProgram, SourceSpan,
    Statement, IfBlock, EvaluateBlock, WhenBranch, PerformInline,
    GoTo, Predicate,
)
from graph_builder import build_graph, compute_stats, DependencyGraph


COBOL_EXTENSIONS = {'.cbl', '.cob', '.CBL', '.COB'}
COPYBOOK_EXTENSIONS = {'.cpy', '.CPY'}


def find_cobol_files(root: Path) -> tuple[list[Path], list[Path]]:
    """Recursively find COBOL source and copybook files."""
    sources = []
    copybooks = []
    for f in sorted(root.rglob('*')):
        if f.is_file():
            if f.suffix in COBOL_EXTENSIONS:
                sources.append(f)
            elif f.suffix in COPYBOOK_EXTENSIONS:
                copybooks.append(f)
    return sources, copybooks


def _span_to_dict(span):
    if span is None:
        return None
    return {'file': span.file, 'start_line': span.start_line, 'end_line': span.end_line}


def _predicate_to_dict(pred: Predicate) -> dict:
    d = {
        'left': pred.left,
        'operator': pred.operator,
        'right': pred.right,
        'raw_text': pred.raw_text,
    }
    if pred.is_88_condition:
        d['is_88_condition'] = True
    if pred.children:
        d['children'] = [_predicate_to_dict(c) for c in pred.children]
    return d


def _statement_to_dict(stmt: Statement) -> dict:
    d = {'stmt_type': stmt.stmt_type}
    if stmt.span:
        d['span'] = _span_to_dict(stmt.span)

    if stmt.stmt_type == 'IF' and isinstance(stmt.data, IfBlock):
        blk = stmt.data
        d['condition'] = _predicate_to_dict(blk.condition)
        d['then_body'] = [_statement_to_dict(s) for s in blk.then_body]
        d['else_body'] = [_statement_to_dict(s) for s in blk.else_body]
    elif stmt.stmt_type == 'EVALUATE' and isinstance(stmt.data, EvaluateBlock):
        blk = stmt.data
        d['subjects'] = blk.subjects
        d['branches'] = []
        for br in blk.branches:
            brd = {
                'conditions': br.conditions,
                'body': [_statement_to_dict(s) for s in br.body],
            }
            if br.condition_predicate:
                brd['condition_predicate'] = _predicate_to_dict(br.condition_predicate)
            d['branches'].append(brd)
    elif stmt.stmt_type == 'PERFORM_INLINE' and isinstance(stmt.data, PerformInline):
        blk = stmt.data
        if blk.varying:
            d['varying'] = blk.varying
        if blk.until:
            d['until'] = _predicate_to_dict(blk.until)
        d['body'] = [_statement_to_dict(s) for s in blk.body]
    elif stmt.stmt_type == 'GOTO' and isinstance(stmt.data, GoTo):
        d['targets'] = stmt.data.targets
        if stmt.data.depending_on:
            d['depending_on'] = stmt.data.depending_on
    elif isinstance(stmt.data, str):
        d['raw'] = stmt.data

    return d


def _goto_to_dict(goto: GoTo) -> dict:
    d = {
        'targets': goto.targets,
        'span': _span_to_dict(goto.span),
    }
    if goto.depending_on:
        d['depending_on'] = goto.depending_on
    return d


def program_to_dict(prog: CobolProgram) -> dict:
    """Serialize a CobolProgram to a JSON-safe dict."""
    return {
        'program_id': prog.program_id,
        'source_file': prog.source_file,
        'author': prog.author,
        'total_lines': prog.total_lines,
        'code_lines': prog.code_lines,
        'comment_lines': prog.comment_lines,
        'divisions': {
            'identification': _span_to_dict(prog.identification_division),
            'environment': _span_to_dict(prog.environment_division),
            'data': _span_to_dict(prog.data_division),
            'procedure': _span_to_dict(prog.procedure_division),
        },
        'paragraphs': [
            {
                'name': p.name,
                'span': _span_to_dict(p.span),
                'performs': [
                    {'target': pt.target_paragraph, 'thru': pt.thru_paragraph, 'is_loop': pt.is_loop}
                    for pt in p.performs
                ],
                'calls': [
                    {'target': ct.target_program, 'type': ct.call_type}
                    for ct in p.calls
                ],
                'cics_ops': [
                    {'operation': c.operation, 'dataset': c.dataset, 'map': c.map_name, 'program': c.program}
                    for c in p.cics_ops
                ],
                'data_flows': [
                    {'type': df.flow_type, 'sources': df.sources, 'targets': df.targets}
                    for df in p.data_flows
                ],
                'conditional_blocks': [_statement_to_dict(s) for s in p.conditional_blocks],
                'goto_targets': [_goto_to_dict(g) for g in p.goto_targets],
            }
            for p in prog.paragraphs
        ],
        'copy_statements': [
            {'copybook': cs.copybook_name, 'replacing': cs.replacing, 'line': cs.span.start_line}
            for cs in prog.copy_statements
        ],
        'call_targets': [
            {'target': ct.target_program, 'type': ct.call_type, 'using': ct.using_args, 'line': ct.span.start_line}
            for ct in prog.call_targets
        ],
        'file_controls': [
            {'name': fc.select_name, 'assign_to': fc.assign_to, 'organization': fc.organization}
            for fc in prog.file_controls
        ],
        'data_items_count': len(prog.data_items),
        'data_items_sample': [
            {'level': d.level, 'name': d.name, 'picture': d.picture, 'occurs': d.occurs}
            for d in prog.data_items[:50]
        ],
        'data_flows_count': len(prog.data_flows),
        'data_flows': [
            {
                'type': df.flow_type,
                'sources': df.sources,
                'targets': df.targets,
                'paragraph': df.paragraph,
                'line': df.span.start_line,
            }
            for df in prog.data_flows
        ],
    }


def graph_to_dict(graph: DependencyGraph) -> dict:
    """Serialize the dependency graph to a JSON-safe dict."""
    nodes = []
    for key, node in graph.nodes.items():
        nodes.append({
            'id': key,
            'name': node.name,
            'type': node.node_type,
            'source_file': node.source_file,
            'metadata': node.metadata,
        })

    edges = []
    for e in graph.edges:
        edges.append({
            'source': e.source,
            'target': e.target,
            'type': e.edge_type,
            'evidence': e.evidence,
        })

    return {'nodes': nodes, 'edges': edges}


def print_summary(stats: dict, programs: list[CobolProgram], graph: DependencyGraph):
    """Print a human-readable summary to stdout."""
    print("\n" + "=" * 70)
    print("  COBOL CODEBASE ANALYSIS REPORT")
    print("=" * 70)

    print(f"\n  Programs parsed:        {stats['total_programs']}")
    print(f"  Total lines:            {stats['total_loc']:,}")
    print(f"  Code lines:             {stats['total_code_lines']:,}")
    print(f"  Comment lines:          {stats['total_comment_lines']:,}")
    print(f"  Online (CICS) programs: {stats['programs_online_cics']}")
    print(f"  Batch programs:         {stats['programs_batch']}")

    print(f"\n  Paragraphs:             {stats['total_paragraphs']}")
    print(f"  Copybook references:    {stats['total_copybook_refs']}")
    print(f"  Inter-program calls:    {stats['total_inter_program_calls']}")
    print(f"  CICS operations:        {stats['total_cics_operations']}")
    print(f"  Data flow statements:   {stats.get('total_data_flows', 0)}")

    print("\n  --- Node Counts ---")
    for ntype, count in sorted(stats['node_counts'].items()):
        print(f"    {ntype:15s} {count}")

    print("\n  --- Edge Counts ---")
    for etype, count in sorted(stats['edge_counts'].items()):
        print(f"    {etype:15s} {count}")

    if stats['unresolved_copybooks']:
        print(f"\n  Unresolved copybooks ({len(stats['unresolved_copybooks'])}):")
        for cb in stats['unresolved_copybooks'][:20]:
            print(f"    - {cb}")

    if stats['unresolved_calls']:
        print(f"\n  Unresolved call targets ({len(stats['unresolved_calls'])}):")
        for ct in stats['unresolved_calls'][:20]:
            print(f"    - {ct}")

    # Per-program summary table
    print("\n  --- Programs ---")
    print(f"  {'Program':<16s} {'Lines':>6s} {'Code':>6s} {'Para':>5s} {'Copy':>5s} {'Call':>5s} {'CICS':>5s}")
    print("  " + "-" * 54)
    for prog in sorted(programs, key=lambda p: p.program_id):
        print(f"  {prog.program_id:<16s} {prog.total_lines:>6d} {prog.code_lines:>6d} "
              f"{len(prog.paragraphs):>5d} {len(prog.copy_statements):>5d} "
              f"{len(prog.call_targets):>5d} {len(prog.cics_operations):>5d}")

    # Call graph summary
    call_edges = [e for e in graph.edges if e.edge_type in ('CALL', 'XCTL', 'LINK')]
    if call_edges:
        print("\n  --- Inter-Program Call Graph ---")
        seen = set()
        for e in call_edges:
            src = e.source.replace('PGM:', '')
            tgt = e.target.replace('PGM:', '')
            key = f"{src}->{tgt}"
            if key not in seen:
                seen.add(key)
                print(f"    {src} --[{e.edge_type}]--> {tgt}")

    # Copybook sharing analysis
    copybook_users = defaultdict(list)
    for e in graph.edges:
        if e.edge_type == 'COPIES':
            src = e.source.replace('PGM:', '')
            tgt = e.target.replace('CPY:', '')
            copybook_users[tgt].append(src)

    shared = {cb: users for cb, users in copybook_users.items() if len(users) > 1}
    if shared:
        print(f"\n  --- Shared Copybooks (used by multiple programs) ---")
        for cb, users in sorted(shared.items(), key=lambda x: -len(x[1])):
            print(f"    {cb} ({len(users)} programs): {', '.join(sorted(users))}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Analyze a COBOL codebase')
    parser.add_argument('codebase_dir', help='Root directory of the COBOL codebase')
    parser.add_argument('--output', '-o', default=None, help='Output directory for JSON artifacts')
    args = parser.parse_args()

    root = Path(args.codebase_dir)
    if not root.exists():
        print(f"Error: {root} does not exist", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output) if args.output else root / '_analysis'
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {root} for COBOL files...")
    sources, copybooks = find_cobol_files(root)
    print(f"  Found {len(sources)} source files, {len(copybooks)} copybook files")

    copybook_set = {str(c) for c in copybooks}

    programs: list[CobolProgram] = []
    errors: list[dict] = []

    t0 = time.time()
    for src in sources:
        try:
            prog = parse_cobol_file(src)
            programs.append(prog)
        except Exception as ex:
            errors.append({'file': str(src), 'error': str(ex)})
            print(f"  ERROR parsing {src.name}: {ex}", file=sys.stderr)

    parse_time = time.time() - t0
    print(f"  Parsed {len(programs)} programs in {parse_time:.2f}s ({len(errors)} errors)")

    print("Building dependency graph...")
    t1 = time.time()
    graph = build_graph(programs, copybook_set)
    stats = compute_stats(graph)
    graph_time = time.time() - t1
    print(f"  Graph built in {graph_time:.2f}s")

    print_summary(stats, programs, graph)

    # Write artifacts
    programs_json = {p.program_id: program_to_dict(p) for p in programs}
    graph_json = graph_to_dict(graph)

    (output_dir / 'programs.json').write_text(json.dumps(programs_json, indent=2))
    (output_dir / 'graph.json').write_text(json.dumps(graph_json, indent=2))
    (output_dir / 'stats.json').write_text(json.dumps(stats, indent=2))

    if errors:
        (output_dir / 'errors.json').write_text(json.dumps(errors, indent=2))

    # Write DOT file for graphviz visualization of inter-program calls
    dot_lines = ['digraph cobol_calls {', '  rankdir=LR;', '  node [shape=box, style=filled];']

    for node in graph.nodes.values():
        if node.node_type == 'PROGRAM':
            color = '#4A90D9' if any(
                e.edge_type == 'CICS_IO' for e in graph.edges if e.source == f"PGM:{node.name}"
            ) else '#7BC67E'
            dot_lines.append(f'  "{node.name}" [fillcolor="{color}", fontcolor="white"];')
        elif node.node_type == 'FILE':
            dot_lines.append(f'  "{node.name}" [shape=cylinder, fillcolor="#F5A623", fontcolor="white"];')
        elif node.node_type == 'COPYBOOK':
            dot_lines.append(f'  "{node.name}" [shape=note, fillcolor="#D0D0D0"];')

    seen_edges = set()
    for e in graph.edges:
        if e.edge_type in ('CALL', 'XCTL', 'LINK', 'COPIES', 'READS_FILE', 'CICS_IO'):
            src = e.source.split(':')[-1] if '::' not in e.source else None
            tgt = e.target.split(':')[-1] if '::' not in e.target else None
            if src and tgt:
                src_name = e.source.replace('PGM:', '').replace('CPY:', '').replace('FILE:', '').replace('MAP:', '')
                tgt_name = e.target.replace('PGM:', '').replace('CPY:', '').replace('FILE:', '').replace('MAP:', '')
                edge_key = f"{src_name}-{e.edge_type}-{tgt_name}"
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    style = ''
                    if e.edge_type == 'COPIES':
                        style = ' [style=dashed, color="#999999"]'
                    elif e.edge_type in ('READS_FILE', 'CICS_IO'):
                        style = f' [style=dotted, color="#F5A623", label="{e.edge_type}"]'
                    elif e.edge_type in ('XCTL', 'LINK'):
                        style = f' [color="#D94A4A", label="{e.edge_type}"]'
                    dot_lines.append(f'  "{src_name}" -> "{tgt_name}"{style};')

    dot_lines.append('}')
    (output_dir / 'call_graph.dot').write_text('\n'.join(dot_lines))

    print(f"\n  Artifacts written to {output_dir}/")
    print(f"    programs.json  — per-program structure ({len(programs)} programs)")
    print(f"    graph.json     — full dependency graph ({len(graph.nodes)} nodes, {len(graph.edges)} edges)")
    print(f"    stats.json     — summary statistics")
    print(f"    call_graph.dot — graphviz visualization (render with: dot -Tsvg call_graph.dot -o call_graph.svg)")
    if errors:
        print(f"    errors.json    — {len(errors)} parse errors")


if __name__ == '__main__':
    main()
