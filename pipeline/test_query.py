"""Quick test: run a few queries against the RAG pipeline."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag_config import register_codebase
register_codebase('carddemo', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'test-codebases', 'carddemo')))
register_codebase('taxe-fonciere', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'test-codebases', 'taxe-fonciere')))

from synthesis.chain import query

QUESTIONS = [
    "Where do we calculate interest on accounts?",
    "What happens when a credit card transaction is posted?",
    "How is the French property tax (cotisation communale) calculated?",
]

for q in QUESTIONS:
    print(f"\n{'='*70}")
    print(f"  Q: {q}")
    print('='*70)
    result = query(q)
    print(f"\n  ANSWER:\n  {result.answer}")
    print(f"\n  SOURCES:")
    for i, s in enumerate(result.sources[:5], 1):
        c = s.chunk
        label = c.file_path
        if c.program_name:
            label += f" ({c.program_name}"
            if c.paragraph_name:
                label += f"::{c.paragraph_name}"
            label += ")"
        print(f"    {i}. [{s.score:.3f}] {label}:{c.start_line}-{c.end_line} [{c.chunk_type}]")
        extras = []
        if c.calls: extras.append(f"calls={','.join(c.calls[:3])}")
        if c.performs: extras.append(f"performs={','.join(c.performs[:3])}")
        if c.cics_ops: extras.append(f"cics={','.join(c.cics_ops[:3])}")
        if extras:
            print(f"       {' | '.join(extras)}")
    print(f"\n  [{result.latency_ms:.0f}ms]")
