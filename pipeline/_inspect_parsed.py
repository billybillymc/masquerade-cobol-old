import json
from pathlib import Path

codebase = Path('../test-codebases/cobolcraft')
programs = json.loads((codebase / '_analysis/programs.json').read_text())

for name, prog in programs.items():
    para_data = prog.get('paragraphs', {})
    if isinstance(para_data, list):
        n = len(para_data)
    elif isinstance(para_data, dict):
        n = len(para_data)
    else:
        n = 0
    if n > 0:
        src = prog.get('source_file', '?')
        print(f'{name}: {n} paragraphs  ({src})')
        if isinstance(para_data, dict):
            for pname, pdata in list(para_data.items())[:8]:
                conds = len(pdata.get('conditional_blocks', []))
                flows = len(pdata.get('data_flows', []))
                print(f'  para={pname}  conds={conds}  flows={flows}')
        elif isinstance(para_data, list):
            for p in para_data[:8]:
                print(f'  para={p.get("name","?")}')
