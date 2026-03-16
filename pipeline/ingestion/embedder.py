"""OpenAI batch embedding with exponential backoff."""

import sys
import time
from pathlib import Path
from typing import Dict, List

from langchain_openai import OpenAIEmbeddings

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag_config import EMBEDDING_BATCH_SIZE, EMBEDDING_MODEL, OPENAI_API_KEY
from rag_models import Chunk


def _create_embeddings_client() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=EMBEDDING_MODEL, openai_api_key=OPENAI_API_KEY)


def _embed_batch_with_backoff(
    client: OpenAIEmbeddings, texts: List[str], max_retries: int = 5
) -> List[List[float]]:
    for attempt in range(max_retries):
        try:
            return client.embed_documents(texts)
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                wait_time = min(2 ** attempt, 32)
                print(f"  Rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                raise
    raise RuntimeError(f"Failed to embed batch after {max_retries} retries")


def embed_chunks(
    chunks: List[Chunk], batch_size: int = EMBEDDING_BATCH_SIZE
) -> List[Dict]:
    """Embed chunks using OpenAI text-embedding-3-small.

    Returns list of dicts ready for Pinecone upsert:
    {"id": str, "values": list[float], "metadata": dict}
    """
    client = _create_embeddings_client()
    records: List[Dict] = []
    total_batches = (len(chunks) + batch_size - 1) // batch_size

    for batch_idx in range(0, len(chunks), batch_size):
        batch = chunks[batch_idx : batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1
        print(f"  Embedding batch {batch_num}/{total_batches} ({len(batch)} chunks)...")

        texts = [chunk.text for chunk in batch]
        vectors = _embed_batch_with_backoff(client, texts)

        for chunk, vector in zip(batch, vectors):
            records.append({
                "id": chunk.id,
                "values": vector,
                "metadata": {
                    "text": chunk.text[:39000],  # Pinecone metadata limit
                    "file_path": chunk.file_path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "chunk_type": chunk.chunk_type,
                    "program_name": chunk.program_name,
                    "paragraph_name": chunk.paragraph_name,
                    "language": chunk.language,
                    "codebase": chunk.codebase,
                    "calls": ",".join(chunk.calls[:10]),
                    "performs": ",".join(chunk.performs[:10]),
                    "copybooks": ",".join(chunk.copybooks[:10]),
                    "cics_ops": ",".join(chunk.cics_ops[:10]),
                    "called_by": ",".join(chunk.called_by[:10]),
                    "calls_to": ",".join(chunk.calls_to[:10]),
                    "shared_with": ",".join(chunk.shared_with[:10]),
                    "hub_score": str(round(chunk.hub_score, 2)),
                    "data_flow_fields": ",".join(chunk.data_flow_fields[:20]),
                    "data_flow_count": str(chunk.data_flow_count),
                },
            })

    return records
