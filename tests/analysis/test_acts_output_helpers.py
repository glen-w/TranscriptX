"""Offline unit tests for acts output helpers (charts, summaries, tag_acts)."""

from __future__ import annotations

from collections import Counter
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.acts import output as acts_output
from transcriptx.core.analysis.acts.config import ClassificationMethod


def _seg(speaker: str, text: str, start: float, act: str = "statement") -> dict:
    return {
        "speaker": speaker,
        "speaker_db_id": {"Alice": 1, "Bob": 2}.get(
            speaker, abs(hash(speaker)) % 10000
        ),
        "text": text,
        "start": start,
        "end": start + 1.0,
        "dialogue_act": act,
    }


@pytest.mark.unit
def test_generate_acts_charts_saves_pie_bar_temporal() -> None:
    output_service = MagicMock()
    tagged = [
        _seg("Alice", "Hello?", 0.0, "question"),
        _seg("Alice", "Please do it.", 30.0, "suggestion"),
        _seg("Bob", "Okay.", 60.0, "acknowledgement"),
        _seg("Bob", "Sure.", 90.0, "acknowledgement"),
    ]
    global_counts = {"question": 1, "suggestion": 1, "acknowledgement": 2}
    per_speaker = {
        "Alice": {"question": 1, "suggestion": 1},
        "Bob": {"acknowledgement": 2},
    }

    acts_output.generate_acts_charts(
        output_service,
        tagged,
        global_counts,
        per_speaker,
        "base",
        title_prefix="Run",
        group_aggregate_viz_ids=True,
    )

    assert output_service.save_chart.call_count >= 4
    viz_ids = [call.args[0].viz_id for call in output_service.save_chart.call_args_list]
    assert any(v.startswith("group.acts.") for v in viz_ids)
    titles = [call.args[0].title for call in output_service.save_chart.call_args_list]
    assert any(t.startswith("Run — ") for t in titles)


@pytest.mark.unit
def test_generate_acts_charts_skips_zero_total_and_notifies_without_speakers() -> None:
    output_service = MagicMock()
    with patch.object(acts_output, "notify_user") as notify:
        acts_output.generate_acts_charts(
            output_service,
            [],
            {"statement": 0},
            {"SPEAKER_00": {"statement": 0}},
            "base",
        )
    notify.assert_called()
    # No named speakers => no bar/temporal/pie saves for speakers with total 0
    assert output_service.save_chart.call_count == 0


@pytest.mark.unit
def test_generate_acts_charts_filters_low_share_acts() -> None:
    output_service = MagicMock()
    # One act overwhelmingly dominant so filter keeps only the large share
    per_speaker = {"Alice": {"statement": 20, "question": 1}}
    global_counts = {"statement": 20, "question": 1}
    tagged = [_seg("Alice", "x", float(i), "statement") for i in range(20)]
    tagged.append(_seg("Alice", "?", 100.0, "question"))

    acts_output.generate_acts_charts(
        output_service, tagged, global_counts, per_speaker, "base"
    )
    pie_calls = [
        c
        for c in output_service.save_chart.call_args_list
        if c.kwargs.get("chart_type") == "pie"
    ]
    assert pie_calls
    for call in pie_calls:
        spec = call.args[0]
        assert "statement" in spec.categories
        assert "question" not in spec.categories


@pytest.mark.unit
def test_generate_method_summary_writes_files(tmp_path) -> None:
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Hi",
            "dialogue_act": "statement",
            "act_confidence": 0.9,
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "How?",
            "dialogue_act": "question",
            "act_confidence": 0.8,
        },
    ]
    with (
        patch.object(acts_output, "write_text") as write_text,
        patch.object(acts_output, "save_json") as save_json,
        patch.object(acts_output, "save_csv") as save_csv,
    ):
        acts_output._generate_method_summary(
            segments, "base", str(tmp_path), None, "ML"
        )
    write_text.assert_called_once()
    save_json.assert_called_once()
    save_csv.assert_called_once()


@pytest.mark.unit
def test_generate_comparison_summary_empty_and_with_disagreements(tmp_path) -> None:
    with (
        patch.object(acts_output, "write_text") as write_text,
        patch.object(acts_output, "save_json") as save_json,
    ):
        acts_output._generate_comparison_summary([], "base", str(tmp_path))
    write_text.assert_called_once()
    save_json.assert_called_once()
    assert save_json.call_args[0][0]["total_utterances"] == 0
    assert save_json.call_args[0][0]["agreement_rate"] == 0

    comparison = [
        {
            "text": "Hello there friend how are you doing today?",
            "ml_act": "statement",
            "rules_act": "question",
            "ml_confidence": 0.9,
            "rules_confidence": 0.4,
            "methods_agreed": False,
            "confidence_difference": 0.5,
        },
        {
            "text": "Okay",
            "ml_act": "acknowledgement",
            "rules_act": "acknowledgement",
            "ml_confidence": 0.8,
            "rules_confidence": 0.7,
            "methods_agreed": True,
            "confidence_difference": 0.1,
        },
    ]
    with (
        patch.object(acts_output, "write_text") as write_text,
        patch.object(acts_output, "save_json") as save_json,
    ):
        acts_output._generate_comparison_summary(comparison, "base", str(tmp_path))
    summary = save_json.call_args[0][0]
    assert summary["agreements"] == 1
    assert summary["disagreements"] == 1
    assert len(summary["sample_disagreements"]) == 1


@pytest.mark.unit
def test_tag_acts_happy_path_with_rules_method(tmp_path) -> None:
    transcript = tmp_path / "call.json"
    transcript.write_text("{}")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "What do you think?",
            "start": 0.0,
            "end": 1.0,
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "I agree.",
            "start": 1.0,
            "end": 2.0,
        },
    ]
    config = SimpleNamespace(
        method=ClassificationMethod.RULES,
        create_separate_outputs=False,
        both_methods_output_dir="both_methods",
    )
    mock_os = MagicMock()
    structure = SimpleNamespace(data_dir=out_dir / "acts" / "data")
    structure.data_dir.mkdir(parents=True)

    def fake_classify(text, context=None):
        if "?" in text:
            return {
                "act_type": "question",
                "confidence": 0.9,
                "method": "rules",
                "probabilities": {"question": 0.9},
            }
        return {
            "act_type": "statement",
            "confidence": 0.8,
            "method": "rules",
            "probabilities": {"statement": 0.8},
        }

    with (
        patch.object(acts_output, "get_act_config", return_value=config),
        patch.object(
            acts_output, "create_standard_output_structure", return_value=structure
        ),
        patch.object(acts_output, "create_output_service", return_value=mock_os),
        patch.object(acts_output, "classify_utterance", side_effect=fake_classify),
        patch.object(acts_output, "save_transcript") as save_tr,
        patch.object(acts_output, "write_text"),
        patch.object(acts_output, "save_json"),
        patch.object(acts_output, "save_csv"),
        patch.object(acts_output, "create_summary_json"),
        patch.object(acts_output, "generate_acts_charts") as gen_charts,
        patch.object(
            acts_output,
            "get_enriched_transcript_path",
            return_value=str(out_dir / "enriched.json"),
        ),
    ):
        acts_output.tag_acts(segments, "call", str(out_dir), {}, str(transcript))

    save_tr.assert_called()
    gen_charts.assert_called_once()
    mock_os.save_chart.assert_not_called()  # charts delegated to generate_acts_charts


@pytest.mark.unit
def test_tag_acts_both_methods_creates_separate_outputs(tmp_path) -> None:
    transcript = tmp_path / "call.json"
    transcript.write_text("{}")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Please help.",
            "start": 0.0,
            "end": 1.0,
        },
    ]
    config = SimpleNamespace(
        method=ClassificationMethod.BOTH,
        create_separate_outputs=True,
        both_methods_output_dir="both_methods",
    )
    structure = SimpleNamespace(data_dir=out_dir / "acts" / "data")
    structure.data_dir.mkdir(parents=True)

    both_result = {
        "act_type": "suggestion",
        "confidence": 0.85,
        "method": "both",
        "probabilities": {},
        "ml_result": {
            "act_type": "suggestion",
            "confidence": 0.9,
            "method": "heuristics",
        },
        "rules_result": {
            "act_type": "statement",
            "confidence": 0.7,
            "method": "rules",
        },
        "methods_agreed": False,
        "confidence_difference": 0.2,
    }

    with (
        patch.object(acts_output, "get_act_config", return_value=config),
        patch.object(
            acts_output, "create_standard_output_structure", return_value=structure
        ),
        patch.object(acts_output, "create_output_service", return_value=MagicMock()),
        patch.object(acts_output, "classify_utterance", return_value=both_result),
        patch.object(acts_output, "save_transcript"),
        patch.object(acts_output, "save_json"),
        patch.object(acts_output, "write_text"),
        patch.object(acts_output, "save_csv"),
        patch.object(acts_output, "create_summary_json"),
        patch.object(acts_output, "generate_acts_charts"),
        patch.object(acts_output, "_generate_method_summary") as method_summary,
        patch.object(acts_output, "_generate_comparison_summary") as comparison_summary,
        patch.object(
            acts_output,
            "get_enriched_transcript_path",
            return_value=str(out_dir / "enriched.json"),
        ),
    ):
        acts_output.tag_acts(segments, "call", str(out_dir), {}, str(transcript))

    assert method_summary.call_count == 2
    comparison_summary.assert_called_once()


@pytest.mark.unit
def test_generate_acts_charts_skips_speaker_without_temporal_points() -> None:
    output_service = MagicMock()
    # Speaker present in counts but tagged segments carry a different act only
    tagged = [_seg("Alice", "hi", 0.0, "other")]
    per_speaker = {"Alice": Counter({"question": 5})}
    acts_output.generate_acts_charts(
        output_service,
        tagged,
        {"question": 5},
        per_speaker,
        "base",
    )
    # global temporal may exist via speakers list + act_counts_global; per-speaker skipped
    assert output_service.save_chart.called
