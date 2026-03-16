"""Data models for the COBOL RAG pipeline."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Chunk:
    """A parsed chunk of COBOL source code, ready for embedding."""
    id: str
    text: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str       # "identification", "data", "procedure", "paragraph", "copybook", "jcl"
    program_name: str
    paragraph_name: str   # populated when chunk is a specific paragraph
    language: str         # "cobol", "copybook", "jcl"
    codebase: str
    calls: List[str] = field(default_factory=list)      # inter-program calls from this chunk
    performs: List[str] = field(default_factory=list)    # PERFORM targets from this chunk
    copybooks: List[str] = field(default_factory=list)  # COPY references from this chunk
    cics_ops: List[str] = field(default_factory=list)   # CICS operations in this chunk
    # Graph-enriched fields (populated when analysis graph is available)
    called_by: List[str] = field(default_factory=list)   # programs that call this program
    calls_to: List[str] = field(default_factory=list)    # programs this program calls (graph-level, not chunk-local)
    shared_with: List[str] = field(default_factory=list) # programs sharing copybooks with this program
    hub_score: float = 0.0                                # degree centrality in the call graph
    # Data flow enrichment
    data_flow_fields: List[str] = field(default_factory=list)  # field names involved in data flows in this chunk
    data_flow_count: int = 0                                    # number of data flow statements in this chunk


@dataclass
class RetrievedChunk:
    """A chunk returned from Pinecone with similarity score."""
    chunk: Chunk
    score: float


@dataclass
class QueryResult:
    """Complete query response."""
    query: str
    answer: str
    sources: List[RetrievedChunk]
    latency_ms: float
