"""
Grounded RAG for TranscriptX: LanceDB-backed Q&A over transcript segments.

Port of patterns from Paperful RAG, adapted for transcript chunks with
timestamped citations. Opt-in and default OFF via TRANSCRIPTX_RAG_ENABLED.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "RagAPI",
    "RagSettings",
    "RagScopeMissing",
    "RagUnavailable",
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
    "parse_rag_enabled",
    "rag_enabled_from_env",
]

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "AnswerStream": (".answer", "AnswerStream"),
    "RagAPI": (".api", "RagAPI"),
    "Chunk": (".chunk", "Chunk"),
    "chunk_segments": (".chunk", "chunk_segments"),
    "OllamaEmbedder": (".embed", "OllamaEmbedder"),
    "parse_rag_enabled": (".flags", "parse_rag_enabled"),
    "rag_enabled_from_env": (".flags", "rag_enabled_from_env"),
    "Index": (".index", "Index"),
    "IndexMissing": (".index", "IndexMissing"),
    "RagScopeMissing": (".index", "RagScopeMissing"),
    "RagUnavailable": (".index", "RagUnavailable"),
    "Ledger": (".ledger", "Ledger"),
    "Source": (".prompt", "Source"),
    "build_context": (".prompt", "build_context"),
    "build_prompt": (".prompt", "build_prompt"),
    "Hit": (".retrieve", "Hit"),
    "search": (".retrieve", "search"),
    "RagSettings": (".settings", "RagSettings"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = _LAZY_EXPORTS[name]
    from importlib import import_module

    return getattr(import_module(module_name, __name__), attr)


if TYPE_CHECKING:
    from .answer import AnswerStream
    from .api import RagAPI
    from .chunk import Chunk, chunk_segments
    from .embed import OllamaEmbedder
    from .flags import parse_rag_enabled, rag_enabled_from_env
    from .index import Index, IndexMissing, RagScopeMissing, RagUnavailable
    from .ledger import Ledger
    from .prompt import Source, build_context, build_prompt
    from .retrieve import Hit, search
    from .settings import RagSettings
