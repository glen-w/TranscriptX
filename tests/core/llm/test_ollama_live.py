"""Optional live Ollama integration smoke test (skipped unless env flag set)."""

from __future__ import annotations

import os

import pytest

from transcriptx.core.llm import get_llm_client
from transcriptx.core.utils.config.main import TranscriptXConfig

pytestmark = pytest.mark.skipif(
    os.getenv("TRANSCRIPTX_LLM_LIVE_TEST", "").strip().lower()
    not in ("1", "true", "yes", "on"),
    reason="Set TRANSCRIPTX_LLM_LIVE_TEST=1 to run live Ollama tests",
)


@pytest.mark.integration
def test_live_ollama_generate_smoke() -> None:
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    cfg.llm.model = os.getenv("TRANSCRIPTX_LLM_MODEL", "qwen3:8b")
    client = get_llm_client(cfg)
    assert client.is_available() is True
    text = client.generate(prompt="Say hello in one word.", temperature=0.0)
    assert isinstance(text, str) and text.strip()
