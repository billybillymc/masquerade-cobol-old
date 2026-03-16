"""
Behavioral specification generator — produces structured program specs
from static analysis data alone (no API keys required).

Each spec documents: purpose, I/O, control flow, data contracts,
business logic indicators, dependencies, and reimplementation guidance.
"""

import json
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graph_context import GraphIndex, DataFlowIndex
from complexity import compute_complexity, complexity_grade


@dataclass
class ParagraphSpec:
    name: str
    performs: list[str]
    calls: list[str]
    cics_ops: list[str]
    data_flows_in: list[str]
    data_flows_out: list[str]
    decision_indicators: int
    is_entry_point: bool


@dataclass
class DataContract:
    copybook: str
    field_count: int
    key_fields: list[str]
    shared_with: list[str]


@dataclass
class ProgramSpec:
    program: str
    program_type: str
    source_file: str
    total_lines: int
    code_lines: int
    paragraph_count: int

    # Complexity
    cyclomatic_complexity: int
    max_nesting: int
    complexity_grade: str

    # Dependencies
    callers: list[str]
    callees: list[str]
    copybooks: list[str]
    files_accessed: list[str]

    # Readiness
    readiness_score: float
    effort_days: float
    risk_level: str

    # Structural
    paragraphs: list[ParagraphSpec]
    data_contracts: list[DataContract]
    cics_operations: list[str]
    data_flow_summary: dict

    # Control flow
    entry_paragraphs: list[str]
    exit_points: list[str]
    perform_graph: dict[str, list[str]]

    # Business logic indicators
    decision_count: int
    computation_count: int
    validation_fields: list[str]

    # Reimplementation
    modern_pattern: str
    migration_wave: str
    notes: list[str]


def _load_program_data(analysis_dir: Path) -> dict:
    """Load programs.json from analysis directory."""
    path = analysis_dir / "programs.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data
    return {p["program_id"]: p for p in data}


def _infer_modern_pattern(has_cics: bool, has_batch_files: bool, has_db: bool, cics_ops: list) -> str:
    """Suggest modern architecture pattern."""
    patterns = []
    if has_cics:
        screen_ops = [op for op in cics_ops if any(k in op.upper() for k in ("SEND", "RECEIVE", "MAP"))]
        if screen_ops:
            patterns.append("REST API + SPA frontend (replacing BMS screens)")
        else:
            patterns.append("Microservice with API endpoints (replacing CICS transactions)")
    if has_batch_files:
        patterns.append("Event-driven pipeline or scheduled job (replacing batch file processing)")
    if has_db:
        patterns.append("ORM/repository pattern (replacing direct DB2/VSAM access)")
    if not patterns:
        patterns.append("Standalone service or library module")
    return " / ".join(patterns)


def _extract_validation_fields(data_flows: list[dict], paragraphs: list[dict]) -> list[str]:
    """Identify fields likely involved in validation (appear in both reads and condition checks)."""
    fields = set()
    for p in paragraphs:
        for df in p.get("data_flows", []):
            if df.get("flow_type") in ("MOVE", "COMPUTE", "STRING", "UNSTRING"):
                for t in df.get("targets", []):
                    name = t.upper()
                    if any(kw in name for kw in ("STATUS", "CODE", "FLAG", "ERR", "VALID", "RC", "RETURN", "IND", "SWITCH")):
                        fields.add(t)
    return sorted(fields)


def _build_perform_graph(paragraphs: list[dict]) -> dict[str, list[str]]:
    """Build a paragraph-to-paragraph perform graph."""
    graph = {}
    for p in paragraphs:
        targets = []
        for perf in p.get("performs", []):
            targets.append(perf.get("target_paragraph", ""))
        graph[p["name"]] = targets
    return graph


def _find_entry_paragraphs(paragraphs: list[dict], perform_graph: dict) -> list[str]:
    """Find paragraphs that are not performed by any other paragraph (likely entry points)."""
    all_targets = set()
    for targets in perform_graph.values():
        all_targets.update(targets)
    return [p["name"] for p in paragraphs if p["name"] not in all_targets]


def _find_exit_points(paragraphs: list[dict]) -> list[str]:
    """Find paragraphs containing STOP RUN, GOBACK, or similar exit indicators."""
    exit_paras = []
    for p in paragraphs:
        name = p["name"].upper()
        if any(kw in name for kw in ("EXIT", "STOP", "END", "GOBACK", "RETURN", "DONE", "FINISH", "TERM")):
            exit_paras.append(p["name"])
    return exit_paras


def _count_computations(paragraphs: list[dict]) -> int:
    count = 0
    for p in paragraphs:
        for df in p.get("data_flows", []):
            if df.get("flow_type") in ("COMPUTE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"):
                count += 1
    return count


def generate_program_spec(
    program_id: str,
    graph: GraphIndex,
    program_data: dict,
    codebase_dir: str,
) -> Optional[ProgramSpec]:
    """Generate a behavioral specification for a single program."""
    node_id = f"PGM:{program_id}"
    node = graph.nodes.get(node_id)
    if not node:
        return None

    meta = node.get("metadata", {})
    enrichment = graph.enrichment_for(program_id)
    readiness = graph.readiness_score(program_id)

    pgm_info = program_data.get(program_id, {})
    paragraphs_raw = pgm_info.get("paragraphs", [])

    # Complexity — source_file is at node level, relative to pipeline dir
    source_file = node.get("source_file", "") or meta.get("source_file", "")
    source_path = None
    if source_file:
        pipeline_dir = Path(__file__).resolve().parent
        candidate = pipeline_dir / source_file
        if candidate.exists():
            source_path = candidate
        else:
            candidate2 = Path(codebase_dir) / source_file
            if candidate2.exists():
                source_path = candidate2

    cc_result = None
    if source_path and source_path.exists():
        cc_result = compute_complexity(str(source_path))

    # Program type detection — check for CICS edges in graph
    cics_edge_types = {"CICS_IO"}
    has_cics = (
        meta.get("has_cics", False)
        or bool(pgm_info.get("cics_operations", []))
        or any(e["type"] in cics_edge_types for e in graph.edges if e["source"] == node_id)
        or bool(readiness.get("details", {}).get("has_cics", False))
    )
    cics_ops_raw = pgm_info.get("cics_operations", [])
    cics_ops_list = [f"{op.get('operation', '')}({op.get('dataset', '') or op.get('map_name', '') or op.get('program', '') or ''})" for op in cics_ops_raw]
    has_file_io = bool(pgm_info.get("file_controls", []))
    has_db = any("SQL" in (op.get("operation", "") or "").upper() for op in cics_ops_raw)

    # File access
    file_edges = [e for e in graph.edges if e["source"] == node_id and e["type"] in ("READS_FILE", "CICS_IO")]
    files_accessed = []
    for e in file_edges:
        tgt = graph.nodes.get(e["target"], {})
        files_accessed.append(f"{tgt.get('name', e['target'])} ({e['type']})")

    # Data flow
    dfi = DataFlowIndex(str(Path(codebase_dir) / "_analysis"))
    flow_summary = dfi.program_flow_summary(program_id)

    # Perform graph
    perform_graph = _build_perform_graph(paragraphs_raw)
    entry_paragraphs = _find_entry_paragraphs(paragraphs_raw, perform_graph)
    exit_points = _find_exit_points(paragraphs_raw)

    # Build paragraph specs
    para_specs = []
    for p in paragraphs_raw:
        flows_in = set()
        flows_out = set()
        for df in p.get("data_flows", []):
            for s in df.get("sources", []):
                flows_in.add(s)
            for t in df.get("targets", []):
                flows_out.add(t)

        decision_count = 0
        for df in p.get("data_flows", []):
            if df.get("flow_type") in ("COMPUTE", "ADD", "SUBTRACT"):
                decision_count += 1

        para_specs.append(ParagraphSpec(
            name=p["name"],
            performs=[perf.get("target_paragraph", "") for perf in p.get("performs", [])],
            calls=[c.get("target_program", "") for c in p.get("calls", [])],
            cics_ops=[f"{op.get('operation', '')}({op.get('map_name', '') or op.get('dataset', '') or ''})" for op in p.get("cics_ops", [])],
            data_flows_in=sorted(flows_in),
            data_flows_out=sorted(flows_out),
            decision_indicators=decision_count,
            is_entry_point=p["name"] in entry_paragraphs,
        ))

    # Copybook contracts
    contracts = []
    for cb_name in enrichment["copybooks"]:
        sharing = [p for p in graph.copybook_users(cb_name) if p != program_id]
        contracts.append(DataContract(
            copybook=cb_name,
            field_count=0,
            key_fields=[],
            shared_with=sharing[:5],
        ))

    # Effort
    dead = graph.dead_code_analysis()
    from effort_estimator import estimate_estate
    estate = estimate_estate(graph.readiness_ranking(), dead)
    effort_map = {e.program: e for e in estate["estimates"]}
    eff = effort_map.get(program_id)

    wave = ""
    for w in estate["waves"]:
        if program_id in w["programs"]:
            wave = w["name"]
            break

    # Reimplementation notes
    notes = []
    code_lines = meta.get("code_lines", 0)
    cc_val = cc_result.cyclomatic if cc_result else 0
    if cc_val > 25:
        notes.append(f"High cyclomatic complexity ({cc_val}) — consider decomposing into smaller functions")
    if code_lines > 1000:
        notes.append(f"Large program ({code_lines} LOC) — may benefit from splitting into modules")
    if has_cics:
        notes.append("CICS program — map BMS screens to API endpoints or web forms")
    if has_file_io:
        notes.append("File I/O present — map VSAM/sequential to modern database or file streams")
    if len(enrichment["callers"]) > 5:
        notes.append(f"High fan-in ({len(enrichment['callers'])} callers) — changes here have wide blast radius")
    if not enrichment["callers"] and not enrichment["callees"]:
        notes.append("Isolated program — good candidate for independent reimplementation")

    display_source = source_file
    if source_path:
        try:
            display_source = str(source_path.resolve().relative_to(Path(codebase_dir).resolve()))
        except ValueError:
            display_source = source_path.name

    return ProgramSpec(
        program=program_id,
        program_type="CICS Online" if has_cics else "Batch",
        source_file=display_source or source_file,
        total_lines=meta.get("total_lines", 0),
        code_lines=code_lines,
        paragraph_count=meta.get("paragraph_count", 0),
        cyclomatic_complexity=cc_val,
        max_nesting=cc_result.max_nesting if cc_result else 0,
        complexity_grade=complexity_grade(cc_val, code_lines) if cc_result else "UNKNOWN",
        callers=enrichment["callers"],
        callees=enrichment["callees"],
        copybooks=enrichment["copybooks"],
        files_accessed=files_accessed,
        readiness_score=readiness["composite"],
        effort_days=eff.effort_days if eff else 0,
        risk_level=eff.risk_level if eff else "UNKNOWN",
        paragraphs=para_specs,
        data_contracts=contracts,
        cics_operations=cics_ops_list,
        data_flow_summary=flow_summary,
        decision_count=cc_val,
        computation_count=_count_computations(paragraphs_raw),
        validation_fields=_extract_validation_fields([], paragraphs_raw),
        modern_pattern=_infer_modern_pattern(has_cics, has_file_io, has_db, cics_ops_list),
        migration_wave=wave,
        notes=notes,
        entry_paragraphs=entry_paragraphs,
        exit_points=exit_points,
        perform_graph=perform_graph,
    )


def render_spec_markdown(spec: ProgramSpec) -> str:
    """Render a ProgramSpec as a structured markdown document."""
    lines = []
    lines.append(f"# Behavioral Specification: {spec.program}")
    lines.append("")
    lines.append(f"**Type**: {spec.program_type}  ")
    lines.append(f"**Source**: `{spec.source_file}`  ")
    lines.append(f"**Lines**: {spec.code_lines} code / {spec.total_lines} total  ")
    lines.append(f"**Readiness**: {spec.readiness_score}/100  ")
    lines.append(f"**Effort**: {spec.effort_days} person-days ({spec.risk_level} risk)  ")
    lines.append(f"**Wave**: {spec.migration_wave}  ")
    lines.append("")

    # Complexity
    lines.append("## Complexity")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Cyclomatic complexity | {spec.cyclomatic_complexity} |")
    lines.append(f"| Max nesting depth | {spec.max_nesting} |")
    lines.append(f"| Grade | {spec.complexity_grade} |")
    lines.append(f"| Decision points | {spec.decision_count} |")
    lines.append(f"| Computations | {spec.computation_count} |")
    lines.append("")

    # Dependencies
    lines.append("## Dependencies")
    lines.append("")
    if spec.callers:
        lines.append(f"**Called by** ({len(spec.callers)}): {', '.join(spec.callers)}")
    else:
        lines.append("**Called by**: none (entry point or standalone)")
    lines.append("")
    if spec.callees:
        lines.append(f"**Calls** ({len(spec.callees)}): {', '.join(spec.callees)}")
    else:
        lines.append("**Calls**: none (leaf program)")
    lines.append("")
    if spec.copybooks:
        lines.append(f"**Copybooks** ({len(spec.copybooks)}): {', '.join(spec.copybooks)}")
    else:
        lines.append("**Copybooks**: none")
    lines.append("")
    if spec.files_accessed:
        lines.append(f"**Files/Datasets**: {', '.join(spec.files_accessed)}")
        lines.append("")

    # Data Flow
    lines.append("## Data Flow")
    lines.append("")
    fs = spec.data_flow_summary
    lines.append(f"- Total assignments: {fs.get('total_flows', 0)}")
    lines.append(f"- Fields written: {len(fs.get('fields_written', []))}")
    lines.append(f"- Fields read: {len(fs.get('fields_read', []))}")
    if spec.validation_fields:
        lines.append(f"- Validation/status fields: {', '.join(spec.validation_fields)}")
    lines.append("")

    # CICS
    if spec.cics_operations:
        lines.append("## CICS Operations")
        lines.append("")
        for op in spec.cics_operations:
            lines.append(f"- `{op}`")
        lines.append("")

    # Control Flow
    lines.append("## Control Flow")
    lines.append("")
    if spec.entry_paragraphs:
        lines.append(f"**Entry points**: {', '.join(spec.entry_paragraphs)}")
    if spec.exit_points:
        lines.append(f"**Exit points**: {', '.join(spec.exit_points)}")
    lines.append("")
    lines.append(f"**Paragraphs** ({spec.paragraph_count}):")
    lines.append("")
    for p in spec.paragraphs:
        marker = " **(entry)**" if p.is_entry_point else ""
        lines.append(f"### `{p.name}`{marker}")
        parts = []
        if p.performs:
            parts.append(f"PERFORMs: {', '.join(p.performs)}")
        if p.calls:
            parts.append(f"CALLs: {', '.join(p.calls)}")
        if p.cics_ops:
            parts.append(f"CICS: {', '.join(p.cics_ops)}")
        if p.data_flows_out:
            out_sample = p.data_flows_out[:8]
            suffix = f" +{len(p.data_flows_out) - 8} more" if len(p.data_flows_out) > 8 else ""
            parts.append(f"Writes: {', '.join(out_sample)}{suffix}")
        if p.data_flows_in:
            in_sample = p.data_flows_in[:8]
            suffix = f" +{len(p.data_flows_in) - 8} more" if len(p.data_flows_in) > 8 else ""
            parts.append(f"Reads: {', '.join(in_sample)}{suffix}")
        if parts:
            for part in parts:
                lines.append(f"- {part}")
        else:
            lines.append("- (no significant operations)")
        lines.append("")

    # Data Contracts
    if spec.data_contracts:
        lines.append("## Data Contracts (Copybooks)")
        lines.append("")
        for c in spec.data_contracts:
            shared = f" — shared with: {', '.join(c.shared_with)}" if c.shared_with else ""
            lines.append(f"- **{c.copybook}**{shared}")
        lines.append("")

    # Reimplementation guidance
    lines.append("## Reimplementation Guidance")
    lines.append("")
    lines.append(f"**Suggested pattern**: {spec.modern_pattern}")
    lines.append("")
    if spec.notes:
        for note in spec.notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines)


def generate_all_specs(codebase_dir: str) -> dict:
    """Generate behavioral specs for all programs in a codebase.

    Returns: {program_id: ProgramSpec, ...} and writes markdown files.
    """
    analysis_dir = Path(codebase_dir) / "_analysis"
    graph = GraphIndex(str(analysis_dir))
    program_data = _load_program_data(analysis_dir)

    specs_dir = analysis_dir / "specs"
    specs_dir.mkdir(exist_ok=True)

    results = {}
    for pgm in sorted(graph.program_names()):
        spec = generate_program_spec(pgm, graph, program_data, codebase_dir)
        if spec:
            results[pgm] = spec
            md = render_spec_markdown(spec)
            spec_path = specs_dir / f"{pgm}.md"
            spec_path.write_text(md, encoding="utf-8")

    # Write an index file
    index_lines = [f"# Behavioral Specifications — {Path(codebase_dir).name}", ""]
    index_lines.append(f"Generated specs for **{len(results)}** programs.", )
    index_lines.append("")
    index_lines.append("| Program | Type | LOC | Complexity | Readiness | Effort | Wave |")
    index_lines.append("|---------|------|-----|-----------|-----------|--------|------|")
    for pgm in sorted(results.keys()):
        s = results[pgm]
        index_lines.append(
            f"| [{s.program}]({s.program}.md) | {s.program_type} | {s.code_lines} | "
            f"{s.cyclomatic_complexity} ({s.complexity_grade}) | {s.readiness_score} | "
            f"{s.effort_days}d | {s.migration_wave} |"
        )
    index_lines.append("")

    (specs_dir / "INDEX.md").write_text("\n".join(index_lines), encoding="utf-8")

    return results
