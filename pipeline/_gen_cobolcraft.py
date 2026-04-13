"""Step 3–5: spec, skeleton, business rules for CobolCraft Blocks-Parse-State."""
import json
from pathlib import Path
from graph_context import GraphIndex
from spec_generator import generate_program_spec
from skeleton_generator import generate_skeleton
from skeleton_ir import spec_to_ir, PythonRenderer, JavaRenderer, CSharpRenderer
from business_rules import extract_structural_rules
from copybook_dict import CopybookDictionary

codebase = Path('../test-codebases/cobolcraft')
analysis = codebase / '_analysis'
out = analysis / 'generated'
out.mkdir(exist_ok=True)

programs = json.loads((analysis / 'programs.json').read_text())
graph    = json.loads((analysis / 'graph.json').read_text())
idx      = GraphIndex(str(analysis))

# Build copybook dict
cbd = CopybookDictionary(str(codebase))
print(f'Copybooks loaded: {len(cbd.records)} copybooks')

# --- Step 3: Spec generation ---
print('\n=== STEP 3: Spec Generation ===')
target = 'Blocks-Parse-State'
# Graph stores IDs uppercase+hyphenated; programs.json uses title-case
graph_id = 'BLOCKS-PARSE-STATE'
actual_key = target if target in programs else next(
    (k for k in programs if k.upper() == target.upper()), target
)
spec = generate_program_spec(graph_id, idx, programs, str(codebase))
spec_path = out / f'{target.lower()}.spec.md'
spec_path.write_text(spec.render_markdown() if hasattr(spec, 'render_markdown') else str(spec))
if spec is None:
    print('  WARNING: spec returned None — program not found in analysis')
else:
    print(f'Spec written: {spec_path}')
    print(f'  complexity={getattr(spec, "complexity_grade", "?")}  readiness={getattr(spec, "readiness_score", 0):.2f}')
    print(f'  patterns: {getattr(spec, "modern_patterns", [])}')
    print(f'  wave: {getattr(spec, "migration_wave", "?")}')
    print(f'  paragraphs: {len(getattr(spec, "paragraphs", []))}')

# --- Step 4: Skeleton generation ---
print('\n=== STEP 4: Skeleton Generation ===')
if spec is not None:
    py_skel  = generate_skeleton(spec, cbd)
    ir       = spec_to_ir(spec)
    java_code = JavaRenderer().render(ir)
    cs_code   = CSharpRenderer().render(ir)

    (out / f'{target.lower()}.py').write_text(py_skel)
    (out / f'{target.lower()}.java').write_text(java_code)
    (out / f'{target.lower()}.cs').write_text(cs_code)
    print(f'Python skeleton: {len(py_skel.splitlines())} lines')
    print(f'Java skeleton:   {len(java_code.splitlines())} lines')
    print(f'C# skeleton:     {len(cs_code.splitlines())} lines')
else:
    print('  Skipped (no spec)')

# --- Step 5: Business rules ---
print('\n=== STEP 5: Business Rule Extraction ===')
prog_data = programs.get(target, programs.get(target.upper(), {}))
rules = extract_structural_rules(target, prog_data)
rules_data = [r.__dict__ if hasattr(r, '__dict__') else r for r in rules]
(out / f'{target.lower()}.rules.json').write_text(json.dumps(rules_data, indent=2, default=str))
print(f'Extracted {len(rules)} rules:')
for r in rules:
    claim = r.claim if hasattr(r, 'claim') else r.get('claim', '?')
    rtype = r.rule_type if hasattr(r, 'rule_type') else r.get('rule_type', '?')
    conf  = r.confidence if hasattr(r, 'confidence') else r.get('confidence', 0)
    try:
        conf_str = f'{float(conf):.2f}'
    except (TypeError, ValueError):
        conf_str = str(conf)
    print(f'  [{rtype}] conf={conf_str}  {claim[:80]}')

print('\nAll artifacts written to:', out)
