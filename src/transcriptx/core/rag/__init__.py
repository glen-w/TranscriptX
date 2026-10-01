"""
Grounded RAG for TranscriptX: LanceDB-backed Q&A over transcript segments.

Port of patterns from Paperful RAG, adapted for transcript chunks with
timestamped citations. Opt-in and default OFF via TRANSCRIPTX_RAG_ENABLED.
"""

from .answer import AnswerStream
from .api import RagAPI
from .chunk import Chunk, chunk_segments
from .embed import OllamaEmbedder
from .index import Index, IndexMissing
from .ledger import Ledger
from .prompt import Source, build_context, build_prompt
from .retrieve import Hit, search
from .settings import RagSettings

__all__ = [
    "RagAPI",
    "RagSettings",
    "Chunk",
    "chunk_segments",
    "Index",
    "IndexMissing",
    "Ledger",
    "Hit",
    "search",
    "Source",
    "build_context",
    "build_prompt",
    "AnswerStream",
    "OllamaEmbedder",
]
