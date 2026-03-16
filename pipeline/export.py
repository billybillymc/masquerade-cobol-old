"""
Export analysis data to structured formats (CSV, JSON) for integration
with external tools like JIRA, Excel, project management systems.
"""

import csv
import json
import sys
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graph_context import GraphIndex
from effort_estimator import estimate_estate, estimate_program
from complexity import compute_all, complexity_grade


def export_program_inventory(graph: GraphIndex, codebase_dir: str) -> list[dict]:
    """Export a flat program inventory with all metrics."""
    readiness = graph.readiness_ranking()
    complexity = {r.program: r for r in compute_all(codebase_dir)}
    estate = estimate_estate(readiness, graph.dead_code_analysis())
    effort_map = {e.program: e for e in estate["estimates"]}

    rows = []
    for r in readiness:
        pgm = r["program"]
        d = r["details"]
        cc = complexity.get(pgm)
        eff = effort_map.get(pgm)

        rows.append({
            "program": pgm,
            "type": "CICS" if d["has_cics"] else "Batch",
            "code_lines": d["code_lines"],
            "total_lines": d["total_lines"],
            "paragraphs": d["paragraph_count"],
            "callers": d["callers"],
            "callees": d["callees"],
            "copybooks": d["copybooks"],
            "readiness_score": round(r["composite"], 1),
            "isolation": round(r["isolation"], 1),
            "simplicity": round(r["simplicity"], 1),
            "dependency_clarity": round(r["dependency_clarity"], 1),
            "testability": round(r["testability"], 1),
            "cyclomatic_complexity": cc.cyclomatic if cc else None,
            "max_nesting": cc.max_nesting if cc else None,
            "complexity_grade": complexity_grade(cc.cyclomatic, d["code_lines"]) if cc else None,
            "effort_days": eff.effort_days if eff else None,
            "risk_level": eff.risk_level if eff else None,
            "migration_wave": _get_wave(pgm, estate["waves"]),
        })

    return rows


def _get_wave(program: str, waves: list[dict]) -> str:
    for w in waves:
        if program in w["programs"]:
            return w["name"]
    return ""


def export_csv(rows: list[dict], output_path: str) -> str:
    """Export program inventory to CSV."""
    if not rows:
        return output_path

    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def export_json(rows: list[dict], graph: GraphIndex, codebase_dir: str, output_path: str) -> str:
    """Export comprehensive analysis as JSON."""
    summary = graph.summary()
    dead = graph.dead_code_analysis()
    readiness = graph.readiness_ranking()
    estate = estimate_estate(readiness, dead)

    output = {
        "meta": {
            "codebase": Path(codebase_dir).name,
            "generator": "Masquerade COBOL Intelligence Engine",
        },
        "summary": {
            "total_programs": summary["total_programs"],
            "total_loc": summary["total_loc"],
            "total_code_lines": summary["total_code_lines"],
            "cics_programs": len(summary["cics_programs"]),
            "batch_programs": len(summary["batch_programs"]),
            "total_copybooks": summary["total_copybooks"],
            "total_edges": summary["total_edges"],
        },
        "effort_estimate": estate["summary"],
        "migration_waves": estate["waves"],
        "programs": rows,
        "dead_code": {
            "unreachable_paragraphs": dead["summary"]["unreachable_count"],
            "orphan_programs": [o["program"] for o in dead["orphan_programs"]],
            "unused_copybooks": dead.get("unused_copybooks", []),
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    return output_path


def export_all(codebase_dir: str) -> dict:
    """Export CSV and JSON for a codebase. Returns paths to generated files."""
    analysis_dir = Path(codebase_dir) / "_analysis"
    graph = GraphIndex(str(analysis_dir))

    rows = export_program_inventory(graph, codebase_dir)

    csv_path = str(analysis_dir / "programs_export.csv")
    json_path = str(analysis_dir / "analysis_export.json")

    export_csv(rows, csv_path)
    export_json(rows, graph, codebase_dir, json_path)

    return {
        "csv": csv_path,
        "json": json_path,
        "programs": len(rows),
    }
