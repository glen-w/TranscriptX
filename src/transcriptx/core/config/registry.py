"""Configuration registry and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional
import os
import copy

from transcriptx.core.utils.config import TranscriptXConfig  # type: ignore[import-untyped]


@dataclass(frozen=True)
class FieldMetadata:
    """Metadata describing a config field."""

    key: str
    path: str
    type: type
    default: Any
    min: Optional[float] = None
    max: Optional[float] = None
    choices: Optional[Iterable[Any]] = None
    description: str = ""
    scope: str = "project"  # default | project | run | run_only
    sensitivity: str = "normal"  # normal | hidden
    category: str = ""
    advanced: bool = False


def _without_env_prefix(prefix: str) -> Dict[str, Optional[str]]:
    removed: Dict[str, Optional[str]] = {}
    for key in list(os.environ.keys()):
        if key.startswith(prefix):
            removed[key] = os.environ.pop(key)
    return removed


def _restore_env(removed: Dict[str, Optional[str]]) -> None:
    for key, value in removed.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def get_default_config_dict() -> Dict[str, Any]:
    """Return default config dict with env vars suppressed."""
    removed = _without_env_prefix("TRANSCRIPTX_")
    try:
        config = TranscriptXConfig()
        return config.to_dict()
    finally:
        _restore_env(removed)


def flatten(nested: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Flatten nested dict to dotpath map."""
    items: Dict[str, Any] = {}
    for key, value in nested.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.update(flatten(value, full_key))
        else:
            items[full_key] = value
    return items


def unflatten(dotmap: Dict[str, Any]) -> Dict[str, Any]:
    """Convert dotpath map to nested dict."""
    nested: Dict[str, Any] = {}
    for key, value in dotmap.items():
        parts = key.split(".")
        cursor = nested
        for part in parts[:-1]:
            if part not in cursor or not isinstance(cursor[part], dict):
                cursor[part] = {}
            cursor = cursor[part]
        cursor[parts[-1]] = value
    return nested


def _infer_type(value: Any) -> type:
    """Infer the type of a value for validation purposes."""
    if value is None:
        # For None values, we'll use a special marker type
        # The validation will need to handle this specially
        return type(None)
    if isinstance(value, bool):
        return bool
    if isinstance(value, int):
        return int
    if isinstance(value, float):
        return float
    if isinstance(value, tuple):
        # Tuples are often serialized as lists in JSON, so we accept both
        return tuple
    if isinstance(value, list):
        return list
    if isinstance(value, dict):
        return dict
    return str


def build_registry() -> Dict[str, FieldMetadata]:
    """Build registry from default config values."""
    defaults = get_default_config_dict()
    dotmap = flatten(defaults)
    registry: Dict[str, FieldMetadata] = {}
    for key, value in dotmap.items():
        category = key.split(".", 1)[0] if "." in key else "general"
        registry[key] = FieldMetadata(
            key=key,
            path=key,
            type=_infer_type(value),
            default=copy.deepcopy(value),
            category=category,
        )
    dynamic_charts_meta = registry.get("output.dynamic_charts")
    if dynamic_charts_meta:
        registry["output.dynamic_charts"] = FieldMetadata(
            **{
                **dynamic_charts_meta.__dict__,
                "choices": ["auto", "on", "off"],
                "description": "Dynamic chart generation mode.",
            }
        )
    dynamic_views_meta = registry.get("output.dynamic_views")
    if dynamic_views_meta:
        registry["output.dynamic_views"] = FieldMetadata(
            **{
                **dynamic_views_meta.__dict__,
                "choices": ["auto", "on", "off"],
                "description": "Dynamic HTML view generation mode.",
            }
        )
    overview_missing_meta = registry.get("dashboard.overview_missing_behavior")
    if overview_missing_meta:
        registry["dashboard.overview_missing_behavior"] = FieldMetadata(
            **{
                **overview_missing_meta.__dict__,
                "choices": ["skip", "show_placeholder"],
                "description": "Behavior when overview charts are missing.",
            }
        )
    overview_max_meta = registry.get("dashboard.overview_max_items")
    if overview_max_meta:
        registry["dashboard.overview_max_items"] = FieldMetadata(
            **{
                **overview_max_meta.__dict__,
                "type": int,
                "default": None,
                "min": 1,
                "description": "Maximum number of overview charts to display.",
            }
        )
    overview_charts_meta = registry.get("dashboard.overview_charts")
    if overview_charts_meta:
        try:
            from transcriptx.core.utils.chart_registry import (  # type: ignore[import-untyped]
                get_chart_registry,
            )

            chart_choices = sorted(get_chart_registry().keys())
        except Exception:
            chart_choices = []
        updated = {
            **overview_charts_meta.__dict__,
            "description": "Ordered list of chart registry IDs for the overview.",
        }
        if chart_choices:
            updated["choices"] = chart_choices
        registry["dashboard.overview_charts"] = FieldMetadata(**updated)
    # Handle transcription.language as a string (explicit; default en).
    transcription_language_meta = registry.get("transcription.language")
    if transcription_language_meta:
        registry["transcription.language"] = FieldMetadata(
            **{
                **transcription_language_meta.__dict__,
                "type": str,  # Allow str values, None is handled by default=None check
                "description": "Language code for transcription (e.g., 'en', 'fr'). Default is 'en'.",
            }
        )
    _apply_semantic_similarity_v2_registry(registry)
    return registry


def _apply_semantic_similarity_v2_registry(registry: Dict[str, FieldMetadata]) -> None:
    """Enrich semantic_similarity_v2 keys with choices, bounds, tooltips, and advanced flags."""

    def upd(path: str, **kwargs: Any) -> None:
        meta = registry.get(path)
        if not meta:
            return
        registry[path] = FieldMetadata(**{**meta.__dict__, **kwargs})

    base = "analysis.semantic_similarity_v2"
    upd(
        f"{base}.enabled",
        description="Enable semantic similarity v2 (default semantic path).",
    )
    upd(
        f"{base}.mode",
        choices=["basic", "advanced"],
        description=(
            "Selects the semantic similarity strategy: `basic` (fast, embeddings only) "
            "or `advanced` (uses sentiment/emotion/acts integration when available; "
            "may degrade to basic if integrations are missing)."
        ),
    )
    upd(
        f"{base}.model_name",
        description="Sentence-transformers model id used for embeddings.",
    )
    upd(
        f"{base}.batch_size",
        min=1,
        description="Transformer batch size for embedding unique texts.",
        advanced=True,
    )
    upd(
        f"{base}.min_text_length_words",
        min=1,
        description="Minimum word count for a segment to enter the v2 pipeline.",
        advanced=True,
    )
    upd(
        f"{base}.self_similarity_threshold",
        min=0.0,
        max=1.0,
        description=(
            "Minimum cosine similarity for two segments by the same speaker to be "
            "flagged as a self-repetition (0.0–1.0; higher = stricter)."
        ),
    )
    upd(
        f"{base}.cross_speaker_similarity_threshold",
        min=0.0,
        max=1.0,
        description=(
            "Minimum cosine similarity for two segments by different speakers to be "
            "flagged as a cross-speaker echo or paraphrase."
        ),
    )
    upd(
        f"{base}.self_time_window_seconds",
        min=0.0,
        description="Self-repetition time window (seconds).",
    )
    upd(
        f"{base}.cross_speaker_time_window_seconds",
        min=0.0,
        description="Cross-speaker candidate time window (seconds).",
    )
    upd(
        f"{base}.max_candidate_pairs",
        min=1,
        description=(
            "Global cap on candidate pairs scored per run. When reached, the pipeline "
            "early-stops and returns partial results."
        ),
    )
    upd(
        f"{base}.top_k_per_segment",
        min=1,
        description=(
            "Hard cap on candidate pairs generated per segment within the time window. "
            "Lower = faster, may miss matches."
        ),
    )
    upd(
        f"{base}.timeout_seconds",
        min=1.0,
        description=(
            "Wall-clock budget for the v2 pipeline. On timeout, partial results are "
            "returned with diagnostics.timeout_reached=True."
        ),
    )
    upd(
        f"{base}.persist_embeddings",
        description=(
            "Persist embeddings to disk keyed by transcript hash + model name + segment "
            "hash; subsequent runs reuse the cache (requires a writable output/cache root)."
        ),
        advanced=True,
    )
    upd(
        f"{base}.lru_size",
        min=0,
        description="Maximum entries in the in-memory embedding LRU cache (0 disables cache).",
        advanced=True,
    )
    upd(
        f"{base}.use_lexical_prefilter",
        description=(
            "Cheap token-Jaccard filter applied before scoring; drops obviously non-similar "
            "candidates. Increases speed, risks dropping borderline paraphrases."
        ),
        advanced=True,
    )
    upd(
        f"{base}.lexical_prefilter_min_jaccard",
        min=0.0,
        max=1.0,
        description="Minimum Jaccard similarity when lexical prefilter is enabled.",
        advanced=True,
    )
    upd(
        f"{base}.strict_advanced_inputs",
        description=(
            "When True, advanced mode blocks the run if sentiment/emotion/acts results are "
            "missing instead of degrading to basic."
        ),
    )
