"""Group-run summary precedence via central synthesis resolver."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.group_llm_synthesis.lock import synthesis_lock
from transcriptx.core.analysis.group_llm_synthesis.synthesize import (
    run_group_llm_synthesis,
)
from transcriptx.web.summary_precedence import resolve_primary_summary


def _write_collect(run: Path) -> None:
    (run / "group_run_metadata.json").write_text("{}", encoding="utf-8")
    collect = run / "llm_summary"
    collect.mkdir(parents=True)
    (collect / "llm_summary.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "aggregation_key": "llm_summary",
                "summaries": [
                    {
                        "summary": "Session A",
                        "source_transcript_id": "t1",
                        "order_index": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _cfg() -> SimpleNamespace:
    return SimpleNamespace(
        analysis=SimpleNamespace(
            group_llm_synthesis=SimpleNamespace(enabled=True, effort="low")
        ),
        llm=SimpleNamespace(
            enabled=True,
            provider="ollama",
            model="test",
            base_url="http://localhost:11434",
            seed=0,
            availability_timeout=1.0,
        ),
    )


def _publish(run: Path, *, summary: str = "Committed group summary") -> None:
    mock_client = MagicMock()
    mock_client.generate.return_value = json.dumps({"summary": summary})
    with synthesis_lock(run):
        with (
            patch(
                "transcriptx.core.analysis.group_llm_synthesis.synthesize.build_ollama_analysis_client",
                return_value=mock_client,
            ),
            patch(
                "transcriptx.core.analysis.group_llm_synthesis.synthesize.require_ollama_analysis",
            ),
            patch(
                "transcriptx.core.analysis.group_llm_synthesis.synthesize.resolve_llm_runtime",
                return_value=SimpleNamespace(
                    effort="low",
                    model="test",
                    max_input_chars=50_000,
                    request_timeout=30.0,
                    max_output_tokens=512,
                    model_source="global",
                ),
            ),
        ):
            result = run_group_llm_synthesis(
                run_root=run,
                run_id="g1",
                config=_cfg(),
                want_global=True,
                want_speakers=False,
            )
    assert result.published


@pytest.mark.unit
def test_group_run_prefers_committed_synthesis(tmp_path: Path) -> None:
    run = tmp_path / "group_run"
    run.mkdir()
    _write_collect(run)
    _publish(run, summary="Committed group summary")
    loader = MagicMock()
    loader.load_text.return_value = "# Member LLM"
    loader.load_json.return_value = {"summary": "member"}

    result = resolve_primary_summary(loader, run_root=run)
    assert result.primary is not None
    assert result.primary.kind == "llm_summary"
    assert result.primary.title == "Cross-session LLM Summary"
    assert result.primary.payload is not None
    assert result.primary.payload["summary"] == "Committed group summary"
    assert result.others == ()
    loader.load_text.assert_not_called()


@pytest.mark.unit
def test_group_run_no_member_fallback_when_synthesis_missing(tmp_path: Path) -> None:
    run = tmp_path / "group_run"
    run.mkdir()
    (run / "group_run_metadata.json").write_text("{}", encoding="utf-8")
    loader = MagicMock()
    loader.load_text.return_value = "# Member LLM"
    loader.load_json.return_value = {"summary": "member"}

    result = resolve_primary_summary(loader, run_root=run)
    assert result.primary is None
    assert "Cross-session summary was unavailable" in result.unavailable_message
    loader.load_text.assert_not_called()


@pytest.mark.unit
def test_group_run_interrupted_synthesis_stays_unavailable(tmp_path: Path) -> None:
    """Partial .group_llm_synthesis generation without ACTIVE must not become primary."""
    run = tmp_path / "group_run"
    run.mkdir()
    (run / "group_run_metadata.json").write_text("{}", encoding="utf-8")
    gen = (
        run / ".group_llm_synthesis" / "generations" / "interrupted_gen" / "llm_summary"
    )
    gen.mkdir(parents=True)
    (gen / "group_llm_summary.json").write_text(
        json.dumps({"summary": "Should not surface"}),
        encoding="utf-8",
    )
    loader = MagicMock()
    loader.load_text.return_value = "# Member LLM"
    loader.load_json.return_value = {"summary": "member"}
    result = resolve_primary_summary(loader, run_root=run)
    assert result.primary is None
    assert "Cross-session summary was unavailable" in result.unavailable_message
    loader.load_text.assert_not_called()


@pytest.mark.unit
def test_non_group_run_uses_loader_precedence(tmp_path: Path) -> None:
    run = tmp_path / "transcript_run"
    run.mkdir()
    loader = MagicMock()
    loader.load_text.side_effect = lambda module, suffix, **kw: (
        "# LLM" if module == "llm_summary" else None
    )
    loader.load_json.side_effect = lambda module, suffix, **kw: (
        {"summary": "x"} if module == "llm_summary" else None
    )
    result = resolve_primary_summary(loader, run_root=run)
    assert result.primary is not None
    assert result.primary.title == "LLM Transcript Summary"
