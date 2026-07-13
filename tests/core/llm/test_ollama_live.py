"""Optional live Ollama client smoke test (skipped unless env flag set).

Module-level live coverage lives in
``tests/core/analysis/test_llm_modules_live.py``.
"""

from __future__ import annotations

import os

import pytest

from transcriptx.core.llm import get_llm_client
from transcriptx.core.utils.config.main import TranscriptXConfig

pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_api,
    pytest.mark.skipif(
        os.getenv("TRANSCRIPTX_LLM_LIVE_TEST", "").strip().lower()
        not in ("1", "true", "yes", "on"),
        reason="Set TRANSCRIPTX_LLM_LIVE_TEST=1 to run live Ollama tests",
    ),
]


@pytest.mark.timeout(300)
def test_live_ollama_generate_smoke() -> None:
    # Host-side live smoke: ignore docker-oriented host.docker.internal from .env.
    base_url = os.getenv(
        "TRANSCRIPTX_LLM_LIVE_BASE_URL", "http://127.0.0.1:11434"
    ).strip()
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    cfg.llm.base_url = base_url
    # Dedicated smoke model (avoid qwen3 thinking models that can emit empty
    # ``response`` when num_predict is small).
    cfg.llm.model = os.getenv("TRANSCRIPTX_LLM_SMOKE_MODEL", "llama3.2:3b")
    cfg.llm.request_timeout = 270.0
    client = get_llm_client(cfg)
    assert client.is_available() is True
    text = client.generate(
        prompt="Reply with exactly the word hello.",
        temperature=0.0,
        max_tokens=64,
    )
    assert isinstance(text, str) and text.strip()
