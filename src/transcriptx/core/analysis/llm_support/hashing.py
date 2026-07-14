"""Hashing primitives for LLM request/caching identities."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

__all__ = [
    "sha256_text",
    "sha256_canonical_json",
    "sha256_llm_request",
]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_canonical_json(data: Any) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return sha256_text(payload)


def sha256_llm_request(
    user_prompt: str,
    *,
    system_prompt: Optional[str] = None,
) -> str:
    """Hash the canonical request payload sent to ``client.generate()``."""
    payload: Dict[str, str] = {"user": user_prompt}
    if system_prompt is not None:
        payload["system"] = system_prompt
    return sha256_canonical_json(payload)
