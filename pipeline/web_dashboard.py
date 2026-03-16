"""
Interactive web dashboard for COBOL codebase analysis.

Run: python web_dashboard.py [--port 5000]
Browse: http://localhost:5000
"""

import json
import os
import sys
from pathlib import Path

from flask import Flask, render_template_string, jsonify, request

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graph_context import GraphIndex, DataFlowIndex
from complexity import compute_all, complexity_grade
from effort_estimator import estimate_estate
from export import export_program_inventory

app = Flask(__name__)

_project_root = Path(__file__).resolve().parent.parent
_test_codebases = _project_root / "test-codebases"

CODEBASES = {}


def _discover_codebases():
    global CODEBASES
    for d in _test_codebases.iterdir():
        analysis = d / "_analysis"
        if analysis.exists() and (analysis / "graph.json").exists():
            name = d.name
            CODEBASES[name] = {
                "dir": str(d),
                "analysis_dir": str(analysis),
                "graph": GraphIndex(str(analysis)),
            }


_discover_codebases()


def _json_safe(obj):
    """Recursively convert sets and tuples to lists for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (set, frozenset)):
        return sorted(str(x) for x in obj)
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    return obj


# ─── HTML Template ───────────────────────────────────────────────────

BASE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Masquerade — COBOL Intelligence Engine</title>
<style>
  :root {
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --dim: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --red: #f85149; --yellow: #d29922; --purple: #bc8cff;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
         background:var(--bg); color:var(--text); }
  a { color:var(--accent); text-decoration:none; }
  a:hover { text-decoration:underline; }

  .topbar { background:var(--surface); border-bottom:1px solid var(--border);
            padding:12px 24px; display:flex; align-items:center; gap:20px; }
  .topbar h1 { font-size:18px; font-weight:600; }
  .topbar .tabs { display:flex; gap:4px; }
  .topbar .tab { padding:6px 14px; border-radius:6px; cursor:pointer; font-size:14px; color:var(--dim); }
  .topbar .tab:hover { background:var(--border); color:var(--text); }
  .topbar .tab.active { background:var(--accent); color:#fff; }

  .container { max-width:1400px; margin:0 auto; padding:24px; }

  .stats-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:16px; margin-bottom:24px; }
  .stat-card { background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:16px; }
  .stat-card .label { font-size:12px; color:var(--dim); text-transform:uppercase; letter-spacing:0.5px; }
  .stat-card .value { font-size:28px; font-weight:700; margin-top:4px; }

  .card { background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:20px; margin-bottom:20px; }
  .card h2 { font-size:16px; margin-bottom:12px; color:var(--accent); }

  table { width:100%; border-collapse:collapse; font-size:13px; }
  th { text-align:left; padding:8px 12px; border-bottom:2px solid var(--border); color:var(--dim);
       font-size:11px; text-transform:uppercase; letter-spacing:0.5px; cursor:pointer; user-select:none; }
  th:hover { color:var(--accent); }
  td { padding:8px 12px; border-bottom:1px solid var(--border); }
  tr:hover td { background:rgba(88,166,255,0.05); }

  .badge { display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }
  .badge-low { background:rgba(63,185,80,0.15); color:var(--green); }
  .badge-med { background:rgba(210,153,34,0.15); color:var(--yellow); }
  .badge-high { background:rgba(248,81,73,0.15); color:var(--red); }
  .badge-cics { background:rgba(188,140,255,0.15); color:var(--purple); }
  .badge-batch { background:rgba(88,166,255,0.15); color:var(--accent); }

  .bar { height:6px; border-radius:3px; background:var(--border); }
  .bar-fill { height:100%; border-radius:3px; }

  .search { background:var(--surface); border:1px solid var(--border); border-radius:6px;
            padding:8px 12px; color:var(--text); font-size:14px; width:300px; }
  .search:focus { outline:none; border-color:var(--accent); }

  .detail-section { margin-top:12px; }
  .detail-section h3 { font-size:14px; color:var(--dim); margin-bottom:8px; }
  .detail-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }

  @media(max-width:768px) { .detail-grid { grid-template-columns:1fr; } .stats-grid { grid-template-columns:1fr 1fr; } }

  .hidden { display:none; }
  .clickable { cursor:pointer; }
  .mono { font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace; }
</style>
</head>
<body>
<div class="topbar">
  <h1>Masquerade</h1>
  <div class="tabs" id="codebase-tabs"></div>
  <input type="text" class="search" id="search" placeholder="Filter programs...">
</div>
<div class="container" id="app">
  <div id="dashboard"></div>
</div>
<script>
const API = '';
let codebases = {};
let active = '';

async function load() {
  const res = await fetch(API + '/api/codebases');
  codebases = await res.json();
  const names = Object.keys(codebases);
  if (!names.length) { document.getElementById('app').innerHTML = '<p>No analyzed codebases found.</p>'; return; }
  active = names[0];
  renderTabs(names);
  await loadCodebase(active);
}

function renderTabs(names) {
  const el = document.getElementById('codebase-tabs');
  el.innerHTML = names.map(n => `<div class="tab ${n===active?'active':''}" onclick="switchCb('${n}')">${n}</div>`).join('');
}

async function switchCb(name) {
  active = name;
  renderTabs(Object.keys(codebases));
  await loadCodebase(name);
}

async function loadCodebase(name) {
  const res = await fetch(API + '/api/codebase/' + name);
  const data = await res.json();
  renderDashboard(data);
}

function renderDashboard(d) {
  const s = d.summary;
  const el = document.getElementById('dashboard');

  const riskBadge = (r) => {
    if (!r) return '';
    const cls = r==='HIGH'?'badge-high':r==='MEDIUM'?'badge-med':'badge-low';
    return `<span class="badge ${cls}">${r}</span>`;
  };
  const typeBadge = (t) => {
    const cls = t==='CICS Online'?'badge-cics':'badge-batch';
    return `<span class="badge ${cls}">${t}</span>`;
  };
  const bar = (val, max, color) => {
    const pct = max > 0 ? Math.min(val/max*100,100) : 0;
    return `<div class="bar"><div class="bar-fill" style="width:${pct}%;background:${color}"></div></div>`;
  };

  const maxCC = Math.max(...d.programs.map(p=>p.cyclomatic_complexity||0), 1);
  const maxLOC = Math.max(...d.programs.map(p=>p.code_lines||0), 1);
  const maxEffort = Math.max(...d.programs.map(p=>p.effort_days||0), 1);

  let html = `
    <div class="stats-grid">
      <div class="stat-card"><div class="label">Programs</div><div class="value">${s.total_programs}</div></div>
      <div class="stat-card"><div class="label">Code Lines</div><div class="value">${(s.total_code_lines||0).toLocaleString()}</div></div>
      <div class="stat-card"><div class="label">CICS / Batch</div><div class="value">${s.cics_programs} / ${s.batch_programs}</div></div>
      <div class="stat-card"><div class="label">Copybooks</div><div class="value">${s.total_copybooks}</div></div>
      <div class="stat-card"><div class="label">Effort (days)</div><div class="value">${d.effort?.total_effort_days || '—'}</div></div>
      <div class="stat-card"><div class="label">Quick Wins</div><div class="value" style="color:var(--green)">${d.effort?.quick_win_count || '—'}</div></div>
    </div>

    <div class="card">
      <h2>Program Inventory</h2>
      <table>
        <thead><tr>
          <th onclick="sortTable(0)">Program</th>
          <th onclick="sortTable(1)">Type</th>
          <th onclick="sortTable(2)">LOC</th>
          <th onclick="sortTable(3)">Complexity</th>
          <th onclick="sortTable(4)">Readiness</th>
          <th onclick="sortTable(5)">Effort</th>
          <th onclick="sortTable(6)">Risk</th>
          <th onclick="sortTable(7)">Wave</th>
        </tr></thead>
        <tbody id="program-table">`;

  for (const p of d.programs) {
    html += `<tr class="program-row clickable" data-program="${p.program}" onclick="showDetail('${p.program}')">
      <td class="mono">${p.program}</td>
      <td>${typeBadge(p.type)}</td>
      <td>${p.code_lines} ${bar(p.code_lines, maxLOC, 'var(--accent)')}</td>
      <td>${p.cyclomatic_complexity||'—'} ${bar(p.cyclomatic_complexity||0, maxCC, p.cyclomatic_complexity>25?'var(--red)':'var(--green)')}</td>
      <td>${p.readiness_score} ${bar(p.readiness_score, 100, 'var(--green)')}</td>
      <td>${p.effort_days||'—'} ${bar(p.effort_days||0, maxEffort, 'var(--yellow)')}</td>
      <td>${riskBadge(p.risk_level)}</td>
      <td style="font-size:12px;color:var(--dim)">${p.migration_wave||''}</td>
    </tr>`;
  }

  html += `</tbody></table></div>
    <div id="program-detail" class="card hidden"></div>`;
  el.innerHTML = html;
  document.getElementById('search').oninput = filterPrograms;
}

function filterPrograms() {
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('.program-row').forEach(r => {
    r.style.display = r.dataset.program.toLowerCase().includes(q) ? '' : 'none';
  });
}

let sortCol = -1, sortAsc = true;
function sortTable(col) {
  if (sortCol === col) sortAsc = !sortAsc; else { sortCol = col; sortAsc = true; }
  const tbody = document.getElementById('program-table');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort((a, b) => {
    let va = a.children[col].textContent.trim();
    let vb = b.children[col].textContent.trim();
    const na = parseFloat(va), nb = parseFloat(vb);
    if (!isNaN(na) && !isNaN(nb)) return sortAsc ? na-nb : nb-na;
    return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
  });
  rows.forEach(r => tbody.appendChild(r));
}

async function showDetail(pgm) {
  const res = await fetch(API + '/api/codebase/' + active + '/program/' + pgm);
  const p = await res.json();
  const el = document.getElementById('program-detail');
  el.classList.remove('hidden');
  el.scrollIntoView({behavior:'smooth'});

  let html = `<h2>${p.program} — ${p.type}</h2>
    <div class="detail-grid">
      <div>
        <div class="detail-section"><h3>Structure</h3>
          <p>Source: <span class="mono">${p.source_file}</span></p>
          <p>Lines: ${p.code_lines} code / ${p.total_lines} total</p>
          <p>Paragraphs: ${p.paragraph_count}</p>
          <p>Complexity: ${p.cyclomatic_complexity} (${p.complexity_grade})</p>
          <p>Nesting depth: ${p.max_nesting}</p>
        </div>
        <div class="detail-section"><h3>Dependencies</h3>
          <p>Callers: ${p.callers?.length ? p.callers.join(', ') : 'none'}</p>
          <p>Callees: ${p.callees?.length ? p.callees.join(', ') : 'none'}</p>
          <p>Copybooks: ${p.copybooks?.length ? p.copybooks.join(', ') : 'none'}</p>
        </div>
      </div>
      <div>
        <div class="detail-section"><h3>Migration</h3>
          <p>Readiness: ${p.readiness_score}/100</p>
          <p>Effort: ${p.effort_days} person-days</p>
          <p>Risk: ${p.risk_level}</p>
          <p>Wave: ${p.migration_wave}</p>
          <p>Pattern: ${p.modern_pattern}</p>
        </div>
        <div class="detail-section"><h3>Data Flow</h3>
          <p>Assignments: ${p.data_flow_summary?.total_flows || 0}</p>
          <p>Fields written: ${p.data_flow_summary?.fields_written?.length || 0}</p>
          <p>Fields read: ${p.data_flow_summary?.fields_read?.length || 0}</p>
          ${p.validation_fields?.length ? '<p>Validation fields: ' + p.validation_fields.join(', ') + '</p>' : ''}
        </div>
      </div>
    </div>`;

  if (p.paragraphs?.length) {
    html += `<div class="detail-section"><h3>Paragraphs (${p.paragraphs.length})</h3><table>
      <thead><tr><th>Name</th><th>PERFORMs</th><th>CALLs</th><th>CICS</th><th>Writes</th></tr></thead><tbody>`;
    for (const para of p.paragraphs) {
      html += `<tr>
        <td class="mono">${para.name}${para.is_entry_point?' ▸':''}</td>
        <td style="font-size:12px">${para.performs?.join(', ')||'—'}</td>
        <td style="font-size:12px">${para.calls?.join(', ')||'—'}</td>
        <td style="font-size:12px">${para.cics_ops?.join(', ')||'—'}</td>
        <td style="font-size:12px">${(para.data_flows_out||[]).slice(0,5).join(', ')}${(para.data_flows_out||[]).length>5?' ...':''}</td>
      </tr>`;
    }
    html += '</tbody></table></div>';
  }

  if (p.notes?.length) {
    html += '<div class="detail-section"><h3>Reimplementation Notes</h3><ul>';
    for (const n of p.notes) html += `<li>${n}</li>`;
    html += '</ul></div>';
  }

  el.innerHTML = html;
}

load();
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(BASE_HTML)


@app.route("/api/codebases")
def api_codebases():
    return jsonify({name: {"dir": info["dir"]} for name, info in CODEBASES.items()})


@app.route("/api/codebase/<name>")
def api_codebase(name):
    if name not in CODEBASES:
        return jsonify({"error": "not found"}), 404

    info = CODEBASES[name]
    graph = info["graph"]
    summary = graph.summary()
    programs = export_program_inventory(graph, info["dir"])
    programs.sort(key=lambda p: p.get("readiness_score", 0), reverse=True)

    dead = graph.dead_code_analysis()
    readiness = graph.readiness_ranking()
    estate = estimate_estate(readiness, dead)

    safe_summary = _json_safe(summary)

    return jsonify({
        "name": name,
        "summary": safe_summary,
        "programs": programs,
        "effort": estate["summary"],
        "waves": estate["waves"],
    })


@app.route("/api/codebase/<name>/program/<pgm>")
def api_program(name, pgm):
    if name not in CODEBASES:
        return jsonify({"error": "not found"}), 404

    info = CODEBASES[name]
    graph = info["graph"]
    pgm = pgm.upper()

    if pgm not in graph.program_names():
        return jsonify({"error": f"program {pgm} not found"}), 404

    from spec_generator import generate_program_spec, _load_program_data
    analysis_dir = Path(info["analysis_dir"])
    program_data = _load_program_data(analysis_dir)

    spec = generate_program_spec(pgm, graph, program_data, info["dir"])
    if not spec:
        return jsonify({"error": "could not generate spec"}), 500

    return jsonify({
        "program": spec.program,
        "type": spec.program_type,
        "source_file": spec.source_file,
        "total_lines": spec.total_lines,
        "code_lines": spec.code_lines,
        "paragraph_count": spec.paragraph_count,
        "cyclomatic_complexity": spec.cyclomatic_complexity,
        "max_nesting": spec.max_nesting,
        "complexity_grade": spec.complexity_grade,
        "callers": spec.callers,
        "callees": spec.callees,
        "copybooks": spec.copybooks,
        "files_accessed": spec.files_accessed,
        "readiness_score": spec.readiness_score,
        "effort_days": spec.effort_days,
        "risk_level": spec.risk_level,
        "paragraphs": [
            {
                "name": p.name,
                "performs": p.performs,
                "calls": p.calls,
                "cics_ops": p.cics_ops,
                "data_flows_in": p.data_flows_in,
                "data_flows_out": p.data_flows_out,
                "is_entry_point": p.is_entry_point,
            }
            for p in spec.paragraphs
        ],
        "data_flow_summary": spec.data_flow_summary,
        "validation_fields": spec.validation_fields,
        "modern_pattern": spec.modern_pattern,
        "migration_wave": spec.migration_wave,
        "notes": spec.notes,
    })


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Masquerade Web Dashboard")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    print(f"\n  Masquerade COBOL Intelligence Engine")
    print(f"  Dashboard: http://{args.host}:{args.port}")
    print(f"  Codebases: {', '.join(CODEBASES.keys()) or 'none found'}\n")

    app.run(host=args.host, port=args.port, debug=True)
