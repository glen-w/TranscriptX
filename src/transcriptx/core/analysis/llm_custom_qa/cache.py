"""Cache lookup helpers for llm_custom_qa (validate-before-reuse)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from transcriptx.core.analysis.llm_custom_qa.artifact_schema import validate_artifact
from transcriptx.core.analysis.llm_custom_qa.errors import (
    CustomQAError,
    CustomQAFailureCode,
)


def try_load_cached_artifact(
    json_final: Path,
    *,
    cache_key: str,
    questions_requested: list[str],
    questions_hash: str,
) -> Optional[dict[str, Any]]:
    """Return validated cached artifact if present and matching, else None.

    On schema/invariant failure raises CUSTOM_QA_CACHE_INVALID so callers can
    regenerate once.
    """
    if not json_final.exists():
        return None
    try:
        raw = json.loads(json_final.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    if raw.get("cache_key") != cache_key:
        return None
    try:
        return validate_artifact(
            raw,
            questions_requested=questions_requested,
            questions_hash=questions_hash,
        )
    except Exception as exc:
        raise CustomQAError(
            f"Cached artifact failed validation: {exc}",
            code=CustomQAFailureCode.CUSTOM_QA_CACHE_INVALID,
            error_context={"path": str(json_final)},
        ) from exc
