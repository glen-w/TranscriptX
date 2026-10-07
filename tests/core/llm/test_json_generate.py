"""Unit tests for shared JSON generate helper."""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from transcriptx.core.llm.json_generate import generate_json


@pytest.mark.unit
def test_generate_json_forwards_kwargs() -> None:
    captured: dict[str, Any] = {}

    def _generate(
        *,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float,
        max_tokens: Optional[int] = None,
        response_format: Any = None,
    ) -> str:
        captured.update(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": response_format,
            }
        )
        return '{"ok":true}'

    client = MagicMock()
    client.generate.side_effect = _generate
    out = generate_json(
        client,
        prompt="user",
        system_prompt="sys",
        temperature=0.1,
        max_tokens=128,
        response_format={"type": "object"},
    )
    assert out == '{"ok":true}'
    assert captured["prompt"] == "user"
    assert captured["system_prompt"] == "sys"
    assert captured["response_format"] == {"type": "object"}
