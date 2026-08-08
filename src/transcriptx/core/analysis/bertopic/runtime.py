"""Shared BERTopic model kwargs + privacy-safe provenance helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from transcriptx.core.analysis.bertopic.deps import redact_path_for_diagnostics
from transcriptx.core.utils.native_threads import limited_native_threads

__all__ = [
    "build_model_kwargs",
    "build_provenance",
    "build_threadsafe_reduction_models",
    "limited_native_threads",
]

# Match BERTopic's historical default reduction geometry, but force single-thread
# native pools. On macOS host Python, default UMAP ``n_jobs=-1`` / HDBSCAN
# ``core_dist_n_jobs=-1`` oversubscribe OpenMP+Numba and segfault during
# ``fit_transform`` (exit -11) even when env thread caps are set late.
_DEFAULT_MIN_TOPIC_SIZE = 10


def build_threadsafe_reduction_models(
    *, min_topic_size: int = _DEFAULT_MIN_TOPIC_SIZE
) -> Dict[str, Any]:
    """Construct UMAP + HDBSCAN backends pinned to one native worker.

    Imports are deferred so core installs without the optional BERTopic extra
    can still import this module for non-fit helpers.
    """
    from hdbscan import HDBSCAN
    from umap import UMAP

    cluster_size = max(2, int(min_topic_size))
    return {
        "umap_model": UMAP(
            n_neighbors=15,
            n_components=5,
            min_dist=0.0,
            metric="cosine",
            random_state=42,
            n_jobs=1,
        ),
        "hdbscan_model": HDBSCAN(
            min_cluster_size=cluster_size,
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=True,
            core_dist_n_jobs=1,
        ),
    }


def build_model_kwargs(
    bertopic_cfg: Any, *, threadsafe_reduction: bool = True
) -> Dict[str, Any]:
    """Build BERTopic constructor kwargs from Pydantic-owned config.

    Always applies explicit config values (including ``False`` / numeric defaults)
    so env/file/UI overrides are not dropped by truthiness checks. ``label_words``
    is intentionally omitted — it is used only when shaping topic labels, not by
    the BERTopic constructor.

    When ``threadsafe_reduction`` is true (default), inject UMAP/HDBSCAN models
    with ``n_jobs`` / ``core_dist_n_jobs`` pinned to 1 so macOS OpenMP+Numba
    oversubscription cannot segfault the process mid-fit.
    """
    model_kwargs: Dict[str, Any] = {}
    if not bertopic_cfg:
        if threadsafe_reduction:
            model_kwargs.update(build_threadsafe_reduction_models())
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

    if threadsafe_reduction:
        cluster_size = int(
            model_kwargs.get("min_topic_size") or _DEFAULT_MIN_TOPIC_SIZE
        )
        model_kwargs.update(
            build_threadsafe_reduction_models(min_topic_size=cluster_size)
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
