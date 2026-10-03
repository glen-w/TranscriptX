"""Best-effort RAG index cleanup when a library transcript is deleted."""

from __future__ import annotations

import os
from pathlib import Path

from transcriptx.core.utils.logger import get_logger

from .flags import ollama_base_url_from_env, rag_enabled_from_env
from .index import Index, IndexMissing, RagUnavailable, session_where
from .settings import RagSettings

logger = get_logger()


def _same_path(left: str | Path, right: str | Path) -> bool:
    try:
        return Path(left).expanduser().resolve() == Path(right).expanduser().resolve()
    except OSError:
        return str(left) == str(right)


def _slugs_for_path(transcript_path: Path) -> list[str]:
    try:
        from transcriptx.core.utils.slug_manager import load_index
    except Exception:
        return []
    try:
        extra = str(transcript_path.expanduser().resolve(strict=False))
    except OSError:
        extra = str(transcript_path)
    try:
        index = load_index()
    except Exception:
        return []
    transcripts = index.get("transcripts", {}) or {}
    slug_to_key = index.get("slug_to_key", {}) or {}
    slugs: list[str] = []
    for slug, key in slug_to_key.items():
        entry = transcripts.get(key)
        if not isinstance(entry, dict):
            continue
        source = entry.get("source_path")
        if source and _same_path(source, extra):
            slugs.append(str(slug))
    return slugs


def purge_transcript_from_index(transcript_path: Path) -> None:
    """Drop indexed chunks for this library file. Never raises."""
    if not rag_enabled_from_env():
        return
    try:
        data_dir = Path(os.environ.get("TRANSCRIPTX_DATA_DIR", "./data"))
        settings = RagSettings(
            data_dir=data_dir,
            enabled=True,
            embed_model=os.environ.get(
                "TRANSCRIPTX_RAG_EMBED_MODEL", "nomic-embed-text"
            ),
            ollama_base_url=ollama_base_url_from_env(),
        )
        slugs = _slugs_for_path(transcript_path)
        if not slugs:
            return
        index = Index.open(settings, create=False)
        for slug in slugs:
            index.delete_where(session_where(slug))
    except (IndexMissing, RagUnavailable):
        return
    except Exception as exc:
        logger.warning("RAG purge skipped for %s: %s", transcript_path, exc)
