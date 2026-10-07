"""Orchestrator for rename suggestions."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.utils.rename.suggestions.models import RawRenameCue
from transcriptx.core.utils.rename.suggestions.service import suggest_rename_stems


def _write_transcript(path: Path, segments: list[dict]) -> None:
    payload = {
        "segments": segments,
        "source": {"type": "import", "original_path": "x", "imported_at": "2026-01-01T00:00:00+00:00"},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.unit
def test_mode_off_returns_empty_without_loading_segments(tmp_path: Path) -> None:
    tpath = tmp_path / "t.json"
    _write_transcript(tpath, [{"text": "hello"}])
    with patch(
        "transcriptx.core.utils.rename.suggestions.service.load_transcript_segments"
    ) as load_mock:
        with patch(
            "transcriptx.core.utils.rename.suggestions.service.get_config"
        ) as cfg_mock:
            cfg_mock.return_value.input.rename_content_suggestions = "off"
            result = suggest_rename_stems(tpath)
    load_mock.assert_not_called()
    assert result.options == ()
    assert result.prefill == ""


@pytest.mark.unit
def test_existing_natural_language_title_always_in_options(tmp_path: Path) -> None:
    title = "Webinar on Implementing the BBNJ in the SWIO Region"
    tpath = tmp_path / f"{title}.json"
    _write_transcript(
        tpath,
        [
            {
                "text": (
                    "Welcome to our webinar on high seas governance. "
                    "Take us through your presentation."
                )
            }
        ],
    )
    with patch(
        "transcriptx.core.utils.rename.suggestions.service.get_config"
    ) as cfg_mock:
        inp = cfg_mock.return_value.input
        inp.rename_content_suggestions = "auto"
        inp.rename_suggest_transcript = True
        inp.rename_suggest_llm = False
        inp.rename_suggest_web = False
        inp.smart_rename_pattern = "{yymmdd}_{period}_{n}"
        cfg_mock.return_value.llm.enabled = False
        result = suggest_rename_stems(tpath, force_refresh=True)

    expected = "Webinar_on_Implementing_the_BBNJ_in_the_SWIO_Region"
    assert any(o.stem == expected and o.basis == "existing_title" for o in result.options)
    assert result.options[0].stem == expected
    assert result.prefill == expected


@pytest.mark.unit
def test_on_demand_runs_when_mode_off(tmp_path: Path) -> None:
    tpath = tmp_path / "webinar.json"
    _write_transcript(
        tpath,
        [{"text": "Recorded on 2026-03-12. Welcome to the Acme product webinar."}],
    )
    with patch(
        "transcriptx.core.utils.rename.suggestions.service.get_config"
    ) as cfg_mock:
        inp = cfg_mock.return_value.input
        inp.rename_content_suggestions = "off"
        inp.rename_suggest_transcript = True
        inp.rename_suggest_llm = False
        inp.rename_suggest_web = False
        inp.smart_rename_pattern = "{yymmdd}_{period}_{n}"
        result = suggest_rename_stems(tpath, on_demand=True, force_refresh=True)
    assert result.options


@pytest.mark.unit
def test_auto_mode_builds_options(tmp_path: Path) -> None:
    tpath = tmp_path / "webinar.json"
    _write_transcript(
        tpath,
        [{"text": "Recorded on 2026-03-12. Welcome to the Acme product webinar."}],
    )
    with patch(
        "transcriptx.core.utils.rename.suggestions.service.get_config"
    ) as cfg_mock:
        inp = cfg_mock.return_value.input
        inp.rename_content_suggestions = "auto"
        inp.rename_suggest_transcript = True
        inp.rename_suggest_llm = False
        inp.rename_suggest_web = False
        inp.rename_suggestions_effort = "low"
        inp.smart_rename_pattern = "{yymmdd}_{period}_{n}"
        cfg_mock.return_value.llm.enabled = False
        result = suggest_rename_stems(tpath, force_refresh=True)
    assert result.options
    assert result.prefill
    assert "rename_managed_transcript" not in dir(result)


def test_suggest_rename_stems_prefers_transcript_event_date_over_file_mtime(tmp_path):
    tpath = tmp_path / "webinar.json"
    _write_transcript(
        tpath,
        [{"text": "Recorded on March 15, 2024. Host: Welcome to the webinar."}],
    )
    with patch(
        "transcriptx.core.utils.rename.suggestions.service.get_config"
    ) as cfg_mock:
        inp = cfg_mock.return_value.input
        inp.rename_content_suggestions = "auto"
        inp.rename_suggest_transcript = True
        inp.rename_suggest_llm = False
        inp.rename_suggest_web = False
        inp.smart_rename_pattern = "{yymmdd}_{title}"
        cfg_mock.return_value.llm.enabled = False
        result = suggest_rename_stems(tpath, force_refresh=True)
    assert result.options
    assert result.prefill == "240315"
    assert any(o.basis == "transcript_date" for o in result.options)
    assert all(o.basis != "file_mtime" or o.stem != result.prefill for o in result.options)


def test_suggest_rename_stems_title_only_when_no_event_date(tmp_path):
    tpath = tmp_path / "webinar.json"
    _write_transcript(
        tpath,
        [{"text": "Welcome to the Future of AI webinar. Host: Thanks for joining."}],
    )
    with patch(
        "transcriptx.core.utils.rename.suggestions.service.get_config"
    ) as cfg_mock:
        inp = cfg_mock.return_value.input
        inp.rename_content_suggestions = "auto"
        inp.rename_suggest_transcript = True
        inp.rename_suggest_llm = False
        inp.rename_suggest_web = False
        inp.smart_rename_pattern = "{yymmdd}_{title}"
        cfg_mock.return_value.llm.enabled = False
        result = suggest_rename_stems(tpath, force_refresh=True)
    assert result.options
    assert result.prefill
    assert not result.prefill.startswith("2")
    assert "future" in result.prefill.lower() or "ai" in result.prefill.lower()


@pytest.mark.unit
def test_maybe_llm_cues_prompt_is_excerpt_only(tmp_path: Path) -> None:
    """Schema must not live inside the bounded transcript envelope."""
    from transcriptx.core.utils.rename.suggestions.service import _maybe_llm_cues

    segments = [{"text": "Welcome to the Acme product webinar on fisheries."}]
    captured: dict = {}

    class _Client:
        def is_available(self) -> bool:
            return True

        def generate(self, **kwargs):  # type: ignore[no-untyped-def]
            captured["prompt"] = kwargs.get("prompt")
            return json.dumps(
                {
                    "suggestions": [
                        {"title": "Acme Webinar", "event_date": None, "quote": ""},
                        {"title": "Fisheries", "event_date": None, "quote": ""},
                        {"title": "Product Launch", "event_date": None, "quote": ""},
                    ]
                }
            )

    with patch(
        "transcriptx.core.utils.rename.suggestions.service.get_config"
    ) as cfg_mock:
        cfg_mock.return_value.llm.enabled = True
        cfg_mock.return_value.llm.provider = "ollama"
        cfg_mock.return_value.llm.default_temperature = 0.0
        with patch(
            "transcriptx.core.analysis.llm_support.runtime.require_ollama_analysis"
        ):
            with patch(
                "transcriptx.core.analysis.llm_support.runtime.resolve_llm_runtime"
            ) as rt:
                rt.return_value.model = "gemma3:12b"
                rt.return_value.model_source = "settings"
                rt.return_value.max_input_chars = 48000
                rt.return_value.max_output_tokens = 512
                with patch(
                    "transcriptx.core.analysis.llm_support.runtime.build_ollama_analysis_client",
                    return_value=_Client(),
                ):
                    with patch(
                        "transcriptx.core.llm.thinking_models.is_thinking_model",
                        return_value=False,
                    ):
                        cues, status, model, _ = _maybe_llm_cues(
                            segments, effort="low"
                        )
    assert model == "gemma3:12b"
    assert len(cues) == 3
    assert "rename suggestions from local LLM" in status
    prompt = captured["prompt"]
    assert "Welcome to the Acme product webinar" in prompt
    assert "<<<TRANSCRIPT>>>" in prompt
    assert "<<<EXCERPT>>>" not in prompt
    assert "Return JSON:" not in prompt
    assert '"event_date"' not in prompt


@pytest.mark.unit
def test_maybe_llm_cues_surfaces_generate_failure() -> None:
    from transcriptx.core.utils.rename.suggestions.service import _maybe_llm_cues

    class _Client:
        def is_available(self) -> bool:
            return True

        def generate(self, **kwargs):  # type: ignore[no-untyped-def]
            raise TypeError("got multiple values for argument 'temperature'")

    with patch(
        "transcriptx.core.utils.rename.suggestions.service.get_config"
    ) as cfg_mock:
        cfg_mock.return_value.llm.enabled = True
        cfg_mock.return_value.llm.provider = "ollama"
        cfg_mock.return_value.llm.default_temperature = 0.0
        with patch(
            "transcriptx.core.analysis.llm_support.runtime.require_ollama_analysis"
        ):
            with patch(
                "transcriptx.core.analysis.llm_support.runtime.resolve_llm_runtime"
            ) as rt:
                rt.return_value.model = "gemma3:12b"
                rt.return_value.model_source = "settings"
                rt.return_value.max_input_chars = 48000
                rt.return_value.max_output_tokens = 512
                with patch(
                    "transcriptx.core.analysis.llm_support.runtime.build_ollama_analysis_client",
                    return_value=_Client(),
                ):
                    with patch(
                        "transcriptx.core.llm.thinking_models.is_thinking_model",
                        return_value=False,
                    ):
                        cues, status, model, _ = _maybe_llm_cues(
                            [{"text": "hello webinar"}], effort="low"
                        )
    assert cues == []
    assert model == "gemma3:12b"
    assert "failed" in status
    assert "multiple values" in status


@pytest.mark.unit
def test_on_demand_runs_llm_when_ollama_configured(tmp_path: Path) -> None:
    tpath = tmp_path / "webinar.json"
    _write_transcript(
        tpath,
        [{"text": "Welcome to our webinar on fisheries management."}],
    )
    llm_cues = [
        RawRenameCue(
            basis="llm",
            confidence="likely",
            detail="Local LLM suggestion 1",
            title="Fisheries Forum",
        ),
        RawRenameCue(
            basis="llm",
            confidence="likely",
            detail="Local LLM suggestion 2",
            title="Marine Stocks",
        ),
        RawRenameCue(
            basis="llm",
            confidence="likely",
            detail="Local LLM suggestion 3",
            title="Ocean Policy",
        ),
    ]
    with patch(
        "transcriptx.core.utils.rename.suggestions.service.get_config"
    ) as cfg_mock:
        inp = cfg_mock.return_value.input
        inp.rename_content_suggestions = "off"
        inp.rename_suggest_transcript = True
        inp.rename_suggest_llm = False
        inp.rename_suggest_web = False
        inp.rename_suggestions_effort = "low"
        inp.smart_rename_pattern = "{yymmdd}_{title}"
        cfg_mock.return_value.llm.enabled = True
        cfg_mock.return_value.llm.provider = "ollama"
        with patch(
            "transcriptx.core.utils.rename.suggestions.service._maybe_llm_cues",
            return_value=(llm_cues, "3 rename suggestions from local LLM (`test`).", "test", "settings"),
        ):
            result = suggest_rename_stems(tpath, on_demand=True, force_refresh=True)
    llm_options = [o for o in result.options if o.basis == "llm"]
    assert len(llm_options) == 3
    assert result.status.startswith("3 rename suggestions")
