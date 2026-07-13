"""Optional live Ollama tests for LLM analysis modules.

Skipped unless ``TRANSCRIPTX_LLM_LIVE_TEST=1``. Excluded from the default fast
suite via ``integration`` / ``requires_api`` / ``slow`` markers.

Requires a reachable Ollama daemon and an installed model
(``TRANSCRIPTX_LLM_MODEL`` or the default / first available tag).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any
from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.llm_action_items import LLMActionItemsAnalysis
from transcriptx.core.analysis.llm_speaker_summary import LLMSpeakerSummaryAnalysis
from transcriptx.core.analysis.llm_summary import LLMSummaryAnalysis
from transcriptx.core.llm import DEFAULT_OLLAMA_MODEL
from transcriptx.core.llm.errors import LLMResponseError
from transcriptx.core.utils.config import get_config, set_config
from transcriptx.core.utils.config.main import TranscriptXConfig

pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_api,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.getenv("TRANSCRIPTX_LLM_LIVE_TEST", "").strip().lower()
        not in ("1", "true", "yes", "on"),
        reason="Set TRANSCRIPTX_LLM_LIVE_TEST=1 to run live Ollama LLM module tests",
    ),
]


def _live_base_url() -> str:
    """Resolve Ollama URL for host-side live tests.

    Prefers ``TRANSCRIPTX_LLM_LIVE_BASE_URL``. Ignores a project ``.env`` value of
    ``host.docker.internal`` (meant for in-container GUI → host Ollama) so live
    tests run correctly on the Mac host.
    """
    explicit = os.getenv("TRANSCRIPTX_LLM_LIVE_BASE_URL", "").strip()
    if explicit:
        return explicit
    configured = os.getenv("TRANSCRIPTX_LLM_BASE_URL", "").strip()
    if configured and (
        "127.0.0.1" in configured or "localhost" in configured.split("://", 1)[-1]
    ):
        return configured
    return "http://127.0.0.1:11434"


def _installed_ollama_models(base_url: str) -> list[str]:
    url = base_url.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise AssertionError(f"Ollama tags probe failed for {url}: {exc!r}") from exc
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    names: list[str] = []
    for row in models:
        if isinstance(row, dict) and isinstance(row.get("name"), str):
            names.append(row["name"])
    return names


def _resolve_live_model(base_url: str) -> str:
    env_model = os.getenv("TRANSCRIPTX_LLM_MODEL", "").strip()
    if env_model:
        return env_model
    installed = _installed_ollama_models(base_url)
    # Prefer smaller models for live test latency when the default is absent.
    preferred = (
        "qwen3:4b",
        "llama3.2:3b",
        DEFAULT_OLLAMA_MODEL,
        "qwen3:8b",
        "qwen2.5:7b",
    )
    for name in preferred:
        if name in installed:
            return name
    if installed:
        return installed[0]
    return DEFAULT_OLLAMA_MODEL


def _live_cfg(*, effort: str = "low") -> TranscriptXConfig:
    base_url = _live_base_url()
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    cfg.llm.base_url = base_url
    cfg.llm.model = _resolve_live_model(base_url)
    cfg.llm.seed = 42
    cfg.llm.default_temperature = 0.0
    cfg.analysis.llm_summary.effort = effort  # type: ignore[assignment]
    cfg.analysis.llm_speaker_summary.effort = effort  # type: ignore[assignment]
    cfg.analysis.llm_action_items.effort = effort  # type: ignore[assignment]
    return cfg


def _context(tmp_path, segments: list[dict[str, Any]]) -> MagicMock:
    transcript = tmp_path / "live_transcript.json"
    transcript.write_text(json.dumps({"segments": segments}), encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    context = MagicMock()
    context.transcript_path = str(transcript)
    context.get_segments.return_value = segments
    context.get_base_name.return_value = "live"
    context.get_transcript_dir.return_value = str(out)
    context.get_run_id.return_value = "live-run"
    context.get_runtime_flags.return_value = {}
    context.store_analysis_result = MagicMock()
    return context


def _with_live_config(cfg: TranscriptXConfig):
    previous = get_config()
    set_config(cfg)
    return previous


@pytest.fixture
def live_cfg() -> TranscriptXConfig:
    return _live_cfg(effort="low")


@pytest.mark.timeout(600)
def test_live_llm_summary_module(tmp_path, live_cfg: TranscriptXConfig) -> None:
    segments = [
        {
            "speaker": "Alice",
            "text": "We need to ship the report by Friday.",
            "start": 0.0,
            "end": 2.0,
        },
        {
            "speaker": "Bob",
            "text": "I will draft the executive summary tomorrow morning.",
            "start": 2.0,
            "end": 5.0,
        },
    ]
    context = _context(tmp_path, segments)
    previous = _with_live_config(live_cfg)
    try:
        result = LLMSummaryAnalysis().run_from_context(context)
    finally:
        set_config(previous)

    assert result["status"] == "success"
    payload = result["payload"]
    assert isinstance(payload.get("summary"), str) and payload["summary"].strip()
    assert payload["schema_id"] == "transcriptx.llm_summary.v1"
    assert payload["provenance"]["provider"] == "ollama"
    assert payload["provenance"]["model"]
    context.store_analysis_result.assert_called()


@pytest.mark.timeout(600)
def test_live_llm_speaker_summary_module(tmp_path, live_cfg: TranscriptXConfig) -> None:
    segments = [
        {
            "speaker": "Alice",
            "text": "I own the budget review for next week.",
            "start": 0.0,
            "end": 2.0,
        },
        {
            "speaker": "Bob",
            "text": "I will collect the vendor quotes by Wednesday.",
            "start": 2.0,
            "end": 4.0,
        },
    ]
    context = _context(tmp_path, segments)
    previous = _with_live_config(live_cfg)
    try:
        result = LLMSpeakerSummaryAnalysis().run_from_context(context)
    finally:
        set_config(previous)

    assert result["status"] == "success"
    payload = result["payload"]
    speakers = payload.get("speakers") or []
    assert len(speakers) == 2
    names = {row.get("speaker") or row.get("display_name") for row in speakers}
    # Accept either field naming from payload shape
    assert "Alice" in names or any("Alice" in str(row) for row in speakers)
    assert payload["provenance"]["success_count"] == 2


@pytest.mark.timeout(600)
def test_live_llm_action_items_module(tmp_path, live_cfg: TranscriptXConfig) -> None:
    # Prefer a non-reasoning JSON-friendly model when available; qwen3 thinking
    # outputs often break strict action-item JSON parsing on small tiers.
    base_url = live_cfg.llm.base_url
    installed = _installed_ollama_models(base_url)
    for candidate in (
        os.getenv("TRANSCRIPTX_LLM_ACTION_ITEMS_MODEL", "").strip(),
        "llama3.2:3b",
        "mistral:latest",
        "qwen2.5:7b",
        live_cfg.llm.model,
    ):
        if candidate and candidate in installed:
            live_cfg.llm.model = candidate
            break

    segments = [
        {
            "speaker": "Alice",
            "text": "Bob, please send the signed contract to legal by Thursday.",
            "start": 0.0,
            "end": 3.0,
        },
        {
            "speaker": "Bob",
            "text": "Understood. I will email the signed contract to legal on Thursday.",
            "start": 3.0,
            "end": 6.0,
        },
    ]
    context = _context(tmp_path, segments)
    previous = _with_live_config(live_cfg)
    try:
        result = LLMActionItemsAnalysis().run_from_context(context)
    except LLMResponseError as exc:
        pytest.skip(
            f"Live action-items JSON not returned by model {live_cfg.llm.model!r}: {exc}"
        )
    finally:
        set_config(previous)

    assert result["status"] == "success"
    payload = result["payload"]
    assert payload["schema_id"] == "transcriptx.llm_action_items.v1"
    items = payload.get("items")
    assert isinstance(items, list)
    assert payload["provenance"]["provider"] == "ollama"
    assert isinstance(payload["provenance"].get("model"), str)


def test_live_cfg_resolves_installed_model(live_cfg: TranscriptXConfig) -> None:
    """Sanity: live fixture points at an installed Ollama model when daemon is up."""
    installed = _installed_ollama_models(live_cfg.llm.base_url)
    assert installed, "Ollama /api/tags returned no models"
    assert live_cfg.llm.model in installed
