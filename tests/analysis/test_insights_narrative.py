"""B18 insights_narrative module tests."""

from __future__ import annotations

from transcriptx.core.analysis.llm_support.insights_narrative_source import (
    build_narrative_input,
)
from transcriptx.core.analysis.insights_narrative import InsightsNarrativeAnalysis
from transcriptx.core.pipeline.module_registry import get_module_registry


def test_build_narrative_input_requires_ok_status() -> None:
    from transcriptx.core.analysis.highlights.post_process import stable_quote_id

    example = {
        "quote": "We must cut spend.",
        "start": 1.0,
        "end": 2.0,
        "speaker": "A",
    }
    qid = stable_quote_id(example, "t1")
    highlights = {
        "transcript_key": "t1",
        "themes": [
            {
                "label": "budget risk",
                "quote_ids": [qid],
            }
        ],
        "sections": {
            "cold_open": {"items": [example]},
            "emblematic_phrases": {"phrases": []},
        },
    }
    insights = {
        "status": "ok",
        "key_themes": [
            {
                "phrase": "budget risk",
                "evidence_quote_ids": [qid],
                "confidence": "high",
            }
        ],
        "recurring_ideas": [],
    }
    payload = build_narrative_input(insights, highlights)
    assert payload["key_themes"][0]["evidence"]


def test_insights_narrative_registered() -> None:
    info = get_module_registry().get_module_info("insights_narrative")
    assert info is not None
    assert info.requires_llm
    assert info.finalize_phase


def test_insights_narrative_operator_hint() -> None:
    from transcriptx.core.analysis.insights_narrative import (
        NARRATIVE_HINT_DISABLED,
        NARRATIVE_HINT_ENABLED,
        insights_narrative_operator_hint,
    )

    assert (
        insights_narrative_operator_hint(["insights"], narrative_enabled=False) is None
    )
    assert (
        insights_narrative_operator_hint(
            ["insights_narrative"], narrative_enabled=False
        )
        == NARRATIVE_HINT_DISABLED
    )
    assert (
        insights_narrative_operator_hint(["insights_narrative"], narrative_enabled=True)
        == NARRATIVE_HINT_ENABLED
    )


def test_insights_narrative_mocked_success(monkeypatch, tmp_path) -> None:
    from types import SimpleNamespace

    from transcriptx.core.analysis.insights_narrative import InsightsNarrativeAnalysis

    class _Client:
        model = "mock"

        def generate(self, **_kwargs):
            return '{"narrative": "Themes connect around budget risk."}'

    monkeypatch.setattr(
        "transcriptx.core.analysis.insights_narrative.get_llm_client",
        lambda *_a, **_k: _Client(),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.insights_narrative.require_resolved_model",
        lambda *_a, **_k: SimpleNamespace(model="mock", source="test"),
        raising=False,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.llm_support.model_selection.require_resolved_model",
        lambda *_a, **_k: SimpleNamespace(model="mock", source="test"),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.insights_narrative.resolve_insights_narrative_inputs",
        lambda _ctx: {
            "key_themes": [{"phrase": "budget", "evidence": ["q1"]}],
            "recurring_ideas": [],
        },
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.insights_narrative.write_llm_artifacts",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.insights_narrative.create_output_service",
        lambda *_a, **_k: object(),
    )
    from transcriptx.core.utils.config import get_config

    cfg = get_config()
    monkeypatch.setattr(cfg.analysis.insights, "narrative_enabled", True)
    monkeypatch.setattr(cfg.llm, "enabled", True)
    monkeypatch.setattr(cfg.llm, "provider", "ollama")
    monkeypatch.setattr(cfg.llm, "model", "mock")
    monkeypatch.setattr(cfg.llm, "seed", 1)
    monkeypatch.setattr(cfg.llm, "max_output_tokens", 200)

    class _Ctx:
        transcript_path = str(tmp_path / "t.json")

        def get_transcript_dir(self):
            return tmp_path

        def get_run_id(self):
            return "run"

        def get_runtime_flags(self):
            return {}

        def store_analysis_result(self, *_a, **_k):
            return None

    result = InsightsNarrativeAnalysis().run_from_context(_Ctx())
    assert result["status"] == "success"
    assert "budget risk" in result["payload"]["narrative"]


def test_insights_narrative_skips_when_disabled(monkeypatch) -> None:
    from transcriptx.core.utils.config import get_config

    cfg = get_config()
    monkeypatch.setattr(cfg.analysis.insights, "narrative_enabled", False)

    class _Ctx:
        transcript_path = "x.json"

    result = InsightsNarrativeAnalysis().run_from_context(_Ctx())
    assert result["status"] == "skipped"
    assert result["metrics"]["skip_reason"] == "narrative_disabled"
