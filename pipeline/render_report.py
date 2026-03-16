"""
Generates a comprehensive HTML analysis report for a COBOL codebase.
Combines structural analysis, readiness scoring, dead code detection,
file contracts, and data flow stats into a single shareable document.

Usage:
    python render_report.py <codebase_dir>
"""

import json
import sys
import time
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graph_context import GraphIndex, DataFlowIndex
from copybook_dict import CopybookDictionary
from jcl_parser import JclIndex
from bms_parser import ScreenFlowIndex
from effort_estimator import estimate_estate
from complexity import compute_all, complexity_grade


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _grade_color(score):
    if score >= 70:
        return "#3fb950"
    elif score >= 45:
        return "#d29922"
    return "#f85149"


def _grade_label(score):
    if score >= 70:
        return "GOOD"
    elif score >= 45:
        return "MODERATE"
    return "COMPLEX"


def _bar_html(value, max_val=100, width=120, color="#58a6ff"):
    pct = min(value / max_val * 100, 100) if max_val > 0 else 0
    return f'<div style="background:#21262d;border-radius:3px;width:{width}px;height:8px;display:inline-block;vertical-align:middle"><div style="background:{color};border-radius:3px;width:{pct}%;height:100%"></div></div>'


def generate_report(codebase_dir: str) -> str:
    codebase_path = Path(codebase_dir)
    analysis_dir = codebase_path / "_analysis"
    codebase_name = codebase_path.name

    graph = GraphIndex(str(analysis_dir))
    summary = graph.summary()
    readiness = graph.readiness_ranking()
    dead = graph.dead_code_analysis()

    dfi = None
    try:
        dfi = DataFlowIndex(str(analysis_dir))
    except FileNotFoundError:
        pass

    cbd = CopybookDictionary(str(codebase_path))
    jcl = JclIndex(str(codebase_path))
    sfi = ScreenFlowIndex(str(codebase_path))

    timestamp = time.strftime("%Y-%m-%d %H:%M")

    sections = []

    # --- Executive Summary ---
    s = summary
    sections.append(f"""
    <section id="summary">
      <h2>Executive Summary</h2>
      <div class="grid-3">
        <div class="card">
          <div class="card-value">{s['total_programs']}</div>
          <div class="card-label">Programs</div>
          <div class="card-detail">{len(s['cics_programs'])} CICS &middot; {len(s['batch_programs'])} Batch</div>
        </div>
        <div class="card">
          <div class="card-value">{s['total_loc']:,}</div>
          <div class="card-label">Total Lines</div>
          <div class="card-detail">{s['total_code_lines']:,} code &middot; {s['total_comment_lines']:,} comments</div>
        </div>
        <div class="card">
          <div class="card-value">{s['total_copybooks']}</div>
          <div class="card-label">Copybooks</div>
          <div class="card-detail">{len(s['shared_copybooks'])} shared across programs</div>
        </div>
        <div class="card">
          <div class="card-value">{s['total_edges']}</div>
          <div class="card-label">Dependencies</div>
          <div class="card-detail">{' &middot; '.join(f'{v} {k}' for k, v in sorted(s['edge_types'].items(), key=lambda x: -x[1])[:4])}</div>
        </div>
        <div class="card">
          <div class="card-value">{len(s['components'])}</div>
          <div class="card-label">Components</div>
          <div class="card-detail">Largest: {len(s['components'][0]) if s['components'] else 0} programs</div>
        </div>
        <div class="card">
          <div class="card-value">{s['total_paragraphs']}</div>
          <div class="card-label">Paragraphs</div>
          <div class="card-detail">{dead['summary']['unreachable_count']} potentially dead</div>
        </div>
      </div>
    </section>""")

    # --- Readiness Ranking ---
    good = sum(1 for r in readiness if r['composite'] >= 70)
    moderate = sum(1 for r in readiness if 45 <= r['composite'] < 70)
    complex_ = sum(1 for r in readiness if r['composite'] < 45)

    rows = []
    for r in readiness:
        d = r['details']
        color = _grade_color(r['composite'])
        grade = _grade_label(r['composite'])
        pgm_type = "CICS" if d['has_cics'] else "Batch"
        type_color = "#58a6ff" if d['has_cics'] else "#3fb950"
        rows.append(f"""<tr>
          <td><strong>{_esc(r['program'])}</strong></td>
          <td style="color:{color};font-weight:600">{r['composite']:.0f}</td>
          <td>{_bar_html(r['composite'], color=color)}</td>
          <td>{r['isolation']:.0f}</td>
          <td>{r['simplicity']:.0f}</td>
          <td>{r['dependency_clarity']:.0f}</td>
          <td>{r['testability']:.0f}</td>
          <td>{d['code_lines']}</td>
          <td><span style="color:{type_color}">{pgm_type}</span></td>
          <td style="color:{color}">{grade}</td>
        </tr>""")

    sections.append(f"""
    <section id="readiness">
      <h2>Reimplementation Readiness</h2>
      <div class="summary-bar">
        <span style="color:#3fb950">{good} Good</span> &middot;
        <span style="color:#d29922">{moderate} Moderate</span> &middot;
        <span style="color:#f85149">{complex_} Complex</span> &middot;
        {len(readiness)} total programs
      </div>
      <table>
        <thead><tr>
          <th>Program</th><th>Score</th><th></th><th>Iso</th><th>Sim</th><th>Dep</th><th>Test</th><th>LOC</th><th>Type</th><th>Grade</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>""")

    # --- Complexity Metrics ---
    complexity_results = compute_all(str(codebase_path))
    if complexity_results:
        complexity_results.sort(key=lambda r: -r.cyclomatic)
        total_cc = sum(r.cyclomatic for r in complexity_results)
        avg_cc = total_cc / len(complexity_results) if complexity_results else 0
        low_c = sum(1 for r in complexity_results if complexity_grade(r.cyclomatic, 500) == "LOW")
        mod_c = sum(1 for r in complexity_results if complexity_grade(r.cyclomatic, 500) == "MODERATE")
        high_c = sum(1 for r in complexity_results if complexity_grade(r.cyclomatic, 500) in ("HIGH", "VERY HIGH"))

        cc_rows = []
        for r in complexity_results:
            grade = complexity_grade(r.cyclomatic, 500)
            gc = "#3fb950" if grade == "LOW" else ("#d29922" if grade == "MODERATE" else "#f85149")
            cc_rows.append(f"""<tr>
              <td><strong>{_esc(r.program)}</strong></td>
              <td>{r.cyclomatic}</td>
              <td>{_bar_html(r.cyclomatic, max_val=max(cr.cyclomatic for cr in complexity_results), color=gc)}</td>
              <td>{r.max_nesting}</td>
              <td>{r.decision_points}</td>
              <td>{r.paragraphs}</td>
              <td style="color:{gc};font-weight:600">{grade}</td>
            </tr>""")

        sections.append(f"""
        <section id="complexity">
          <h2>Cyclomatic Complexity</h2>
          <div class="grid-3">
            <div class="card"><div class="card-value">{avg_cc:.1f}</div><div class="card-label">Average Complexity</div><div class="card-detail">{total_cc} total across {len(complexity_results)} programs</div></div>
            <div class="card"><div class="card-value" style="color:#3fb950">{low_c}</div><div class="card-label">Low Complexity</div></div>
            <div class="card"><div class="card-value" style="color:#f85149">{high_c}</div><div class="card-label">High/Very High</div><div class="card-detail">{mod_c} moderate</div></div>
          </div>
          <table><thead><tr><th>Program</th><th>CC</th><th></th><th>Nest</th><th>Decisions</th><th>Paras</th><th>Grade</th></tr></thead>
          <tbody>{''.join(cc_rows)}</tbody></table>
        </section>""")

    # --- Migration Effort ---
    estate = estimate_estate(readiness, dead)
    es = estate["summary"]

    wave_rows = []
    for w in estate["waves"]:
        if w["program_count"] == 0:
            continue
        pgm_list = ', '.join(w["programs"][:8])
        if w["program_count"] > 8:
            pgm_list += f" +{w['program_count'] - 8}"
        wave_rows.append(f"""<tr>
          <td><strong>{_esc(w['name'])}</strong></td>
          <td>{w['program_count']}</td>
          <td>{w['effort_days']:.0f}</td>
          <td class="dim">{_esc(pgm_list)}</td>
        </tr>""")

    est_rows = []
    for est in sorted(estate["estimates"], key=lambda e: -e.effort_days):
        risk_color = "#3fb950" if est.risk_level == "LOW" else ("#d29922" if est.risk_level == "MEDIUM" else "#f85149")
        notes = ', '.join(est.notes) if est.notes else ""
        est_rows.append(f"""<tr>
          <td><strong>{_esc(est.program)}</strong></td>
          <td>{est.code_lines}</td>
          <td>{est.category}</td>
          <td>{est.readiness_score:.0f}</td>
          <td><strong>{est.effort_days:.1f}</strong></td>
          <td style="color:{risk_color};font-weight:600">{est.risk_level}</td>
          <td class="dim">{_esc(notes)}</td>
        </tr>""")

    sections.append(f"""
    <section id="effort">
      <h2>Migration Effort Estimate</h2>
      <div class="grid-3">
        <div class="card"><div class="card-value">{es['total_effort_days']:.0f}</div><div class="card-label">Person-Days Total</div><div class="card-detail">{es['total_effort_weeks']:.1f} weeks / {es['total_effort_months']:.1f} months</div></div>
        <div class="card"><div class="card-value">{es['batch_effort_days']:.0f} / {es['cics_effort_days']:.0f}</div><div class="card-label">Batch / CICS Days</div></div>
        <div class="card"><div class="card-value" style="color:#3fb950">{es['quick_win_count']}</div><div class="card-label">Quick Wins</div><div class="card-detail">{es['low_risk_count']} low risk, {es['high_risk_count']} high risk</div></div>
      </div>
      <p class="dim">Covers analysis + design + coding + unit testing. Does not include integration testing, UAT, data migration, or deployment.</p>
      <h3>Migration Waves</h3>
      <table><thead><tr><th>Wave</th><th>Programs</th><th>Days</th><th>Programs</th></tr></thead>
      <tbody>{''.join(wave_rows)}</tbody></table>
      <h3>Per-Program Breakdown</h3>
      <table><thead><tr><th>Program</th><th>LOC</th><th>Type</th><th>Ready</th><th>Days</th><th>Risk</th><th>Notes</th></tr></thead>
      <tbody>{''.join(est_rows)}</tbody></table>
    </section>""")

    # --- Dead Code ---
    ds = dead['summary']
    dead_pct = ds['unreachable_count'] / ds['total_paragraphs'] * 100 if ds['total_paragraphs'] else 0

    dead_rows = []
    by_pgm = defaultdict(list)
    for p in dead['unreachable_paragraphs']:
        by_pgm[p['program']].append(p)

    for pgm, paras in sorted(by_pgm.items(), key=lambda x: -len(x[1])):
        para_names = ', '.join(p['paragraph'] for p in paras[:8])
        if len(paras) > 8:
            para_names += f" +{len(paras) - 8} more"
        dead_rows.append(f"""<tr>
          <td><strong>{_esc(pgm)}</strong></td>
          <td>{len(paras)}</td>
          <td class="dim">{_esc(para_names)}</td>
        </tr>""")

    orphan_rows = []
    for o in sorted(dead['orphan_programs'], key=lambda x: -x['code_lines']):
        pgm_type = "CICS" if o['has_cics'] else "Batch"
        callees = ', '.join(o['callees'][:3]) if o['callees'] else "(leaf)"
        orphan_rows.append(f"""<tr>
          <td><strong>{_esc(o['program'])}</strong></td>
          <td>{o['code_lines']}</td>
          <td>{pgm_type}</td>
          <td class="dim">{_esc(callees)}</td>
        </tr>""")

    sections.append(f"""
    <section id="dead-code">
      <h2>Dead Code Analysis</h2>
      <div class="grid-3">
        <div class="card"><div class="card-value" style="color:#f85149">{ds['unreachable_count']}</div><div class="card-label">Unreachable Paragraphs</div><div class="card-detail">{dead_pct:.1f}% of {ds['total_paragraphs']}</div></div>
        <div class="card"><div class="card-value">{ds['orphan_count']}</div><div class="card-label">Orphan Programs</div><div class="card-detail">No callers found</div></div>
        <div class="card"><div class="card-value">{ds['unused_count']}</div><div class="card-label">Unused Copybooks</div><div class="card-detail">Not COPY'd by any program</div></div>
      </div>
      {"<h3>Unreachable Paragraphs by Program</h3><table><thead><tr><th>Program</th><th>Count</th><th>Paragraphs</th></tr></thead><tbody>" + ''.join(dead_rows) + "</tbody></table>" if dead_rows else ""}
      {"<h3>Orphan Programs (no callers)</h3><p class='dim'>May be JCL/CICS entry points or truly unused.</p><table><thead><tr><th>Program</th><th>LOC</th><th>Type</th><th>Callees</th></tr></thead><tbody>" + ''.join(orphan_rows) + "</tbody></table>" if orphan_rows else ""}
    </section>""")

    # --- Screen Flow ---
    if sfi.mapsets:
        sfi_sum = sfi.summary()
        flow = sfi.screen_flow()

        screen_rows = []
        for ms_name in sorted(sfi.mapsets.keys()):
            ms = sfi.mapsets[ms_name]
            for m in ms.maps:
                programs = sfi._mapset_programs.get(ms_name, [])
                pgm_list = ', '.join(set(programs)) if programs else "(unlinked)"
                n_inputs = len(m.input_fields)
                n_outputs = len(m.output_fields)
                desc = _esc(ms.description[:60]) if ms.description else ""
                screen_rows.append(f"""<tr>
                  <td><strong>{_esc(ms_name)}</strong></td>
                  <td>{n_inputs}</td>
                  <td>{n_outputs}</td>
                  <td class="dim">{pgm_list}</td>
                  <td class="dim">{desc}</td>
                </tr>""")

        nav_rows = []
        for e in flow["edges"]:
            nav_rows.append(f"""<tr>
              <td><strong>{_esc(e['from'])}</strong></td>
              <td>&rarr;</td>
              <td><strong>{_esc(e['to'])}</strong></td>
              <td class="dim">{e['type']}</td>
            </tr>""")

        sections.append(f"""
        <section id="screens">
          <h2>CICS Screen Flow</h2>
          <div class="grid-3">
            <div class="card"><div class="card-value">{sfi_sum['total_mapsets']}</div><div class="card-label">Screens (Mapsets)</div></div>
            <div class="card"><div class="card-value">{sfi_sum['total_input_fields']}</div><div class="card-label">Input Fields</div></div>
            <div class="card"><div class="card-value">{sfi_sum['screen_transitions']}</div><div class="card-label">Navigation Paths</div></div>
          </div>
          <h3>Screen Inventory</h3>
          <table><thead><tr><th>Mapset</th><th>Inputs</th><th>Outputs</th><th>Program(s)</th><th>Description</th></tr></thead>
          <tbody>{''.join(screen_rows)}</tbody></table>
          {"<h3>Screen Navigation</h3><table><thead><tr><th>From</th><th></th><th>To</th><th>Type</th></tr></thead><tbody>" + ''.join(nav_rows) + "</tbody></table>" if nav_rows else ""}
        </section>""")

    # --- File Contracts ---
    file_programs = defaultdict(list)
    for edge in graph.edges:
        if edge["type"] in ("READS_FILE", "CICS_IO") and edge["target"].startswith("FILE:"):
            file_name = graph.nodes.get(edge["target"], {}).get("name", edge["target"])
            src_name = graph.nodes.get(edge["source"], {}).get("name", "")
            if not src_name or "::PARA:" in edge["source"]:
                continue
            evidence = edge.get("evidence", [{}])
            op = evidence[0].get("operation", "FILE_IO") if evidence else "FILE_IO"
            file_programs[file_name].append({"program": src_name, "operation": op})

    file_rows = []
    for fname in sorted(file_programs.keys()):
        progs = file_programs[fname]
        unique = {}
        for p in progs:
            unique.setdefault(p["program"], set()).add(p["operation"])
        shared = len(unique) > 1
        prog_list = ', '.join(f'{pgm} ({",".join(ops)})' for pgm, ops in sorted(unique.items()))
        marker = '<span style="color:#d29922;font-weight:600"> SHARED</span>' if shared else ''
        file_rows.append(f"""<tr>
          <td><strong>{_esc(fname)}</strong>{marker}</td>
          <td>{len(unique)}</td>
          <td class="dim">{_esc(prog_list)}</td>
        </tr>""")

    if file_rows:
        sections.append(f"""
        <section id="files">
          <h2>File &amp; Dataset Contracts</h2>
          <table><thead><tr><th>File/Dataset</th><th>Programs</th><th>Accessors</th></tr></thead>
          <tbody>{''.join(file_rows)}</tbody></table>
        </section>""")

    # --- Shared Copybooks ---
    cb_rows = []
    for cb, user_count, users in s['shared_copybooks'][:15]:
        user_list = ', '.join(users[:6])
        if user_count > 6:
            user_list += f" +{user_count - 6}"
        cb_rows.append(f"""<tr>
          <td><strong>{_esc(cb)}</strong></td>
          <td>{user_count}</td>
          <td>{_bar_html(user_count, max_val=max(u for _, u, _ in s['shared_copybooks'][:15]))}</td>
          <td class="dim">{_esc(user_list)}</td>
        </tr>""")

    if cb_rows:
        sections.append(f"""
        <section id="copybooks">
          <h2>Shared Copybooks (Coupling Indicators)</h2>
          <table><thead><tr><th>Copybook</th><th>Users</th><th></th><th>Programs</th></tr></thead>
          <tbody>{''.join(cb_rows)}</tbody></table>
        </section>""")

    # --- Hotspots ---
    hub_rows = []
    for name, score in s['hub_programs']:
        callers_n = len(graph.callers(name))
        callees_n = len(graph.callees(name))
        cbs_n = len(graph.copybooks_of(name))
        hub_rows.append(f"""<tr>
          <td><strong>{_esc(name)}</strong></td>
          <td>{score:.0f}</td>
          <td>{_bar_html(score, max_val=s['hub_programs'][0][1] if s['hub_programs'] else 1, color='#f85149')}</td>
          <td>{callers_n}</td><td>{callees_n}</td><td>{cbs_n}</td>
        </tr>""")

    if hub_rows:
        sections.append(f"""
        <section id="hotspots">
          <h2>Hotspot Programs (Change Risk)</h2>
          <table><thead><tr><th>Program</th><th>Score</th><th></th><th>Callers</th><th>Callees</th><th>Copybooks</th></tr></thead>
          <tbody>{''.join(hub_rows)}</tbody></table>
        </section>""")

    # --- Data Flow Stats ---
    if dfi:
        flow_counts = []
        for pgm in graph.program_names():
            node_id = f"PGM:{pgm}"
            if not graph.nodes.get(node_id, {}).get("source_file"):
                continue
            fs = dfi.program_flow_summary(pgm)
            if fs['total_flows'] > 0:
                flow_counts.append((pgm, fs['total_flows'], len(fs['fields_written']), len(fs['fields_read'])))

        flow_counts.sort(key=lambda x: -x[1])
        flow_rows = []
        for pgm, flows, writes, reads in flow_counts[:20]:
            flow_rows.append(f"""<tr>
              <td><strong>{_esc(pgm)}</strong></td>
              <td>{flows}</td>
              <td>{writes}</td>
              <td>{reads}</td>
            </tr>""")

        total_flows = sum(f[1] for f in flow_counts)
        sections.append(f"""
        <section id="dataflow">
          <h2>Data Flow Summary</h2>
          <p class="dim">{total_flows} total data assignments across {len(flow_counts)} programs</p>
          <table><thead><tr><th>Program</th><th>Flows</th><th>Fields Written</th><th>Fields Read</th></tr></thead>
          <tbody>{''.join(flow_rows)}</tbody></table>
        </section>""")

    # --- Batch Job Flow ---
    if jcl.jobs:
        jcl_sum = jcl.summary()
        job_rows = []
        for jname in sorted(jcl.jobs.keys()):
            job = jcl.jobs[jname]
            programs = [s.program for s in job.steps]
            cobol_pgms = [p for p in programs if p not in {"SORT", "IDCAMS", "IEFBR14", "IEBGENER", "IEBCOPY", "DFSRRC00", "IKJEFT01", "IRXJCL", "DSNUTILB", "DSNUPROC", "DFHCSDUP"}]
            desc = _esc(job.description[:80]) if job.description else ""
            pgm_list = ', '.join(cobol_pgms[:5])
            if len(cobol_pgms) > 5:
                pgm_list += f" +{len(cobol_pgms) - 5}"
            job_rows.append(f"""<tr>
              <td><strong>{_esc(jname)}</strong></td>
              <td>{len(job.steps)}</td>
              <td>{len(cobol_pgms)}</td>
              <td class="dim">{pgm_list or '(utilities only)'}</td>
              <td class="dim">{desc}</td>
            </tr>""")

        flows = jcl.dataset_flow()
        flow_rows = []
        for f in flows:
            ds_short = f["dataset"].split(".")[-1] if "." in f["dataset"] else f["dataset"]
            flow_rows.append(f"""<tr>
              <td><strong>{_esc(f['producer'])}</strong></td>
              <td>&rarr;</td>
              <td><strong>{_esc(f['consumer'])}</strong></td>
              <td class="dim">{_esc(ds_short)}</td>
            </tr>""")

        layers = jcl.execution_order()
        layer_html = ""
        for i, layer in enumerate(layers):
            jobs_str = ', '.join(layer[:10])
            if len(layer) > 10:
                jobs_str += f" +{len(layer) - 10}"
            layer_html += f"<p><strong>Layer {i}:</strong> {_esc(jobs_str)}</p>"

        sections.append(f"""
        <section id="jobs">
          <h2>Batch Job Flow</h2>
          <div class="grid-3">
            <div class="card"><div class="card-value">{jcl_sum['total_jobs']}</div><div class="card-label">JCL Jobs</div></div>
            <div class="card"><div class="card-value">{jcl_sum['total_steps']}</div><div class="card-label">Execution Steps</div></div>
            <div class="card"><div class="card-value">{jcl_sum['total_datasets']}</div><div class="card-label">Datasets Referenced</div></div>
          </div>
          <table><thead><tr><th>Job</th><th>Steps</th><th>COBOL Pgms</th><th>Programs</th><th>Description</th></tr></thead>
          <tbody>{''.join(job_rows)}</tbody></table>
          {"<h3>Cross-Job Data Flows</h3><table><thead><tr><th>Producer</th><th></th><th>Consumer</th><th>Dataset</th></tr></thead><tbody>" + ''.join(flow_rows) + "</tbody></table>" if flow_rows else ""}
          {"<h3>Execution Order</h3>" + layer_html if layers else ""}
        </section>""")

    # --- Copybook Dictionary ---
    if cbd.records:
        cbd_sum = cbd.summary()
        cbd_rows = []
        for cb_name in sorted(cbd.records.keys()):
            rec = cbd.records[cb_name]
            top_fields = [f for f in rec.fields if f.level != 88 and f.level <= 5][:5]
            field_preview = ', '.join(f.name for f in top_fields)
            if rec.field_count > 5:
                field_preview += f" +{rec.field_count - 5}"
            cbd_rows.append(f"""<tr>
              <td><strong>{_esc(cb_name)}</strong></td>
              <td>{rec.total_lines}</td>
              <td>{rec.field_count}</td>
              <td>{rec.condition_count}</td>
              <td class="dim">{_esc(field_preview)}</td>
            </tr>""")

        sections.append(f"""
        <section id="dictionary">
          <h2>Copybook Data Dictionary</h2>
          <div class="grid-3">
            <div class="card"><div class="card-value">{cbd_sum['total_copybooks']}</div><div class="card-label">Copybooks Parsed</div></div>
            <div class="card"><div class="card-value">{cbd_sum['total_fields']:,}</div><div class="card-label">Total Fields</div></div>
            <div class="card"><div class="card-value">{cbd_sum['total_conditions']}</div><div class="card-label">88-Level Conditions</div></div>
          </div>
          <table><thead><tr><th>Copybook</th><th>Lines</th><th>Fields</th><th>88s</th><th>Key Fields</th></tr></thead>
          <tbody>{''.join(cbd_rows)}</tbody></table>
        </section>""")

    # --- Unresolved References ---
    unresolved_cbs = s.get('unresolved_copybooks', []) if isinstance(s, dict) else summary.get('unresolved_copybooks', [])
    unresolved_calls = s.get('unresolved_calls', []) if isinstance(s, dict) else summary.get('unresolved_calls', [])

    # Pull from stats
    unresolved_cbs = graph.stats.get('unresolved_copybooks', [])
    unresolved_calls = graph.stats.get('unresolved_calls', [])

    if unresolved_cbs or unresolved_calls:
        sections.append(f"""
        <section id="unresolved">
          <h2>Unresolved External References</h2>
          {"<h3>Copybooks (" + str(len(unresolved_cbs)) + ")</h3><p class='dim'>" + ', '.join(_esc(c) for c in unresolved_cbs) + "</p>" if unresolved_cbs else ""}
          {"<h3>Call Targets (" + str(len(unresolved_calls)) + ")</h3><p class='dim'>" + ', '.join(_esc(c) for c in unresolved_calls) + "</p>" if unresolved_calls else ""}
        </section>""")

    # --- Build navigation ---
    nav_items = [
        ("summary", "Summary"),
        ("readiness", "Readiness"),
        ("complexity", "Complexity"),
        ("effort", "Effort"),
        ("dead-code", "Dead Code"),
    ]
    if sfi.mapsets:
        nav_items.append(("screens", "Screens"))
    if file_rows:
        nav_items.append(("files", "Files"))
    if cb_rows:
        nav_items.append(("copybooks", "Copybooks"))
    if hub_rows:
        nav_items.append(("hotspots", "Hotspots"))
    if dfi:
        nav_items.append(("dataflow", "Data Flow"))
    if jcl.jobs:
        nav_items.append(("jobs", "Jobs"))
    if cbd.records:
        nav_items.append(("dictionary", "Dictionary"))
    if unresolved_cbs or unresolved_calls:
        nav_items.append(("unresolved", "Unresolved"))

    nav_html = ''.join(f'<a href="#{id}">{label}</a>' for id, label in nav_items)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Masquerade Analysis Report - {_esc(codebase_name)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: #0d1117; color: #c9d1d9; line-height: 1.5; }}
  header {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 20px 32px; }}
  header h1 {{ font-size: 22px; color: #58a6ff; }}
  header .subtitle {{ color: #8b949e; font-size: 13px; margin-top: 4px; }}
  nav {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 0 32px; display: flex; gap: 0; position: sticky; top: 0; z-index: 10; }}
  nav a {{ color: #8b949e; text-decoration: none; padding: 10px 16px; font-size: 13px; border-bottom: 2px solid transparent; }}
  nav a:hover {{ color: #c9d1d9; border-bottom-color: #30363d; }}
  main {{ max-width: 1200px; margin: 0 auto; padding: 24px 32px; }}
  section {{ margin-bottom: 40px; }}
  h2 {{ font-size: 18px; color: #f0883e; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #21262d; }}
  h3 {{ font-size: 14px; color: #58a6ff; margin: 20px 0 8px; }}
  .grid-3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px 20px; }}
  .card-value {{ font-size: 28px; font-weight: 700; color: #58a6ff; }}
  .card-label {{ font-size: 13px; color: #8b949e; margin-top: 2px; }}
  .card-detail {{ font-size: 11px; color: #484f58; margin-top: 6px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 16px; }}
  thead th {{ text-align: left; padding: 8px 10px; color: #8b949e; font-weight: 600; border-bottom: 2px solid #30363d; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
  tbody td {{ padding: 6px 10px; border-bottom: 1px solid #21262d; }}
  tbody tr:hover {{ background: #161b22; }}
  .dim {{ color: #484f58; }}
  .summary-bar {{ margin-bottom: 16px; font-size: 14px; }}
  p {{ margin-bottom: 12px; }}
  footer {{ text-align: center; padding: 24px; color: #484f58; font-size: 11px; border-top: 1px solid #21262d; margin-top: 40px; }}
  @media print {{
    body {{ background: white; color: #1f2328; }}
    header, nav {{ background: white; border-color: #d1d9e0; }}
    header h1 {{ color: #0969da; }}
    .card {{ border-color: #d1d9e0; }}
    .card-value {{ color: #0969da; }}
    nav {{ position: static; }}
    h2 {{ color: #bf8700; border-color: #d1d9e0; }}
    h3 {{ color: #0969da; }}
    tbody td {{ border-color: #d1d9e0; }}
    thead th {{ border-color: #d1d9e0; }}
    .dim {{ color: #656d76; }}
    tbody tr:hover {{ background: transparent; }}
  }}
</style>
</head>
<body>
<header>
  <h1>Masquerade Analysis Report</h1>
  <div class="subtitle">{_esc(codebase_name)} &middot; Generated {timestamp}</div>
</header>
<nav>{nav_html}</nav>
<main>
{''.join(sections)}
</main>
<footer>Generated by Masquerade COBOL Intelligence Engine &middot; {timestamp}</footer>
</body>
</html>"""

    out_path = analysis_dir / "report.html"
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python render_report.py <codebase_dir>")
        sys.exit(1)
    path = generate_report(sys.argv[1])
    print(f"Report written to: {path}")
