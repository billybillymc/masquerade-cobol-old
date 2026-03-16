"""
Standalone ingestion script: scan -> parse -> chunk -> cache -> embed -> upload.

Usage:
    python ingest.py <codebase_dir> --name <codebase_name> [--index <pinecone_index>] [--dry-run]

Examples:
    python ingest.py ../test-codebases/taxe-fonciere --name taxe-fonciere --dry-run
    python ingest.py ../test-codebases/carddemo --name carddemo --index masquerade-cobol
"""

import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_config import register_codebase, CODEBASES, PINECONE_INDEX_NAME
from ingestion.scanner import scan_source_files
from ingestion.chunker import chunk_all_files
from cobol_parser import parse_cobol_file
from graph_context import GraphIndex


def ingest_codebase(name: str, dry_run: bool = False) -> None:
    cb_config = CODEBASES[name]
    index_name = cb_config["index"]
    src_path = cb_config["src_path"]

    print("=" * 60)
    print(f"  COBOL Ingestion: {name.upper()}")
    print(f"  Source: {src_path}")
    print(f"  Index: {index_name}")
    print("=" * 60)

    # Step 1: Scan
    print("\n[1/5] Scanning source files...")
    files = scan_source_files(base_path=src_path, codebase=name)
    print(f"  Found {len(files)} files")

    by_ext = {}
    for f in files:
        ext = f["extension"]
        by_ext[ext] = by_ext.get(ext, 0) + 1
    for ext, count in sorted(by_ext.items()):
        print(f"    {ext}: {count}")

    # Step 2: Parse COBOL files for structural metadata
    print("\n[2/5] Parsing COBOL files for structural metadata...")
    parsed_programs = {}
    parse_errors = 0
    cobol_files = [f for f in files if f["extension"] in (".cbl", ".cob")]
    for file_info in cobol_files:
        try:
            prog = parse_cobol_file(Path(file_info["path"]))
            parsed_programs[file_info["path"]] = prog
        except Exception as e:
            parse_errors += 1
            print(f"    Parse error: {file_info['rel_path']}: {e}")

    print(f"  Parsed {len(parsed_programs)} programs ({parse_errors} errors)")

    # Step 2b: Load analysis graph if available
    analysis_dir = Path(src_path) / "_analysis"
    graph = None
    if analysis_dir.exists() and (analysis_dir / "graph.json").exists():
        print(f"\n  Loading analysis graph from {analysis_dir}...")
        graph = GraphIndex(str(analysis_dir))
        print(f"  Graph loaded: {len(graph.program_names())} programs, {len(graph.edges)} edges")
    else:
        print(f"\n  No analysis graph found at {analysis_dir}.")
        print(f"  Run 'python analyze.py {src_path}' first for graph-enriched ingestion.")

    # Step 3: Chunk
    print("\n[3/5] Chunking files...")
    chunks = chunk_all_files(files, parsed_programs=parsed_programs, graph=graph)
    print(f"  Generated {len(chunks)} chunks")

    by_type = {}
    for c in chunks:
        by_type[c.chunk_type] = by_type.get(c.chunk_type, 0) + 1
    for ctype, count in sorted(by_type.items()):
        print(f"    {ctype}: {count}")

    parser_enriched = sum(1 for c in chunks if c.calls or c.performs or c.copybooks or c.cics_ops)
    graph_enriched = sum(1 for c in chunks if c.called_by or c.calls_to or c.shared_with)
    flow_enriched = sum(1 for c in chunks if c.data_flow_count > 0)
    print(f"  {parser_enriched}/{len(chunks)} chunks have parser-level metadata")
    print(f"  {graph_enriched}/{len(chunks)} chunks have graph-level metadata (callers/callees/shared)")
    print(f"  {flow_enriched}/{len(chunks)} chunks have data flow metadata")

    # Step 4: Cache
    print("\n[4/5] Caching chunks...")
    from ingestion.uploader import save_chunks_cache, _cache_path_for
    cache_path = _cache_path_for(name)
    cache_records = [{
        "id": c.id,
        "metadata": {
            "text": c.text[:39000],
            "file_path": c.file_path,
            "start_line": c.start_line,
            "end_line": c.end_line,
            "chunk_type": c.chunk_type,
            "program_name": c.program_name,
            "paragraph_name": c.paragraph_name,
            "language": c.language,
            "codebase": c.codebase,
            "calls": ",".join(c.calls[:10]),
            "performs": ",".join(c.performs[:10]),
            "copybooks": ",".join(c.copybooks[:10]),
            "cics_ops": ",".join(c.cics_ops[:10]),
            "called_by": ",".join(c.called_by[:10]),
            "calls_to": ",".join(c.calls_to[:10]),
            "shared_with": ",".join(c.shared_with[:10]),
            "hub_score": str(round(c.hub_score, 2)),
            "data_flow_fields": ",".join(c.data_flow_fields[:20]),
            "data_flow_count": str(c.data_flow_count),
        },
    } for c in chunks]
    save_chunks_cache(cache_records, path=cache_path)

    if dry_run:
        print("\n[DRY RUN] Skipping embedding and upload.")
        print(f"  {len(chunks)} chunks ready. Run without --dry-run to embed and upload.")
        return

    # Step 5: Embed + Upload
    print("\n[5/5] Embedding and uploading to Pinecone...")
    from ingestion.embedder import embed_chunks
    from ingestion.uploader import upload_to_pinecone

    records = embed_chunks(chunks)
    upload_to_pinecone(records, index_name=index_name, codebase=name)

    print(f"\n  Ingestion complete! {len(records)} vectors indexed for '{name}'.")


def main():
    parser = argparse.ArgumentParser(description="Ingest a COBOL codebase into Pinecone.")
    parser.add_argument("codebase_dir", help="Root directory of the COBOL codebase")
    parser.add_argument("--name", required=True, help="Codebase name (used as identifier)")
    parser.add_argument("--index", default=None, help=f"Pinecone index name (default: {PINECONE_INDEX_NAME})")
    parser.add_argument("--dry-run", action="store_true", help="Parse and cache without calling APIs")
    args = parser.parse_args()

    src_path = str(Path(args.codebase_dir).resolve())
    register_codebase(args.name, src_path, index=args.index)
    ingest_codebase(args.name, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
