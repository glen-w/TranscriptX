"""Shared BERTopic model kwargs + privacy-safe provenance helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from transcriptx.core.analysis.bertopic.deps import redact_path_for_diagnostics
from transcriptx.core.utils.native_threads import limited_native_threads

__all__ = [
    "build_model_kwargs",
    "build_provenance",
    "limited_native_threads",
]


def build_model_kwargs(bertopic_cfg: Any) -> Dict[str, Any]:
    """Build BERTopic constructor kwargs from Pydantic-owned config.

    Always applies explicit config values (including ``False`` / numeric defaults)
    so env/file/UI overrides are not dropped by truthiness checks. ``label_words``
    is intentionally omitted — it is used only when shaping topic labels, not by
    the BERTopic constructor.
    """
    model_kwargs: Dict[str, Any] = {}
    if not bertopic_cfg:
        return model_kwargs

    embedding_model = getattr(bertopic_cfg, "embedding_model", None)
    if isinstance(embedding_model, str) and embedding_model.strip():
        model_kwargs["embedding_model"] = embedding_model.strip()

    min_topic_size = getattr(bertopic_cfg, "min_topic_size", None)
    if isinstance(min_topic_size, int) and min_topic_size >= 2:
        model_kwargs["min_topic_size"] = min_topic_size

    nr_topics = getattr(bertopic_cfg, "nr_topics", None)
    if isinstance(nr_topics, str):
        normalized = nr_topics.strip()
        if normalized.isdigit():
            model_kwargs["nr_topics"] = int(normalized)
        elif normalized:
            model_kwargs["nr_topics"] = normalized
    elif isinstance(nr_topics, int) and nr_topics >= 1:
        model_kwargs["nr_topics"] = nr_topics

    top_n_words = getattr(bertopic_cfg, "top_n_words", None)
    if isinstance(top_n_words, int) and top_n_words >= 1:
        model_kwargs["top_n_words"] = top_n_words

    if hasattr(bertopic_cfg, "calculate_probabilities"):
        model_kwargs["calculate_probabilities"] = bool(
            getattr(bertopic_cfg, "calculate_probabilities")
        )
    return model_kwargs


def build_provenance(
    *,
    embedding_model: Optional[str],
    fit_scope: str,
    duration_seconds: Optional[float] = None,
    package_version: Optional[str] = None,
    embedding_revision: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Privacy-safe provenance: no transcript text, tokens, or absolute paths.

    Fields are nullable/optional; analysis success must not require complete
    revision discovery.
    """
    return {
        "fit_scope": fit_scope,
        "embedding_model": embedding_model,
        "embedding_revision": embedding_revision,
        "package_version": package_version,
        "duration_seconds": duration_seconds,
        "embedding_model_basename": redact_path_for_diagnostics(embedding_model),
    }
