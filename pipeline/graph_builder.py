"""
Builds dependency graphs from parsed COBOL programs.
Produces inter-program call graphs, copybook dependency maps,
intra-program control flow, and field-level data lineage stubs.
"""

from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
from typing import Optional

from cobol_parser import CobolProgram, CopyStatement, CallTarget


@dataclass
class Edge:
    source: str
    target: str
    edge_type: str  # CALLS, XCTL, LINK, COPIES, PERFORMS, READS_FILE, WRITES_FILE, CICS_IO
    weight: int = 1
    evidence: list[dict] = field(default_factory=list)


@dataclass
class Node:
    name: str
    node_type: str  # PROGRAM, COPYBOOK, PARAGRAPH, FILE, MAP
    source_file: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class DependencyGraph:
    nodes: dict[str, Node]
    edges: list[Edge]
    programs: dict[str, CobolProgram]
    unresolved_copybooks: set[str]
    unresolved_calls: set[str]


def build_graph(programs: list[CobolProgram], copybook_files: set[str]) -> DependencyGraph:
    """Build a full dependency graph from a list of parsed programs."""
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    program_map: dict[str, CobolProgram] = {}
    known_programs = {p.program_id.upper() for p in programs}
    known_copybooks = {Path(c).stem.upper() for c in copybook_files}
    unresolved_copybooks: set[str] = set()
    unresolved_calls: set[str] = set()

    for prog in programs:
        pid = prog.program_id.upper()
        program_map[pid] = prog
        nodes[f"PGM:{pid}"] = Node(
            name=pid,
            node_type='PROGRAM',
            source_file=prog.source_file,
            metadata={
                'total_lines': prog.total_lines,
                'code_lines': prog.code_lines,
                'comment_lines': prog.comment_lines,
                'paragraph_count': len(prog.paragraphs),
                'data_flow_count': len(prog.data_flows),
                'author': prog.author,
            },
        )

        # Copybook edges
        for cs in prog.copy_statements:
            cb_name = cs.copybook_name.upper()
            cb_key = f"CPY:{cb_name}"
            if cb_key not in nodes:
                nodes[cb_key] = Node(name=cb_name, node_type='COPYBOOK')
            if cb_name not in known_copybooks:
                unresolved_copybooks.add(cb_name)
            edges.append(Edge(
                source=f"PGM:{pid}",
                target=cb_key,
                edge_type='COPIES',
                evidence=[{
                    'file': cs.span.file,
                    'line': cs.span.start_line,
                    'replacing': cs.replacing,
                }],
            ))

        # Inter-program call edges
        for ct in prog.call_targets:
            target = ct.target_program.upper()
            target_key = f"PGM:{target}"
            if target_key not in nodes:
                nodes[target_key] = Node(name=target, node_type='PROGRAM')
            if target not in known_programs:
                unresolved_calls.add(target)
            edges.append(Edge(
                source=f"PGM:{pid}",
                target=target_key,
                edge_type=ct.call_type,
                evidence=[{
                    'file': ct.span.file,
                    'line': ct.span.start_line,
                    'using': ct.using_args,
                }],
            ))

        # File control edges
        for fc in prog.file_controls:
            file_key = f"FILE:{fc.assign_to.upper()}"
            if file_key not in nodes:
                nodes[file_key] = Node(
                    name=fc.assign_to,
                    node_type='FILE',
                    metadata={'organization': fc.organization, 'access': fc.access_mode},
                )
            edges.append(Edge(
                source=f"PGM:{pid}",
                target=file_key,
                edge_type='READS_FILE',
                evidence=[{'file': fc.span.file, 'line': fc.span.start_line}],
            ))

        # CICS dataset edges
        for cics in prog.cics_operations:
            if cics.dataset:
                ds_key = f"FILE:{cics.dataset.upper()}"
                if ds_key not in nodes:
                    nodes[ds_key] = Node(name=cics.dataset, node_type='FILE')
                edges.append(Edge(
                    source=f"PGM:{pid}",
                    target=ds_key,
                    edge_type='CICS_IO',
                    evidence=[{
                        'file': cics.span.file,
                        'line': cics.span.start_line,
                        'operation': cics.operation,
                    }],
                ))

            if cics.map_name:
                map_key = f"MAP:{cics.map_name.upper()}"
                if map_key not in nodes:
                    nodes[map_key] = Node(
                        name=cics.map_name,
                        node_type='MAP',
                        metadata={'mapset': cics.mapset},
                    )
                edges.append(Edge(
                    source=f"PGM:{pid}",
                    target=map_key,
                    edge_type='CICS_IO',
                    evidence=[{
                        'file': cics.span.file,
                        'line': cics.span.start_line,
                        'operation': cics.operation,
                    }],
                ))

        # Data flow summary per program (stored as metadata, not individual edges)
        flow_summary: dict[str, set] = defaultdict(set)
        for df in prog.data_flows:
            for src in df.sources:
                for tgt in df.targets:
                    flow_summary[tgt].add(src)

        # CALL USING parameter binding edges
        for ct in prog.call_targets:
            if ct.using_args:
                target = ct.target_program.upper()
                for arg in ct.using_args:
                    edges.append(Edge(
                        source=f"PGM:{pid}",
                        target=f"PGM:{target}",
                        edge_type='DATA_PASSES',
                        evidence=[{
                            'file': ct.span.file,
                            'line': ct.span.start_line,
                            'field': arg,
                            'call_type': ct.call_type,
                        }],
                    ))

        # Intra-program paragraph edges
        for para in prog.paragraphs:
            para_key = f"PGM:{pid}::PARA:{para.name}"
            nodes[para_key] = Node(
                name=para.name,
                node_type='PARAGRAPH',
                source_file=prog.source_file,
                metadata={
                    'program': pid,
                    'start_line': para.span.start_line,
                    'end_line': para.span.end_line,
                    'call_count': len(para.calls),
                    'perform_count': len(para.performs),
                    'cics_count': len(para.cics_ops),
                    'data_flow_count': len(para.data_flows),
                },
            )
            for pt in para.performs:
                target_para_key = f"PGM:{pid}::PARA:{pt.target_paragraph}"
                edges.append(Edge(
                    source=para_key,
                    target=target_para_key,
                    edge_type='PERFORMS',
                    evidence=[{
                        'file': pt.span.file,
                        'line': pt.span.start_line,
                        'is_loop': pt.is_loop,
                        'thru': pt.thru_paragraph,
                    }],
                ))

    return DependencyGraph(
        nodes=nodes,
        edges=edges,
        programs=program_map,
        unresolved_copybooks=unresolved_copybooks,
        unresolved_calls=unresolved_calls,
    )


def compute_stats(graph: DependencyGraph) -> dict:
    """Compute summary statistics from the dependency graph."""
    node_counts = defaultdict(int)
    for n in graph.nodes.values():
        node_counts[n.node_type] += 1

    edge_counts = defaultdict(int)
    for e in graph.edges:
        edge_counts[e.edge_type] += 1

    total_loc = sum(p.total_lines for p in graph.programs.values())
    total_code = sum(p.code_lines for p in graph.programs.values())
    total_comments = sum(p.comment_lines for p in graph.programs.values())
    total_paragraphs = sum(len(p.paragraphs) for p in graph.programs.values())
    total_copybook_refs = sum(len(p.copy_statements) for p in graph.programs.values())
    total_calls = sum(len(p.call_targets) for p in graph.programs.values())
    total_cics = sum(len(p.cics_operations) for p in graph.programs.values())

    total_data_flows = sum(len(p.data_flows) for p in graph.programs.values())
    programs_with_cics = sum(1 for p in graph.programs.values() if p.cics_operations)
    programs_batch = len(graph.programs) - programs_with_cics

    return {
        'node_counts': dict(node_counts),
        'edge_counts': dict(edge_counts),
        'total_programs': len(graph.programs),
        'total_loc': total_loc,
        'total_code_lines': total_code,
        'total_comment_lines': total_comments,
        'total_paragraphs': total_paragraphs,
        'total_copybook_refs': total_copybook_refs,
        'total_inter_program_calls': total_calls,
        'total_cics_operations': total_cics,
        'programs_online_cics': programs_with_cics,
        'programs_batch': programs_batch,
        'total_data_flows': total_data_flows,
        'unresolved_copybooks': sorted(graph.unresolved_copybooks),
        'unresolved_calls': sorted(graph.unresolved_calls),
    }
