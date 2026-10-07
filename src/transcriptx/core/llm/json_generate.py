"""Shared helpers for JSON-format LLM generation across GUI/analysis consumers.

All callers must use keyword-only ``prompt=`` / ``system_prompt=`` on
:meth:`LLMClient.generate`. This module centralises the ``response_format``
payload so assistive features (rename, speaker names) and analysis modules
share one path.
"""

from __future__ import annotations

from typing import Optional

from transcriptx.core.llm.llm_client import JsonResponseFormat, LLMClient

__all__ = [
    "JsonResponseFormat",
    "generate_json",
]


def generate_json(
    client: LLMClient,
    *,
    prompt: str,
    temperature: float,
    system_prompt: Optional[str] = None,
    max_tokens: Optional[int] = None,
    response_format: JsonResponseFormat = "json",
) -> str:
    """Call ``client.generate`` with a JSON ``response_format``.

    ``response_format`` may be the string ``\"json\"`` or an Ollama JSON Schema
    object (passed through as the ``format`` body field).
    """
    return client.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )
