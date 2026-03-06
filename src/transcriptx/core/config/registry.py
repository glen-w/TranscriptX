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
    return registry
