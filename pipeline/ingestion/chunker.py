"""
COBOL-aware chunking using structural parser output.

Unlike LegacyLens's regex-only approach, this uses the full structural parser
to split at division/section/paragraph boundaries and enriches each chunk
with graph context (calls, performs, copybooks, CICS ops).

Split hierarchy (high to low priority):
  1. DIVISION boundaries (IDENTIFICATION, ENVIRONMENT, DATA, PROCEDURE)
  2. SECTION boundaries within DATA (WORKING-STORAGE, LINKAGE, FILE, etc.)
  3. Paragraph boundaries within PROCEDURE DIVISION
  4. Long comment separator lines (* * * * or ------)
  5. Hard line-based split as fallback
"""

import hashlib
import re
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional

import tiktoken

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag_config import CHUNK_MAX_TOKENS, CHUNK_OVERLAP_RATIO, CHUNK_TARGET_TOKENS
from rag_models import Chunk
from cobol_parser import parse_cobol_file, CobolProgram
from graph_context import GraphIndex

_encoder = tiktoken.get_encoding("cl100k_base")

COBOL_SPLIT_PATTERNS = re.compile(
    r"|".join([
        r"^\s{6}\s+(IDENTIFICATION|ID)\s+DIVISION",
        r"^\s{6}\s+ENVIRONMENT\s+DIVISION",
        r"^\s{6}\s+DATA\s+DIVISION",
        r"^\s{6}\s+PROCEDURE\s+DIVISION",
        r"^\s{6}\s+WORKING-STORAGE\s+SECTION",
        r"^\s{6}\s+LINKAGE\s+SECTION",
        r"^\s{6}\s+FILE\s+SECTION",
        r"^\s{6}\s+LOCAL-STORAGE\s+SECTION",
        r"^\s{6}\s+COMMUNICATION\s+SECTION",
        r"^\s{6}\s+INPUT-OUTPUT\s+SECTION",
        r"^\s{6}\s+CONFIGURATION\s+SECTION",
        r"^\s{6}\*[\*\-=]{20,}",  # long comment separators
    ]),
    re.IGNORECASE | re.MULTILINE,
)

_RE_PARAGRAPH_HEADER = re.compile(r"^\s{7}\s*([A-Z0-9][\w-]+)\s*\.\s*$", re.IGNORECASE)

_COBOL_RESERVED_PARA = {
    'PERFORM', 'MOVE', 'COMPUTE', 'IF', 'ELSE', 'END-IF', 'EVALUATE', 'WHEN',
    'ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE', 'DISPLAY', 'ACCEPT', 'CALL',
    'STOP', 'GOBACK', 'GO', 'EXIT', 'CONTINUE', 'INITIALIZE', 'STRING',
    'UNSTRING', 'INSPECT', 'SEARCH', 'READ', 'WRITE', 'REWRITE', 'DELETE',
    'OPEN', 'CLOSE', 'START', 'RETURN', 'SORT', 'MERGE', 'SET', 'EXEC',
    'END-EXEC', 'COPY', 'SECTION', 'DIVISION',
}


def _count_tokens(text: str) -> int:
    return len(_encoder.encode(text))


def _generate_chunk_id(file_path: str, start_line: int) -> str:
    raw = f"{file_path}:{start_line}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _find_structural_boundaries(lines: List[str]) -> List[int]:
    """Find split points using COBOL structural patterns and paragraph headers."""
    boundaries = [0]
    in_procedure = False

    for i, line in enumerate(lines):
        if i == 0:
            continue

        upper = line.upper()
        if 'PROCEDURE' in upper and 'DIVISION' in upper:
            in_procedure = True

        if COBOL_SPLIT_PATTERNS.match(line):
            boundaries.append(i)
            continue

        if in_procedure:
            m = _RE_PARAGRAPH_HEADER.match(line)
            if m:
                name = m.group(1).upper()
                if name not in _COBOL_RESERVED_PARA and not name.endswith('DIVISION') and not name.endswith('SECTION'):
                    boundaries.append(i)

    return sorted(set(boundaries))


def _merge_small_segments(segments: List[Dict], target_tokens: int) -> List[Dict]:
    """Merge adjacent small segments up to target token count."""
    if not segments:
        return segments

    merged: List[Dict] = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        combined_tokens = _count_tokens(prev["text"] + seg["text"])
        if combined_tokens <= target_tokens:
            prev["text"] += seg["text"]
            prev["end_line"] = seg["end_line"]
            prev["paragraph_names"].extend(seg["paragraph_names"])
        else:
            merged.append(seg)
    return merged


def _hard_split(
    text: str, base_line: int, rel_path: str, chunk_type: str,
    program_name: str, language: str, codebase: str,
) -> List[Chunk]:
    """Line-based splitting for segments exceeding max tokens."""
    lines = text.splitlines(keepends=True)
    chunks: List[Chunk] = []
    current_lines: List[str] = []
    current_start = base_line

    for line in lines:
        current_lines.append(line)
        if _count_tokens("".join(current_lines)) >= CHUNK_TARGET_TOKENS:
            chunks.append(Chunk(
                id=_generate_chunk_id(rel_path, current_start),
                text="".join(current_lines),
                file_path=rel_path,
                start_line=current_start,
                end_line=current_start + len(current_lines) - 1,
                chunk_type=chunk_type,
                program_name=program_name,
                paragraph_name="",
                language=language,
                codebase=codebase,
            ))
            current_start = current_start + len(current_lines)
            current_lines = []

    if current_lines:
        chunks.append(Chunk(
            id=_generate_chunk_id(rel_path, current_start),
            text="".join(current_lines),
            file_path=rel_path,
            start_line=current_start,
            end_line=current_start + len(current_lines) - 1,
            chunk_type=chunk_type,
            program_name=program_name,
            paragraph_name="",
            language=language,
            codebase=codebase,
        ))

    return chunks


def _enrich_chunk_metadata(chunk: Chunk, parsed: CobolProgram) -> Chunk:
    """Enrich chunk with graph context from the parsed program."""
    for para in parsed.paragraphs:
        if para.span.start_line >= chunk.start_line and para.span.start_line <= chunk.end_line:
            if not chunk.paragraph_name:
                chunk.paragraph_name = para.name
            chunk.performs.extend(pt.target_paragraph for pt in para.performs)
            chunk.calls.extend(ct.target_program for ct in para.calls)
            chunk.cics_ops.extend(c.operation for c in para.cics_ops)

    for cs in parsed.copy_statements:
        if cs.span.start_line >= chunk.start_line and cs.span.start_line <= chunk.end_line:
            chunk.copybooks.append(cs.copybook_name)

    chunk.performs = list(dict.fromkeys(chunk.performs))
    chunk.calls = list(dict.fromkeys(chunk.calls))
    chunk.cics_ops = list(dict.fromkeys(chunk.cics_ops))
    chunk.copybooks = list(dict.fromkeys(chunk.copybooks))

    flow_fields = set()
    flow_count = 0
    for para in parsed.paragraphs:
        for df in para.data_flows:
            if chunk.start_line <= df.span.start_line <= chunk.end_line:
                flow_count += 1
                for t in df.targets:
                    flow_fields.add(t)
                for s in df.sources:
                    flow_fields.add(s)
    chunk.data_flow_fields = list(flow_fields)[:30]
    chunk.data_flow_count = flow_count

    return chunk


def _enrich_chunk_from_graph(chunk: Chunk, graph: GraphIndex) -> Chunk:
    """Enrich chunk with cross-program graph context (callers, callees, centrality)."""
    if not chunk.program_name:
        return chunk

    enrichment = graph.enrichment_for(chunk.program_name)
    chunk.called_by = enrichment["callers"]
    chunk.calls_to = enrichment["callees"]
    chunk.shared_with = enrichment["programs_sharing_copybooks"]
    chunk.hub_score = enrichment["hub_score"]

    return chunk


def chunk_cobol_file(
    file_path: str,
    rel_path: str,
    content: str,
    category: str,
    codebase: str,
    parsed: Optional[CobolProgram] = None,
) -> List[Chunk]:
    """Chunk a COBOL source file using structural boundaries.

    If `parsed` is provided, enriches chunks with graph metadata.
    Otherwise, parses the file on the fly.
    """
    if not content.strip():
        return []

    lines = content.splitlines(keepends=True)
    language = "cobol"

    if parsed is None:
        try:
            parsed = parse_cobol_file(Path(file_path))
        except Exception:
            parsed = None

    program_name = parsed.program_id if parsed else Path(file_path).stem

    token_count = _count_tokens(content)
    if token_count <= CHUNK_MAX_TOKENS:
        chunk = Chunk(
            id=_generate_chunk_id(rel_path, 1),
            text=content,
            file_path=rel_path,
            start_line=1,
            end_line=len(lines),
            chunk_type=category,
            program_name=program_name,
            paragraph_name="",
            language=language,
            codebase=codebase,
        )
        if parsed:
            _enrich_chunk_metadata(chunk, parsed)
        return [chunk]

    boundaries = _find_structural_boundaries(lines)

    segments: List[Dict] = []
    for i in range(len(boundaries)):
        start = boundaries[i]
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(lines)
        text = "".join(lines[start:end])

        para_names = []
        for line in lines[start:end]:
            m = _RE_PARAGRAPH_HEADER.match(line)
            if m and m.group(1).upper() not in _COBOL_RESERVED_PARA:
                para_names.append(m.group(1).upper())

        segments.append({
            "text": text,
            "start_line": start + 1,
            "end_line": end,
            "paragraph_names": para_names,
        })

    segments = _merge_small_segments(segments, CHUNK_TARGET_TOKENS)

    overlap_lines = max(3, int(len(lines) * CHUNK_OVERLAP_RATIO))
    chunks: List[Chunk] = []

    for i, seg in enumerate(segments):
        text = seg["text"]

        if i > 0 and overlap_lines > 0:
            prev_text = segments[i - 1]["text"]
            prev_lines = prev_text.splitlines(keepends=True)
            overlap_text = "".join(prev_lines[-overlap_lines:])
            text = overlap_text + text

        if _count_tokens(text) > CHUNK_MAX_TOKENS:
            sub_chunks = _hard_split(
                text, seg["start_line"], rel_path, category,
                program_name, language, codebase,
            )
            for sc in sub_chunks:
                if parsed:
                    _enrich_chunk_metadata(sc, parsed)
            chunks.extend(sub_chunks)
        else:
            para_name = seg["paragraph_names"][0] if seg["paragraph_names"] else ""
            chunk = Chunk(
                id=_generate_chunk_id(rel_path, seg["start_line"]),
                text=text,
                file_path=rel_path,
                start_line=seg["start_line"],
                end_line=seg["end_line"],
                chunk_type="paragraph" if para_name else category,
                program_name=program_name,
                paragraph_name=para_name,
                language=language,
                codebase=codebase,
            )
            if parsed:
                _enrich_chunk_metadata(chunk, parsed)
            chunks.append(chunk)

    return chunks


def chunk_copybook_file(
    file_path: str, rel_path: str, content: str, codebase: str,
) -> List[Chunk]:
    """Chunk a copybook file. Most are small enough for a single chunk."""
    if not content.strip():
        return []

    name = Path(file_path).stem
    line_count = content.count("\n") + 1

    if _count_tokens(content) <= CHUNK_MAX_TOKENS:
        return [Chunk(
            id=_generate_chunk_id(rel_path, 1),
            text=content,
            file_path=rel_path,
            start_line=1,
            end_line=line_count,
            chunk_type="copybook",
            program_name="",
            paragraph_name="",
            language="copybook",
            codebase=codebase,
        )]

    return _hard_split(
        content, 1, rel_path, "copybook", name, "copybook", codebase,
    )


def chunk_jcl_file(
    file_path: str, rel_path: str, content: str, codebase: str,
) -> List[Chunk]:
    """Chunk a JCL file. Split at job/step boundaries."""
    if not content.strip():
        return []

    name = Path(file_path).stem
    lines = content.splitlines(keepends=True)

    if _count_tokens(content) <= CHUNK_MAX_TOKENS:
        return [Chunk(
            id=_generate_chunk_id(rel_path, 1),
            text=content,
            file_path=rel_path,
            start_line=1,
            end_line=len(lines),
            chunk_type="jcl",
            program_name=name,
            paragraph_name="",
            language="jcl",
            codebase=codebase,
        )]

    # Split at JCL step boundaries: //stepname EXEC
    boundaries = [0]
    for i, line in enumerate(lines):
        if i > 0 and re.match(r'^//\w+\s+EXEC\s', line, re.IGNORECASE):
            boundaries.append(i)

    segments = []
    for i in range(len(boundaries)):
        start = boundaries[i]
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(lines)
        text = "".join(lines[start:end])
        segments.append({"text": text, "start_line": start + 1, "end_line": end, "paragraph_names": []})

    segments = _merge_small_segments(segments, CHUNK_TARGET_TOKENS)

    return [
        Chunk(
            id=_generate_chunk_id(rel_path, seg["start_line"]),
            text=seg["text"],
            file_path=rel_path,
            start_line=seg["start_line"],
            end_line=seg["end_line"],
            chunk_type="jcl",
            program_name=name,
            paragraph_name="",
            language="jcl",
            codebase=codebase,
        )
        for seg in segments
    ]


def chunk_all_files(
    files: List[Dict[str, str]],
    parsed_programs: Optional[Dict[str, CobolProgram]] = None,
    graph: Optional[GraphIndex] = None,
) -> List[Chunk]:
    """Process all discovered files into chunks.

    If parsed_programs is provided (keyed by file path), uses pre-parsed
    structural info for richer metadata.

    If graph is provided (a GraphIndex loaded from _analysis/), enriches
    each chunk with cross-program context: callers, callees, shared
    copybook peers, and centrality scores.
    """
    all_chunks: List[Chunk] = []

    for file_info in files:
        path = file_info["path"]
        rel_path = file_info["rel_path"]
        category = file_info["category"]
        ext = file_info["extension"].lower()
        codebase = file_info.get("codebase", "unknown")

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, IOError) as e:
            print(f"  Warning: Could not read {rel_path}: {e}")
            continue

        parsed = parsed_programs.get(path) if parsed_programs else None

        if ext in (".cbl", ".cob"):
            chunks = chunk_cobol_file(path, rel_path, content, category, codebase, parsed)
        elif ext == ".cpy":
            chunks = chunk_copybook_file(path, rel_path, content, codebase)
        elif ext == ".jcl":
            chunks = chunk_jcl_file(path, rel_path, content, codebase)
        else:
            continue

        if graph:
            for chunk in chunks:
                _enrich_chunk_from_graph(chunk, graph)

        all_chunks.extend(chunks)

    return all_chunks
