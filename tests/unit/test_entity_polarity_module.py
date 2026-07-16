"""Offline unit tests for core.analysis.entity_sentiment (filename avoids auto-marker)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.entity_sentiment import (
    EntitySentimentAnalysis,
    normalize_entity_name,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("u.s.", "United States"),
        ("USA", "United States"),
        ("uk", "United Kingdom"),
        ("nyc", "New York"),
        ("acme corp", "Acme Corp"),
    ],
)
def test_normalize_entity_name(raw: str, expected: str) -> None:
    assert normalize_entity_name(raw) == expected


@pytest.mark.unit
def test_analyze_builds_stats_with_cached_sentiment() -> None:
    module = EntitySentimentAnalysis()
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Python is great and useful.",
            "start": 0.0,
            "end": 1.0,
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "Python helps teams ship.",
            "start": 1.0,
            "end": 2.0,
        },
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Ignore DATE entity types here.",
            "start": 2.0,
            "end": 3.0,
        },
        {"text": "no speaker"},
    ]
    sentiment_data = {
        "segments_with_sentiment": [
            {"sentiment": {"compound": 0.6, "pos": 0.7, "neu": 0.2, "neg": 0.1}},
            {"sentiment": {"compound": 0.4, "pos": 0.5, "neu": 0.4, "neg": 0.1}},
            {"sentiment": {"compound": -0.2, "pos": 0.1, "neu": 0.5, "neg": 0.4}},
        ]
    }

    def fake_ents(text: str):
        if "Python" in text:
            return [("Python", "ORG"), ("Python", "ORG")]
        if "DATE" in text:
            return [("yesterday", "DATE")]
        return []

    with (
        patch(
            "transcriptx.core.analysis.entity_sentiment.extract_named_entities",
            side_effect=fake_ents,
        ),
        patch(
            "transcriptx.core.analysis.entity_sentiment.score_sentiment",
            return_value={"compound": 0.1, "pos": 0.2, "neu": 0.7, "neg": 0.1},
        ),
        patch(
            "transcriptx.core.analysis.entity_sentiment.preprocess_for_sentiment",
            return_value="pre",
        ),
    ):
        result = module.analyze(segments, sentiment_data=sentiment_data)

    assert result["total_entities"] >= 1
    assert "Python" in result["entities"] or "python" in [
        e.lower() for e in result["entities"]
    ]
    stats = result["entity_stats"]
    assert stats
    first = next(iter(stats.values()))
    assert first["mention_count"] >= 2
    assert "speaker_breakdown" in first
    assert result["summary"]["total_entities"] == result["total_entities"]


@pytest.mark.unit
def test_analyze_computes_sentiment_when_cache_missing() -> None:
    module = EntitySentimentAnalysis()
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Acme rocks forever.",
            "start": 0.0,
            "end": 1.0,
        },
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Acme again today.",
            "start": 1.0,
            "end": 2.0,
        },
    ]
    with (
        patch(
            "transcriptx.core.analysis.entity_sentiment.extract_named_entities",
            return_value=[("Acme", "ORG")],
        ),
        patch(
            "transcriptx.core.analysis.entity_sentiment.preprocess_for_sentiment",
            return_value="",
        ),
        patch(
            "transcriptx.core.analysis.entity_sentiment.score_sentiment",
            return_value={"compound": 0.2, "pos": 0.3, "neu": 0.6, "neg": 0.1},
        ) as score,
    ):
        result = module.analyze(segments)
    assert score.call_count >= 2
    assert result["total_mentions"] >= 2


@pytest.mark.unit
def test_analyze_filters_single_mention_entities() -> None:
    module = EntitySentimentAnalysis()
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Only once.",
            "start": 0.0,
            "end": 1.0,
        }
    ]
    with (
        patch(
            "transcriptx.core.analysis.entity_sentiment.extract_named_entities",
            return_value=[("OnceOrg", "ORG")],
        ),
        patch(
            "transcriptx.core.analysis.entity_sentiment.score_sentiment",
            return_value={"compound": 0.0, "pos": 0.0, "neu": 1.0, "neg": 0.0},
        ),
        patch(
            "transcriptx.core.analysis.entity_sentiment.preprocess_for_sentiment",
            return_value="x",
        ),
    ):
        result = module.analyze(segments)
    assert result["total_entities"] == 0
    assert result["entity_stats"] == {}


@pytest.mark.unit
def test_run_from_context_success_and_error(tmp_path, monkeypatch) -> None:
    module = EntitySentimentAnalysis()
    stored: dict = {}

    context = SimpleNamespace(
        transcript_path=str(tmp_path / "t.json"),
        get_segments=lambda: [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Python Python",
                "start": 0.0,
                "end": 1.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Python rocks",
                "start": 1.0,
                "end": 2.0,
            },
        ],
        get_analysis_result=lambda name: None,
        get_transcript_dir=lambda: str(tmp_path),
        get_run_id=lambda: "run-1",
        get_runtime_flags=lambda: {},
        store_analysis_result=lambda name, results: stored.setdefault(name, results),
    )

    fake_out = MagicMock()
    fake_out.get_output_structure.return_value = SimpleNamespace(
        module_dir=tmp_path / "es"
    )

    with (
        patch(
            "transcriptx.core.analysis.entity_sentiment.extract_named_entities",
            return_value=[("Python", "ORG")],
        ),
        patch(
            "transcriptx.core.analysis.entity_sentiment.score_sentiment",
            return_value={"compound": 0.5, "pos": 0.5, "neu": 0.4, "neg": 0.1},
        ),
        patch(
            "transcriptx.core.analysis.entity_sentiment.preprocess_for_sentiment",
            return_value="p",
        ),
        patch(
            "transcriptx.core.output.output_service.create_output_service",
            return_value=fake_out,
        ),
        patch.object(module, "save_results"),
    ):
        ok = module.run_from_context(context)
    assert ok["status"] == "success"
    assert "entity_sentiment" in stored

    broken = SimpleNamespace(
        transcript_path=str(tmp_path / "t.json"),
        get_segments=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        get_analysis_result=lambda name: None,
        get_transcript_dir=lambda: str(tmp_path),
        get_run_id=lambda: "run-1",
        get_runtime_flags=lambda: {},
        store_analysis_result=lambda *a, **k: None,
    )
    err = module.run_from_context(broken)
    assert err["status"] == "error"
    assert "boom" in err["error"]


@pytest.mark.unit
def test_save_results_and_viz_helpers(tmp_path, monkeypatch) -> None:
    module = EntitySentimentAnalysis()
    results = {
        "entity_stats": {
            "Python": {
                "entity_type": "ORG",
                "mention_count": 5,
                "avg_sentiment": 0.4,
                "std_sentiment": 0.1,
                "pos_count": 3,
                "neu_count": 1,
                "neg_count": 1,
                "speaker_breakdown": {"Alice": 3, "Bob": 2},
                "example_segments": ["a", "b"],
            },
            "Paris": {
                "entity_type": "GPE",
                "mention_count": 2,
                "avg_sentiment": -0.2,
                "std_sentiment": 0.05,
                "pos_count": 0,
                "neu_count": 1,
                "neg_count": 1,
                "speaker_breakdown": {"Alice": 2},
                "example_segments": ["c"],
            },
        },
        "total_entities": 2,
        "total_mentions": 7,
    }
    output = MagicMock()
    output.base_name = "sample"
    output.get_output_structure.return_value = SimpleNamespace(
        module_dir=tmp_path, global_data_dir=tmp_path
    )
    output.save_data = MagicMock()
    output.save_chart = MagicMock()
    output.save_summary = MagicMock()

    fake_plt = MagicMock()
    monkeypatch.setattr(
        "transcriptx.core.analysis.entity_sentiment.plt", fake_plt
    )
    module._save_results(results, output)
    assert output.save_chart.call_count >= 2
    assert output.save_summary.called

    # Empty stats → early returns inside helpers
    empty = {"entity_stats": {}}
    module._create_sentiment_heatmap(empty, None, "b", output)
    module._create_entity_type_analysis(empty, None, "b", output)
    module._create_speaker_entity_analysis(empty, None, "b", output)
    module._create_analysis_summary(empty, None, "b", output)
    assert any(c.args[1] == "summary" for c in output.save_data.call_args_list)
