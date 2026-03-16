"""Central configuration for the COBOL RAG pipeline."""

import os
from pathlib import Path
from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")
load_dotenv(_project_root / "pipeline" / ".env")


def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise ValueError(f"Missing required environment variable: {key}. Check your .env file.")
    return val


def _optional_env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


OPENAI_API_KEY: str = _optional_env("OPENAI_API_KEY")
PINECONE_API_KEY: str = _optional_env("PINECONE_API_KEY")
GOOGLE_API_KEY: str = _optional_env("GOOGLE_API_KEY")
COHERE_API_KEY: str = _optional_env("COHERE_API_KEY")
LANGSMITH_API_KEY: str = _optional_env("LANGSMITH_API_KEY")

PINECONE_INDEX_NAME: str = _optional_env("PINECONE_INDEX_NAME", "masquerade-cobol")
LANGCHAIN_TRACING_V2: str = _optional_env("LANGCHAIN_TRACING_V2", "true")
LANGCHAIN_PROJECT: str = _optional_env("LANGCHAIN_PROJECT", "masquerade-cobol")

EMBEDDING_MODEL: str = "text-embedding-3-small"
EMBEDDING_DIMENSIONS: int = 1536
LLM_MODEL: str = "gemini-2.5-flash"

CHUNK_MAX_TOKENS: int = 1000
CHUNK_TARGET_TOKENS: int = 600
CHUNK_OVERLAP_RATIO: float = 0.15

TOP_K: int = 10
EMBEDDING_BATCH_SIZE: int = 100
PINECONE_UPSERT_BATCH: int = 100

DATA_DIR: str = str(_project_root / "pipeline" / "data")
CHUNKS_CACHE_PATH: str = str(Path(DATA_DIR) / "chunks_cache.json")
UPLOAD_CHECKPOINT_PATH: str = str(Path(DATA_DIR) / "upload_checkpoint.txt")

COBOL_EXTENSIONS: set = {".cbl", ".cob", ".CBL", ".COB"}
COPYBOOK_EXTENSIONS: set = {".cpy", ".CPY"}
JCL_EXTENSIONS: set = {".jcl", ".JCL"}

CODEBASES: dict = {}


def register_codebase(name: str, src_path: str, index: str = None, skip_dirs: set = None):
    """Register a COBOL codebase for ingestion and retrieval."""
    CODEBASES[name] = {
        "src_path": src_path,
        "index": index or PINECONE_INDEX_NAME,
        "language": "cobol",
        "extensions": COBOL_EXTENSIONS | COPYBOOK_EXTENSIONS | JCL_EXTENSIONS,
        "skip_dirs": skip_dirs or {".git", "_analysis", "__pycache__", "data"},
    }
