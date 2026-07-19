"""BERTopic artifact schema contracts and validation helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Current artifact schema for topics / doc_topic_data / meta payloads.
SCHEMA_VERSION = 1

# Versions that may be read directly without upgrade.
SUPPORTED_SCHEMA_VERSIONS = frozenset({1})


def attach_schema_version(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow copy with schema_version set when absent."""
    out = dict(payload)
    out.setdefault("schema_version", SCHEMA_VERSION)
    return out


def read_schema_version(payload: Any) -> Optional[int]:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("schema_version")
    if raw is None:
        # Pre-re-enable artifacts omit schema_version; treat as v1-compatible.
        return 1
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def validate_bertopic_artifact_payload(
    payload: Any,
    *,
    require_topics: bool = True,
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """
    Validate a bertopic artifact-like payload.

    Returns ``(normalized_payload, warnings)``.
    Unsupported schema versions yield ``(None, warnings)`` (skip-with-warning).
    Corrupt / invalid shapes yield ``(None, warnings)`` (reject).
    """
    warnings: List[str] = []
    if not isinstance(payload, dict):
        warnings.append("bertopic artifact is not an object")
        return None, warnings

    version = read_schema_version(payload)
    if version is None:
        warnings.append("bertopic artifact has corrupt schema_version")
        return None, warnings
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        warnings.append(
            f"bertopic artifact schema_version={version} unsupported; skipping"
        )
        return None, warnings

    if require_topics:
        topics = payload.get("topics")
        if topics is not None and not isinstance(topics, list):
            warnings.append("bertopic artifact topics is not a list")
            return None, warnings

    return payload, warnings
