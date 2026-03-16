"""
Generates an interactive HTML visualization of the COBOL dependency graph.
Uses D3.js force-directed layout for the inter-program call graph
and provides a browsable program detail panel.
"""

import json
import sys
from pathlib import Path


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>COBOL Codebase Analysis — {title}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace; background: #0d1117; color: #c9d1d9; }
  #header { padding: 18px 24px; background: #161b22; border-bottom: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; }
  #header h1 { font-size: 18px; color: #58a6ff; font-weight: 600; }
  #header .stats { font-size: 13px; color: #8b949e; }
  #header .stats span { color: #58a6ff; font-weight: 600; margin: 0 4px; }
  #main { display: flex; height: calc(100vh - 60px); }
  #graph-panel { flex: 1; position: relative; overflow: hidden; }
  #detail-panel { width: 380px; background: #161b22; border-left: 1px solid #30363d; overflow-y: auto; padding: 16px; display: none; }
  #detail-panel.open { display: block; }
  #detail-panel h2 { font-size: 16px; color: #f0883e; margin-bottom: 12px; }
  #detail-panel h3 { font-size: 13px; color: #58a6ff; margin: 14px 0 6px; text-transform: uppercase; letter-spacing: 0.5px; }
  #detail-panel .close-btn { position: absolute; top: 8px; right: 8px; cursor: pointer; color: #8b949e; font-size: 18px; }
  #detail-panel .close-btn:hover { color: #f0883e; }
  .detail-table { width: 100%; font-size: 12px; border-collapse: collapse; }
  .detail-table td { padding: 3px 6px; border-bottom: 1px solid #21262d; }
  .detail-table td:first-child { color: #8b949e; width: 40%; }
  .detail-list { font-size: 12px; list-style: none; }
  .detail-list li { padding: 3px 0; border-bottom: 1px solid #21262d; }
  .detail-list li .type-tag { font-size: 10px; padding: 1px 5px; border-radius: 3px; margin-left: 6px; }
  .tag-call { background: #1f6feb33; color: #58a6ff; }
  .tag-xctl { background: #da363333; color: #f85149; }
  .tag-link { background: #f0883e33; color: #f0883e; }
  .tag-copies { background: #8b949e33; color: #8b949e; }
  .tag-cics { background: #a371f733; color: #bc8cff; }
  svg { width: 100%; height: 100%; }
  .link { stroke-opacity: 0.6; }
  .link-CALL { stroke: #58a6ff; }
  .link-XCTL { stroke: #f85149; }
  .link-LINK { stroke: #f0883e; }
  .link-COPIES { stroke: #484f58; stroke-dasharray: 4,3; }
  .link-CICS_IO { stroke: #bc8cff; stroke-dasharray: 2,2; }
  .link-READS_FILE { stroke: #f0883e; stroke-dasharray: 3,3; }
  .node-label { font-size: 11px; fill: #c9d1d9; pointer-events: none; text-anchor: middle; font-family: inherit; }
  #legend { position: absolute; bottom: 16px; left: 16px; background: #161b22ee; border: 1px solid #30363d; border-radius: 6px; padding: 12px 16px; font-size: 11px; }
  #legend div { margin: 3px 0; display: flex; align-items: center; gap: 8px; }
  #legend .swatch { width: 14px; height: 14px; border-radius: 3px; }
  #controls { position: absolute; top: 12px; right: 12px; display: flex; gap: 6px; }
  #controls button { background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-family: inherit; }
  #controls button:hover { background: #30363d; }
  #controls button.active { background: #1f6feb; border-color: #58a6ff; }
  #tooltip { position: absolute; background: #1c2128; border: 1px solid #30363d; border-radius: 4px; padding: 8px 12px; font-size: 11px; pointer-events: none; display: none; z-index: 100; max-width: 300px; }
</style>
</head>
<body>

<div id="header">
  <h1>{title}</h1>
  <div class="stats">
    <span>{n_programs}</span> programs &middot;
    <span>{total_loc}</span> LOC &middot;
    <span>{n_paragraphs}</span> paragraphs &middot;
    <span>{n_copybooks}</span> copybook refs &middot;
    <span>{n_calls}</span> calls &middot;
    <span>{n_cics}</span> CICS ops
  </div>
</div>

<div id="main">
  <div id="graph-panel">
    <svg id="svg"></svg>
    <div id="legend">
      <div><div class="swatch" style="background:#4A90D9"></div> CICS Program</div>
      <div><div class="swatch" style="background:#7BC67E"></div> Batch Program</div>
      <div><div class="swatch" style="background:#F5A623"></div> File / Dataset</div>
      <div><div class="swatch" style="background:#D0D0D0"></div> Copybook</div>
      <div><div class="swatch" style="background:#bc8cff"></div> BMS Map</div>
      <div style="margin-top:6px"><svg width="14" height="2"><line x1="0" y1="1" x2="14" y2="1" stroke="#58a6ff" stroke-width="2"/></svg> CALL</div>
      <div><svg width="14" height="2"><line x1="0" y1="1" x2="14" y2="1" stroke="#f85149" stroke-width="2"/></svg> XCTL</div>
      <div><svg width="14" height="2"><line x1="0" y1="1" x2="14" y2="1" stroke="#484f58" stroke-width="2" stroke-dasharray="4,3"/></svg> COPIES</div>
    </div>
    <div id="controls">
      <button id="btn-programs" class="active" onclick="toggleLayer('programs')">Programs</button>
      <button id="btn-copybooks" onclick="toggleLayer('copybooks')">Copybooks</button>
      <button id="btn-files" onclick="toggleLayer('files')">Files</button>
    </div>
    <div id="tooltip"></div>
  </div>
  <div id="detail-panel">
    <span class="close-btn" onclick="closeDetail()">&times;</span>
    <div id="detail-content"></div>
  </div>
</div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const graphData = {graph_json};
const programData = {programs_json};
const statsData = {stats_json};

const nodeTypeColors = {
  'PROGRAM': n => {
    const pid = n.name;
    const prog = programData[pid];
    if (prog && prog.paragraphs.some(p => p.cics_ops.length > 0)) return '#4A90D9';
    const edges = graphData.edges.filter(e => e.source === n.id && e.type === 'CICS_IO');
    if (edges.length > 0) return '#4A90D9';
    return '#7BC67E';
  },
  'FILE': () => '#F5A623',
  'COPYBOOK': () => '#D0D0D0',
  'MAP': () => '#bc8cff',
};

const nodeTypeRadius = {
  'PROGRAM': 10,
  'FILE': 7,
  'COPYBOOK': 5,
  'MAP': 6,
};

let showCopybooks = false;
let showFiles = false;

function toggleLayer(layer) {
  if (layer === 'copybooks') {
    showCopybooks = !showCopybooks;
    d3.select('#btn-copybooks').classed('active', showCopybooks);
  } else if (layer === 'files') {
    showFiles = !showFiles;
    d3.select('#btn-files').classed('active', showFiles);
  }
  updateVisibility();
}

function updateVisibility() {
  node.style('display', d => {
    if (d.type === 'PARAGRAPH') return 'none';
    if (d.type === 'COPYBOOK' && !showCopybooks) return 'none';
    if ((d.type === 'FILE' || d.type === 'MAP') && !showFiles) return 'none';
    return null;
  });
  label.style('display', d => {
    if (d.type === 'PARAGRAPH') return 'none';
    if (d.type === 'COPYBOOK' && !showCopybooks) return 'none';
    if ((d.type === 'FILE' || d.type === 'MAP') && !showFiles) return 'none';
    return null;
  });
  link.style('display', d => {
    const sType = nodesById[d.source.id || d.source]?.type;
    const tType = nodesById[d.target.id || d.target]?.type;
    if (sType === 'PARAGRAPH' || tType === 'PARAGRAPH') return 'none';
    if ((sType === 'COPYBOOK' || tType === 'COPYBOOK') && !showCopybooks) return 'none';
    if ((sType === 'FILE' || tType === 'FILE' || sType === 'MAP' || tType === 'MAP') && !showFiles) return 'none';
    return null;
  });
}

const nodesById = {};
const filteredNodes = graphData.nodes.filter(n => n.type !== 'PARAGRAPH');
filteredNodes.forEach(n => { nodesById[n.id] = n; });
const filteredEdges = graphData.edges.filter(e => {
  const sn = nodesById[e.source];
  const tn = nodesById[e.target];
  return sn && tn;
});

const svg = d3.select('#svg');
const width = document.getElementById('graph-panel').clientWidth;
const height = document.getElementById('graph-panel').clientHeight;

const g = svg.append('g');
const zoom = d3.zoom().scaleExtent([0.1, 4]).on('zoom', e => g.attr('transform', e.transform));
svg.call(zoom);

svg.append('defs').append('marker')
  .attr('id', 'arrowhead').attr('viewBox', '0 0 10 10')
  .attr('refX', 20).attr('refY', 5)
  .attr('markerWidth', 6).attr('markerHeight', 6)
  .attr('orient', 'auto')
  .append('path').attr('d', 'M 0 0 L 10 5 L 0 10 z').attr('fill', '#484f58');

const simulation = d3.forceSimulation(filteredNodes)
  .force('link', d3.forceLink(filteredEdges).id(d => d.id).distance(d => {
    if (d.type === 'COPIES') return 120;
    return 80;
  }))
  .force('charge', d3.forceManyBody().strength(d => d.type === 'PROGRAM' ? -300 : -100))
  .force('center', d3.forceCenter(width / 2, height / 2))
  .force('collision', d3.forceCollide(20));

const link = g.append('g').selectAll('line')
  .data(filteredEdges).join('line')
  .attr('class', d => 'link link-' + d.type)
  .attr('stroke-width', d => d.type === 'COPIES' ? 1 : 2)
  .attr('marker-end', 'url(#arrowhead)');

const node = g.append('g').selectAll('circle')
  .data(filteredNodes).join('circle')
  .attr('r', d => nodeTypeRadius[d.type] || 6)
  .attr('fill', d => {
    const fn = nodeTypeColors[d.type];
    return fn ? fn(d) : '#888';
  })
  .attr('stroke', '#0d1117').attr('stroke-width', 1.5)
  .style('cursor', 'pointer')
  .on('click', (e, d) => showDetail(d))
  .on('mouseover', (e, d) => showTooltip(e, d))
  .on('mouseout', hideTooltip)
  .call(d3.drag()
    .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
    .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
    .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
  );

const label = g.append('g').selectAll('text')
  .data(filteredNodes).join('text')
  .attr('class', 'node-label')
  .attr('dy', d => -(nodeTypeRadius[d.type] || 6) - 4)
  .text(d => d.name);

simulation.on('tick', () => {
  link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
  node.attr('cx', d => d.x).attr('cy', d => d.y);
  label.attr('x', d => d.x).attr('y', d => d.y);
});

updateVisibility();

function showTooltip(event, d) {
  const tt = d3.select('#tooltip');
  let html = `<strong>${d.name}</strong> (${d.type})`;
  if (d.metadata) {
    if (d.metadata.total_lines) html += `<br>${d.metadata.total_lines} lines, ${d.metadata.paragraph_count} paragraphs`;
    if (d.metadata.author) html += `<br>Author: ${d.metadata.author}`;
  }
  tt.html(html).style('display', 'block')
    .style('left', (event.pageX + 12) + 'px')
    .style('top', (event.pageY - 12) + 'px');
}

function hideTooltip() { d3.select('#tooltip').style('display', 'none'); }

function showDetail(d) {
  const panel = d3.select('#detail-panel').classed('open', true);
  const content = d3.select('#detail-content');
  let html = `<h2>${d.name}</h2><p style="color:#8b949e;font-size:12px">${d.type}</p>`;

  if (d.type === 'PROGRAM' && programData[d.name]) {
    const prog = programData[d.name];
    html += `<h3>Metrics</h3><table class="detail-table">
      <tr><td>Source file</td><td>${prog.source_file.split(/[/\\]/).pop()}</td></tr>
      <tr><td>Total lines</td><td>${prog.total_lines}</td></tr>
      <tr><td>Code lines</td><td>${prog.code_lines}</td></tr>
      <tr><td>Comment lines</td><td>${prog.comment_lines}</td></tr>
      <tr><td>Paragraphs</td><td>${prog.paragraphs.length}</td></tr>
      <tr><td>Copybooks</td><td>${prog.copy_statements.length}</td></tr>
      <tr><td>Data items</td><td>${prog.data_items_count}</td></tr>
    </table>`;

    if (prog.paragraphs.length > 0) {
      html += `<h3>Paragraphs</h3><ul class="detail-list">`;
      prog.paragraphs.forEach(p => {
        const tags = [];
        p.performs.forEach(pf => tags.push(pf.target));
        p.calls.forEach(c => tags.push(`${c.target} <span class="type-tag tag-${c.type.toLowerCase()}">${c.type}</span>`));
        p.cics_ops.forEach(c => tags.push(`${c.operation} <span class="type-tag tag-cics">CICS</span>`));
        html += `<li><strong>${p.name}</strong>`;
        if (p.span) html += ` <span style="color:#484f58">L${p.span.start_line}</span>`;
        if (tags.length) html += `<br><span style="color:#8b949e;font-size:11px">${tags.join(', ')}</span>`;
        html += `</li>`;
      });
      html += `</ul>`;
    }

    if (prog.copy_statements.length > 0) {
      html += `<h3>Copybooks</h3><ul class="detail-list">`;
      prog.copy_statements.forEach(c => {
        html += `<li>${c.copybook} <span class="type-tag tag-copies">COPY</span>`;
        if (c.replacing.length) html += ` <span style="color:#484f58">REPLACING</span>`;
        html += `</li>`;
      });
      html += `</ul>`;
    }

    if (prog.call_targets.length > 0) {
      html += `<h3>Calls</h3><ul class="detail-list">`;
      prog.call_targets.forEach(c => {
        html += `<li>${c.target} <span class="type-tag tag-${c.type.toLowerCase()}">${c.type}</span> L${c.line}</li>`;
      });
      html += `</ul>`;
    }

    if (prog.file_controls.length > 0) {
      html += `<h3>File Controls</h3><ul class="detail-list">`;
      prog.file_controls.forEach(f => {
        html += `<li>${f.name} &rarr; ${f.assign_to}`;
        if (f.organization) html += ` (${f.organization})`;
        html += `</li>`;
      });
      html += `</ul>`;
    }
  }

  // Show connected edges
  const incoming = graphData.edges.filter(e => (e.target === d.id || e.target.id === d.id) && e.type !== 'PERFORMS');
  const outgoing = graphData.edges.filter(e => (e.source === d.id || e.source.id === d.id) && e.type !== 'PERFORMS');

  if (incoming.length > 0) {
    html += `<h3>Incoming (${incoming.length})</h3><ul class="detail-list">`;
    const seen = new Set();
    incoming.forEach(e => {
      const src = typeof e.source === 'string' ? e.source : e.source.id;
      const key = src + e.type;
      if (!seen.has(key)) {
        seen.add(key);
        const name = src.replace(/^(PGM|CPY|FILE|MAP):/, '');
        html += `<li>${name} <span class="type-tag tag-${e.type === 'COPIES' ? 'copies' : e.type.toLowerCase()}">${e.type}</span></li>`;
      }
    });
    html += `</ul>`;
  }

  content.html(html);
}

function closeDetail() {
  d3.select('#detail-panel').classed('open', false);
}
</script>
</body>
</html>"""


def generate_html(analysis_dir: Path, title: str):
    programs = json.loads((analysis_dir / 'programs.json').read_text())
    graph = json.loads((analysis_dir / 'graph.json').read_text())
    stats = json.loads((analysis_dir / 'stats.json').read_text())

    html = HTML_TEMPLATE
    html = html.replace('{title}', title)
    html = html.replace('{n_programs}', str(stats['total_programs']))
    html = html.replace('{total_loc}', f"{stats['total_loc']:,}")
    html = html.replace('{n_paragraphs}', str(stats['total_paragraphs']))
    html = html.replace('{n_copybooks}', str(stats['total_copybook_refs']))
    html = html.replace('{n_calls}', str(stats['total_inter_program_calls']))
    html = html.replace('{n_cics}', str(stats['total_cics_operations']))
    html = html.replace('{graph_json}', json.dumps(graph))
    html = html.replace('{programs_json}', json.dumps(programs))
    html = html.replace('{stats_json}', json.dumps(stats))

    out_path = analysis_dir / 'explorer.html'
    out_path.write_text(html, encoding='utf-8')
    print(f"Written: {out_path}")
    return out_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python render_html.py <analysis_dir> [title]")
        sys.exit(1)
    analysis_dir = Path(sys.argv[1])
    title = sys.argv[2] if len(sys.argv) > 2 else analysis_dir.parent.name
    generate_html(analysis_dir, title)
