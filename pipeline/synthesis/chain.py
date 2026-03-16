"""LCEL chain: embed query -> search Pinecone -> graph expand -> dedup -> rerank -> format -> LLM."""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Generator, List, Optional, Tuple

import cohere
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag_config import (
    CODEBASES,
    COHERE_API_KEY,
    EMBEDDING_MODEL,
    GOOGLE_API_KEY,
    LLM_MODEL,
    OPENAI_API_KEY,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    TOP_K,
    DATA_DIR,
)
from rag_models import Chunk, QueryResult, RetrievedChunk
from graph_context import GraphIndex
from synthesis.prompts import RAG_PROMPT_TEMPLATE

_embeddings = None
_pinecone_indexes = None
_llm = None
_prompt = None
_cohere_client = None
_graph_indexes: dict[str, GraphIndex] = {}

_embedding_cache: dict = {}
_CACHE_MAX_SIZE = 256
_CACHE_FILE = os.path.join(DATA_DIR, "embedding_cache.json")

MAX_CONTEXT_CHARS = 12000

_project_root = Path(__file__).resolve().parent.parent.parent
_test_codebases = _project_root / "test-codebases"


def _load_embedding_cache():
    global _embedding_cache
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r") as f:
                _embedding_cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            _embedding_cache = {}


def _save_embedding_cache():
    os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump(_embedding_cache, f)


_bg_executor = ThreadPoolExecutor(max_workers=1)


def _save_embedding_cache_async():
    """Write embedding cache to disk without blocking the query path."""
    cache_snapshot = dict(_embedding_cache)
    _bg_executor.submit(_write_cache_snapshot, cache_snapshot)


def _write_cache_snapshot(snapshot: dict):
    try:
        os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
        with open(_CACHE_FILE, "w") as f:
            json.dump(snapshot, f)
    except OSError:
        pass


def _normalize_query(q: str) -> str:
    return " ".join(q.lower().split())


def _get_cached_embedding(query: str) -> list | None:
    if not _embedding_cache:
        _load_embedding_cache()
    return _embedding_cache.get(_normalize_query(query))


def _put_cached_embedding(query: str, vector: list):
    key = _normalize_query(query)
    if len(_embedding_cache) >= _CACHE_MAX_SIZE:
        oldest = next(iter(_embedding_cache))
        del _embedding_cache[oldest]
    _embedding_cache[key] = vector
    _save_embedding_cache_async()


def _format_context(docs: List[Document]) -> str:
    """Format retrieved documents with COBOL-specific metadata headers."""
    formatted = []
    total_chars = 0
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        file_path = meta.get("file_path", "unknown")
        start = meta.get("start_line", "?")
        end = meta.get("end_line", "?")
        chunk_type = meta.get("chunk_type", "")
        program = meta.get("program_name", "")
        paragraph = meta.get("paragraph_name", "")
        codebase = meta.get("codebase", "")
        calls = meta.get("calls", "")
        performs = meta.get("performs", "")
        copybooks = meta.get("copybooks", "")
        cics = meta.get("cics_ops", "")
        called_by = meta.get("called_by", "")
        calls_to = meta.get("calls_to", "")
        shared_with = meta.get("shared_with", "")
        graph_expanded = meta.get("_graph_expanded", "")
        copybook_inlined = meta.get("_copybook_inlined", "")

        content = doc.page_content
        if total_chars + len(content) > MAX_CONTEXT_CHARS and formatted:
            content = content[:max(500, MAX_CONTEXT_CHARS - total_chars)] + "\n[...truncated]"

        header = f"[Source {i}]"
        if copybook_inlined:
            header += " [referenced-copybook]"
        elif graph_expanded:
            header += " [graph-related]"
        if codebase:
            header += f" ({codebase})"
        header += f" {file_path}:{start}-{end}"
        if program:
            header += f" program={program}"
        if paragraph:
            header += f" paragraph={paragraph}"
        if chunk_type:
            header += f" [{chunk_type}]"

        annotations = []
        if calls:
            annotations.append(f"CALLS: {calls}")
        if performs:
            annotations.append(f"PERFORMS: {performs}")
        if copybooks:
            annotations.append(f"COPIES: {copybooks}")
        if cics:
            annotations.append(f"CICS: {cics}")
        if called_by:
            annotations.append(f"CALLED_BY: {called_by}")
        if calls_to:
            annotations.append(f"CALLS_TO: {calls_to}")
        if shared_with:
            annotations.append(f"SHARES_COPYBOOKS_WITH: {shared_with}")

        data_flow_fields = meta.get("data_flow_fields", "")
        data_flow_count = meta.get("data_flow_count", "0")
        if data_flow_fields:
            annotations.append(f"DATA_FIELDS: {data_flow_fields}")
        if data_flow_count and data_flow_count != "0":
            annotations.append(f"DATA_FLOWS: {data_flow_count}")

        block = f"{header}\n"
        if annotations:
            block += f"  {' | '.join(annotations)}\n"
        block += f"```cobol\n{content}\n```"

        formatted.append(block)
        total_chars += len(content)

    return "\n\n".join(formatted)


def _get_embeddings() -> OpenAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL, openai_api_key=OPENAI_API_KEY)
    return _embeddings


def _get_pinecone_indexes() -> dict:
    global _pinecone_indexes
    if _pinecone_indexes is None:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        _pinecone_indexes = {}

        seen_indexes = set()
        for cb_name, cb_config in CODEBASES.items():
            idx_name = cb_config["index"]
            if idx_name not in seen_indexes:
                _pinecone_indexes[cb_name] = pc.Index(idx_name)
                seen_indexes.add(idx_name)

        if not _pinecone_indexes:
            _pinecone_indexes["default"] = pc.Index(PINECONE_INDEX_NAME)

    return _pinecone_indexes


def _get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        _llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=0.0,
            thinking_budget=0,
        )
    return _llm


def _get_prompt() -> ChatPromptTemplate:
    global _prompt
    if _prompt is None:
        _prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)
    return _prompt


def _get_cohere_client():
    global _cohere_client
    if _cohere_client is None and COHERE_API_KEY:
        _cohere_client = cohere.ClientV2(api_key=COHERE_API_KEY)
    return _cohere_client


def _get_graph(codebase: str) -> Optional[GraphIndex]:
    """Load graph index for a codebase from its _analysis/ directory."""
    if codebase in _graph_indexes:
        return _graph_indexes[codebase]

    cb_config = CODEBASES.get(codebase, {})
    src_path = cb_config.get("src_path", "")
    if src_path:
        analysis_dir = Path(src_path) / "_analysis"
    else:
        analysis_dir = _test_codebases / codebase / "_analysis"

    if analysis_dir.exists() and (analysis_dir / "graph.json").exists():
        try:
            gi = GraphIndex(str(analysis_dir))
            _graph_indexes[codebase] = gi
            return gi
        except Exception:
            pass
    return None


def get_graph_for_codebase(codebase: str) -> Optional[GraphIndex]:
    """Public accessor for CLI commands that need graph data."""
    return _get_graph(codebase)


def _rerank(
    question: str, docs_with_scores: List[Tuple[Document, float]], top_n: int = 5
) -> List[Tuple[Document, float]]:
    client = _get_cohere_client()
    if client is None:
        return docs_with_scores[:top_n]

    try:
        texts = [doc.page_content for doc, _ in docs_with_scores]
        response = client.rerank(
            model="rerank-v3.5",
            query=question,
            documents=texts,
            top_n=top_n,
        )
        return [(docs_with_scores[r.index][0], r.relevance_score) for r in response.results]
    except Exception as e:
        print(f"  Reranking failed, using vector scores: {e}")
        return docs_with_scores[:top_n]


def _deduplicate_by_file(
    docs_with_scores: List[Tuple[Document, float]], limit: int = 5, min_per_codebase: int = 2
) -> List[Tuple[Document, float]]:
    by_codebase: dict = {}
    for doc, score in docs_with_scores:
        cb = doc.metadata.get("codebase", "unknown")
        fp = doc.metadata.get("file_path", "")
        if cb not in by_codebase:
            by_codebase[cb] = {}
        if fp not in by_codebase[cb]:
            by_codebase[cb][fp] = (doc, score)

    result = []
    remaining = []
    for cb, files in by_codebase.items():
        sorted_files = sorted(files.values(), key=lambda x: x[1], reverse=True)
        result.extend(sorted_files[:min_per_codebase])
        remaining.extend(sorted_files[min_per_codebase:])

    remaining.sort(key=lambda x: x[1], reverse=True)
    slots_left = limit - len(result)
    if slots_left > 0:
        result.extend(remaining[:slots_left])
    result.sort(key=lambda x: x[1], reverse=True)
    return result


def _pinecone_query_to_docs(results: dict, codebase: str = "") -> List[Tuple[Document, float]]:
    docs = []
    for match in results.get("matches", []):
        meta = match.get("metadata", {})
        text = meta.pop("text", "")
        if codebase and "codebase" not in meta:
            meta["codebase"] = codebase
        doc = Document(page_content=text, metadata=meta)
        docs.append((doc, match["score"]))
    return docs


def _query_single_index(index, vec, top_k, codebase_filter=None):
    kwargs = dict(vector=vec, top_k=top_k, include_metadata=True)
    if codebase_filter:
        kwargs["filter"] = {"codebase": {"$eq": codebase_filter}}
    return index.query(**kwargs)


def _expand_with_graph_neighbors(
    initial_results: List[Tuple[Document, float]],
    indexes: dict,
    vec: list,
    codebase_filter: str = None,
) -> List[Tuple[Document, float]]:
    """Expand initial retrieval results with graph neighbors.

    Identifies programs and copybooks from initial hits, walks the
    dependency graph 1 hop, and fetches all neighbor chunks in a
    single batched Pinecone query using $in filter.
    """
    if not initial_results:
        return initial_results

    hit_programs: set[str] = set()
    hit_copybooks: set[str] = set()
    hit_codebases: set[str] = set()

    for doc, _ in initial_results:
        meta = doc.metadata
        pgm = meta.get("program_name", "")
        if pgm:
            hit_programs.add(pgm.upper())
        cbs = meta.get("copybooks", "")
        if cbs:
            for cb in cbs.split(","):
                cb = cb.strip()
                if cb:
                    hit_copybooks.add(cb.upper())
        cb_name = meta.get("codebase", "")
        if cb_name:
            hit_codebases.add(cb_name)

    neighbor_programs: set[str] = set()
    for codebase in hit_codebases:
        graph = _get_graph(codebase)
        if not graph:
            continue
        expansion = graph.neighbors_for_retrieval(
            list(hit_programs), list(hit_copybooks), max_per_type=5
        )
        neighbor_programs.update(expansion["programs"])

    if not neighbor_programs:
        return initial_results

    existing_ids = {doc.metadata.get("id", "") for doc, _ in initial_results}
    neighbor_list = sorted(neighbor_programs)

    neighbor_docs: List[Tuple[Document, float]] = []

    def _fetch_neighbors(cb_name, idx):
        """Single batched Pinecone query for all neighbor programs."""
        pc_filter = {"program_name": {"$in": neighbor_list}}
        if codebase_filter:
            pc_filter["codebase"] = {"$eq": codebase_filter}
        try:
            return cb_name, idx.query(
                vector=vec,
                top_k=3 * len(neighbor_list),
                include_metadata=True,
                filter=pc_filter,
            )
        except Exception:
            return cb_name, {"matches": []}

    with ThreadPoolExecutor(max_workers=max(len(indexes), 1)) as executor:
        futures = [
            executor.submit(_fetch_neighbors, cb_name, idx)
            for cb_name, idx in indexes.items()
        ]
        for future in futures:
            cb_name, results = future.result()
            for match in results.get("matches", []):
                if match["id"] not in existing_ids:
                    meta = match.get("metadata", {})
                    text = meta.pop("text", "")
                    meta["_graph_expanded"] = "true"
                    if cb_name and "codebase" not in meta:
                        meta["codebase"] = cb_name
                    doc = Document(page_content=text, metadata=meta)
                    neighbor_docs.append((doc, match["score"] * 0.9))
                    existing_ids.add(match["id"])

    combined = initial_results + neighbor_docs
    combined.sort(key=lambda x: x[1], reverse=True)
    return combined


def _resolve_copybook_content(
    docs: List[Document],
    indexes: dict,
    codebase_filter: str = None,
    max_copybooks: int = 3,
) -> List[Document]:
    """Resolve COPY references in retrieved chunks by fetching copybook content.

    Collects copybook names from the retrieved chunks' metadata, fetches
    their content from Pinecone by metadata filter, and returns them as
    supplementary Document objects for the context window.
    """
    referenced_copybooks: set[str] = set()
    existing_files: set[str] = set()

    for doc in docs:
        meta = doc.metadata
        existing_files.add(meta.get("file_path", ""))
        cbs = meta.get("copybooks", "")
        if cbs:
            for cb in cbs.split(","):
                cb = cb.strip()
                if cb:
                    referenced_copybooks.add(cb)

    # Don't re-fetch copybooks already in the results
    copybooks_to_fetch = set()
    for cb in referenced_copybooks:
        already_present = any(
            cb.upper() in doc.metadata.get("file_path", "").upper()
            for doc in docs
        )
        if not already_present:
            copybooks_to_fetch.add(cb)

    if not copybooks_to_fetch:
        return []

    copybook_list = sorted(copybooks_to_fetch)[:max_copybooks * 2]

    copybook_docs: List[Document] = []
    for cb_name, idx in indexes.items():
        try:
            # Fetch copybook chunks by chunk_type and file name pattern
            results = idx.query(
                vector=[0.0] * 1536,  # dummy vector — we filter by metadata only
                top_k=max_copybooks * 2,
                include_metadata=True,
                filter={
                    "chunk_type": {"$eq": "copybook"},
                    **({"codebase": {"$eq": codebase_filter}} if codebase_filter else {}),
                },
            )
            for match in results.get("matches", []):
                meta = match.get("metadata", {})
                file_path = meta.get("file_path", "")
                file_stem = Path(file_path).stem.upper() if file_path else ""
                if file_stem in {cb.upper() for cb in copybook_list}:
                    text = meta.pop("text", "")
                    meta["_copybook_inlined"] = "true"
                    doc = Document(page_content=text, metadata=meta)
                    copybook_docs.append(doc)
                    copybooks_to_fetch.discard(file_stem)
        except Exception:
            continue

    return copybook_docs[:max_copybooks]


def _retrieve_and_prepare(question: str, codebase_filter: str = None):
    t_start = time.perf_counter()

    indexes = _get_pinecone_indexes()
    t_init = time.perf_counter()

    vec = _get_cached_embedding(question)
    if vec is None:
        vec = _get_embeddings().embed_query(question)
        _put_cached_embedding(question, vec)

    with ThreadPoolExecutor(max_workers=max(len(indexes), 1)) as executor:
        futures = {
            cb_name: executor.submit(_query_single_index, idx, vec, TOP_K * 2, codebase_filter)
            for cb_name, idx in indexes.items()
        }
        all_raw = {cb_name: future.result() for cb_name, future in futures.items()}

    raw_results = []
    for cb_name, results in all_raw.items():
        raw_results.extend(_pinecone_query_to_docs(results, codebase=cb_name))

    raw_results.sort(key=lambda x: x[1], reverse=True)
    t_search = time.perf_counter()

    expanded = _expand_with_graph_neighbors(raw_results, indexes, vec, codebase_filter)
    graph_added = len(expanded) - len(raw_results)
    t_graph = time.perf_counter()

    deduped = _deduplicate_by_file(expanded, limit=TOP_K)

    reranked = _rerank(question, deduped, top_n=9)
    t_rerank = time.perf_counter()

    docs = [doc for doc, _ in reranked]
    copybook_docs = _resolve_copybook_content(docs, indexes, codebase_filter)
    t_copybook = time.perf_counter()

    all_docs = docs + copybook_docs
    context = _format_context(all_docs)
    t_format = time.perf_counter()

    timing = {
        "init_ms": (t_init - t_start) * 1000,
        "embed_search_ms": (t_search - t_init) * 1000,
        "graph_expand_ms": (t_graph - t_search) * 1000,
        "graph_added": graph_added,
        "rerank_ms": (t_rerank - t_graph) * 1000,
        "copybook_ms": (t_copybook - t_rerank) * 1000,
        "copybooks_inlined": len(copybook_docs),
        "format_ms": (t_format - t_copybook) * 1000,
        "retrieve_total_ms": (t_format - t_start) * 1000,
    }
    return reranked, context, timing


def _split_meta(meta: dict, key: str) -> list[str]:
    val = meta.get(key, "")
    if not val:
        return []
    return [v.strip() for v in val.split(",") if v.strip()]


def _build_sources(reranked: List[Tuple[Document, float]]) -> List[RetrievedChunk]:
    sources = []
    for doc, score in reranked:
        meta = doc.metadata
        chunk = Chunk(
            id=meta.get("id", ""),
            text=doc.page_content,
            file_path=meta.get("file_path", ""),
            start_line=int(meta.get("start_line", 0)),
            end_line=int(meta.get("end_line", 0)),
            chunk_type=meta.get("chunk_type", ""),
            program_name=meta.get("program_name", ""),
            paragraph_name=meta.get("paragraph_name", ""),
            language=meta.get("language", ""),
            codebase=meta.get("codebase", ""),
            calls=_split_meta(meta, "calls"),
            performs=_split_meta(meta, "performs"),
            copybooks=_split_meta(meta, "copybooks"),
            cics_ops=_split_meta(meta, "cics_ops"),
            called_by=_split_meta(meta, "called_by"),
            calls_to=_split_meta(meta, "calls_to"),
            shared_with=_split_meta(meta, "shared_with"),
            hub_score=float(meta.get("hub_score", 0)),
        )
        sources.append(RetrievedChunk(chunk=chunk, score=score))
    return sources


def _print_timing(timing: dict):
    parts = []
    if timing.get("init_ms", 0) > 5:
        parts.append(f"init={timing['init_ms']:.0f}ms")
    parts.append(f"embed+search={timing['embed_search_ms']:.0f}ms")
    if timing.get("graph_added", 0) > 0:
        parts.append(f"graph={timing['graph_expand_ms']:.0f}ms(+{timing['graph_added']})")
    parts.append(f"rerank={timing['rerank_ms']:.0f}ms")
    if timing.get("copybooks_inlined", 0) > 0:
        parts.append(f"copybooks={timing['copybook_ms']:.0f}ms(+{timing['copybooks_inlined']})")
    parts.append(f"llm={timing['llm_ms']:.0f}ms")
    parts.append(f"total={timing['total_ms']:.0f}ms")
    print(f"\n  [timing] {' | '.join(parts)}")


def query(question: str, codebase_filter: str = None) -> QueryResult:
    start = time.perf_counter()
    reranked, context, timing = _retrieve_and_prepare(question, codebase_filter)

    chain = _get_prompt() | _get_llm() | StrOutputParser()
    t4 = time.perf_counter()
    answer = chain.invoke({"context": context, "question": question})
    t5 = time.perf_counter()

    timing["llm_ms"] = (t5 - t4) * 1000
    timing["chain_build_ms"] = (t4 - start) * 1000 - timing["retrieve_total_ms"]
    timing["total_ms"] = (time.perf_counter() - start) * 1000
    _print_timing(timing)

    return QueryResult(
        query=question,
        answer=answer,
        sources=_build_sources(reranked),
        latency_ms=timing["total_ms"],
    )


def query_stream(question: str, codebase_filter: str = None) -> Generator[str | QueryResult, None, None]:
    """Stream the RAG pipeline: yields tokens, then a final QueryResult."""
    start = time.perf_counter()
    reranked, context, timing = _retrieve_and_prepare(question, codebase_filter)

    chain = _get_prompt() | _get_llm() | StrOutputParser()
    t4 = time.perf_counter()
    answer_parts = []
    for token in chain.stream({"context": context, "question": question}):
        answer_parts.append(token)
        yield token
    t5 = time.perf_counter()

    timing["llm_ms"] = (t5 - t4) * 1000
    timing["chain_build_ms"] = (t4 - start) * 1000 - timing["retrieve_total_ms"]
    timing["total_ms"] = (time.perf_counter() - start) * 1000
    _print_timing(timing)

    yield QueryResult(
        query=question,
        answer="".join(answer_parts),
        sources=_build_sources(reranked),
        latency_ms=timing["total_ms"],
    )
