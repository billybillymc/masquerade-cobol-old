import json
from pathlib import Path
from graph_context import GraphIndex
from spec_generator import generate_program_spec
from complexity import compute_complexity

codebase = Path('../test-codebases/cobolcraft')
idx = GraphIndex(str(codebase / '_analysis'))
programs = json.loads((codebase / '_analysis/programs.json').read_text())
stats    = json.loads((codebase / '_analysis/stats.json').read_text())

print('=== STATS ===')
for k, v in stats.items():
    print(f'  {k}: {v}')

print()
print('=== HOTSPOTS (top 15 most-depended-upon copybooks/programs) ===')
for name, score in idx.hub_programs(15):
    print(f'  {score}  {name}')

print()
print('=== ISOLATED leaf programs (first 20) ===')
leaves = idx.leaf_programs()
for name in leaves[:20]:
    print(f'  {name}')
print(f'  ... {len(leaves)} total')

print()
print('=== READINESS top 20 ===')
scores = []
for p in programs:
    r = idx.readiness_score(p)
    s = r.get('score', 0) if isinstance(r, dict) else r
    scores.append((p, s))
scores.sort(key=lambda x: x[1], reverse=True)
for name, score in scores[:20]:
    print(f'  {score:.2f}  {name}')

print()
print('=== DEAD CODE ===')
dead = idx.dead_code_analysis()
dead_keys = list(dead.keys()) if isinstance(dead, dict) else 'list'
print(f'  type={type(dead).__name__}  keys={dead_keys}')
if isinstance(dead, dict):
    unreachable = dead.get('unreachable', dead.get('dead_programs', []))
    print(f'  {len(unreachable)} unreachable programs')
    for d in list(unreachable)[:10]:
        print(f'    {d}')

print()
print('=== COMPLEXITY: top 15 most complex programs (by paragraph count) ===')
complex_progs = []
for name, prog in programs.items():
    para_data = prog.get('paragraphs', {})
    if isinstance(para_data, dict):
        para_list = list(para_data.values())
    else:
        para_list = para_data if isinstance(para_data, list) else []
    paras = len(para_list)
    flows = len(prog.get('data_flows', []))
    conds = sum(len(p.get('conditional_blocks', [])) for p in para_list if isinstance(p, dict))
    complex_progs.append((name, paras, conds, flows))
complex_progs.sort(key=lambda x: x[2] + x[1], reverse=True)
for name, paras, conds, flows in complex_progs[:15]:
    print(f'  paragraphs={paras:3d}  conditionals={conds:4d}  flows={flows:3d}  {name}')
