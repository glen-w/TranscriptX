"""Offline unit tests for conversation_loops helpers and analysis entry points."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.conversation_loops.analysis import (
    ConversationLoop,
    ConversationLoopDetector,
    ConversationLoopsAnalysis,
    analyze_conversation_loops,
    analyze_loop_patterns,
    create_analysis_summary,
    create_loop_act_analysis,
    create_loop_network,
    create_loop_timeline,
    save_loop_data,
)


def _loop(
    lid: int = 0,
    a: str = "Alice",
    b: str = "Bob",
    t1: str = "Can you help?",
    t2: str = "Yes.",
    t3: str = "Thanks!",
    act1: str = "question",
    act2: str = "statement",
    act3: str = "acknowledgement",
) -> ConversationLoop:
    return ConversationLoop(
        loop_id=lid,
        speaker_a=a,
        speaker_b=b,
        turn_1_index=0,
        turn_2_index=1,
        turn_3_index=2,
        turn_1_text=t1,
        turn_2_text=t2,
        turn_3_text=t3,
        turn_1_act=act1,
        turn_2_act=act2,
        turn_3_act=act3,
        turn_1_timestamp=0.0,
        turn_2_timestamp=10.0,
        turn_3_timestamp=20.0,
        turn_1_sentiment=0.1,
        turn_2_sentiment=0.2,
        turn_3_sentiment=0.0,
        gap_1_2=1.0,
        gap_2_3=2.0,
    )


@pytest.mark.unit
def test_is_monologue_similarity_thresholds() -> None:
    det = ConversationLoopDetector()
    assert det._is_monologue("same words here now", "same words here now") is True
    assert (
        det._is_monologue("completely different text", "other content entirely")
        is False
    )
    assert det._is_monologue("", "hello") is False
    assert det._is_monologue("hello", "") is False


@pytest.mark.unit
def test_detect_loops_finds_question_response_return() -> None:
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Can you help?",
            "start": 0.0,
            "end": 1.0,
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "Sure thing.",
            "start": 1.0,
            "end": 2.0,
        },
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Great!",
            "start": 2.0,
            "end": 3.0,
        },
    ]
    with (
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.classify_utterance",
            side_effect=lambda text: "question" if "?" in text else "statement",
        ),
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.score_sentiment",
            return_value={"compound": 0.1},
        ),
    ):
        loops = ConversationLoopDetector().detect_loops(segments)
    assert len(loops) == 1
    assert loops[0].speaker_a == "Alice"
    assert loops[0].speaker_b == "Bob"


@pytest.mark.unit
def test_detect_loops_excludes_monologue_and_warns_on_speaker_map() -> None:
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Please do this work now please",
            "start": 0.0,
            "end": 1.0,
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "Ok",
            "start": 1.0,
            "end": 2.0,
        },
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Please do this work now please",
            "start": 2.0,
            "end": 3.0,
        },
    ]
    with (
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.classify_utterance",
            return_value="suggestion",
        ),
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.score_sentiment",
            return_value=0.0,
        ),
        pytest.warns(DeprecationWarning),
    ):
        loops = ConversationLoopDetector(exclude_monologues=True).detect_loops(
            segments, speaker_map={"unused": "x"}
        )
    assert loops == []


@pytest.mark.unit
def test_analyze_loop_patterns_empty_and_populated() -> None:
    empty = analyze_loop_patterns([])
    assert empty["total_loops"] == 0
    assert empty["gap_statistics"]["gap_1_2"]["mean"] == 0

    with pytest.warns(DeprecationWarning):
        result = analyze_loop_patterns([_loop(), _loop(1)], speaker_map={"a": "b"})
    assert result["total_loops"] == 2
    assert result["unique_speaker_pairs"] == 1
    assert "Alice ↔ Bob" in result["speaker_pair_counts"]
    assert result["sentiment_statistics"]["turn_1"]["mean"] == pytest.approx(0.1)


@pytest.mark.unit
def test_save_loop_data_writes_global_and_speaker(tmp_path) -> None:
    structure = SimpleNamespace(
        global_data_dir=tmp_path,
        speaker_data_dir=tmp_path,
    )
    long_text = "x" * 150
    loops = [_loop(t1=long_text, t2=long_text, t3=long_text)]
    with (
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.save_global_data"
        ) as save_g,
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.save_speaker_data"
        ) as save_s,
        pytest.warns(DeprecationWarning),
    ):
        save_loop_data(
            loops, speaker_map={"a": "b"}, output_structure=structure, base_name="base"
        )
    assert save_g.call_count == 2
    assert save_s.call_count == 4  # csv+json per Alice and Bob


@pytest.mark.unit
def test_create_loop_network_and_timeline_and_act_charts() -> None:
    output_service = MagicMock()
    analysis = analyze_loop_patterns([_loop(), _loop(1, a="Carol", b="Dave")])
    create_loop_network(analysis, None, "base", output_service=output_service)
    assert output_service.save_chart.called
    spec = output_service.save_chart.call_args[0][0]
    assert spec.chart_intent == "network_graph"

    output_service.reset_mock()
    create_loop_timeline([_loop()], None, None, "base", output_service=output_service)
    assert output_service.save_chart.called
    assert output_service.save_chart.call_args.kwargs.get("chart_type") == "timeline"

    output_service.reset_mock()
    create_loop_act_analysis([_loop()], None, "base", output_service=output_service)
    assert output_service.save_chart.called
    assert output_service.save_chart.call_args.kwargs.get("chart_type") == "bar"


@pytest.mark.unit
def test_create_loop_helpers_noop_without_data_or_service() -> None:
    create_loop_network({"speaker_pair_counts": {}}, None, "base")
    create_loop_timeline([], None, None, "base", output_service=MagicMock())
    create_loop_act_analysis([], None, "base", output_service=MagicMock())
    # with pairs but no service → builds graph but skips save
    create_loop_network(
        {"speaker_pair_counts": {"Alice ↔ Bob": 2}}, None, "base", output_service=None
    )


@pytest.mark.unit
def test_create_analysis_summary_writes_json_and_text(tmp_path) -> None:
    structure = SimpleNamespace(global_data_dir=tmp_path)
    results = analyze_loop_patterns([_loop()])
    with (
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.save_global_data"
        ) as save_g,
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.write_text"
        ) as write_text,
    ):
        create_analysis_summary(results, structure, "base")
    save_g.assert_called_once()
    write_text.assert_called_once()
    text = write_text.call_args[0][1]
    assert "Total Loops Detected" in text


@pytest.mark.unit
def test_conversation_loops_analysis_analyze_and_save() -> None:
    mod = ConversationLoopsAnalysis(
        {"max_intermediate_turns": 2, "exclude_monologues": True}
    )
    with patch.object(
        ConversationLoopDetector,
        "detect_loops",
        return_value=[_loop()],
    ):
        result = mod.analyze([{"speaker": "Alice", "text": "?", "start": 0, "end": 1}])
    assert result["summary"]["total_loops"] == 1
    assert result["statistics"] is result["summary"]

    output_service = MagicMock()
    output_service.base_name = "base"
    output_service.get_output_structure.return_value = SimpleNamespace()
    with (
        patch.object(mod, "_create_loop_network") as net,
        patch.object(mod, "_create_loop_timeline") as timeline,
        patch.object(mod, "_create_loop_act_analysis") as acts,
        patch.object(mod, "_create_analysis_summary") as summary,
    ):
        mod._save_results(result, output_service)
    assert output_service.save_data.call_count == 2
    net.assert_called_once()
    timeline.assert_called_once()
    acts.assert_called_once()
    summary.assert_called_once()


@pytest.mark.unit
def test_save_results_skips_viz_when_no_loops() -> None:
    mod = ConversationLoopsAnalysis()
    output_service = MagicMock()
    output_service.base_name = "base"
    output_service.get_output_structure.return_value = SimpleNamespace()
    with patch.object(mod, "_create_analysis_summary") as summary:
        mod._save_results({"loops": [], "total_loops": 0}, output_service)
    summary.assert_called_once()
    # network/timeline helpers not invoked when loops empty
    assert output_service.save_data.call_count == 2


@pytest.mark.unit
def test_analysis_viz_wrappers_delegate() -> None:
    mod = ConversationLoopsAnalysis()
    output_service = MagicMock()
    output_service.base_name = "base"
    output_service.get_output_structure.return_value = "struct"
    with (
        patch(
            "transcriptx.core.analysis.conversation_loops.create_loop_network"
        ) as net,
        patch(
            "transcriptx.core.analysis.conversation_loops.create_loop_timeline"
        ) as timeline,
        patch(
            "transcriptx.core.analysis.conversation_loops.create_loop_act_analysis"
        ) as acts,
        patch(
            "transcriptx.core.analysis.conversation_loops.create_analysis_summary"
        ) as summary,
    ):
        mod._create_loop_network(
            {"speaker_pair_counts": {}}, "struct", "base", output_service
        )
        mod._create_loop_timeline([_loop()], None, None, None, output_service)
        mod._create_loop_act_analysis([_loop()], "struct", "base", output_service)
        mod._create_analysis_summary(
            {"total_loops": 0, "unique_speaker_pairs": 0},
            "struct",
            "base",
            output_service,
        )
    net.assert_called_once()
    timeline.assert_called_once()
    acts.assert_called_once()
    summary.assert_called_once()
    output_service.save_summary.assert_called_once()


@pytest.mark.unit
def test_analyze_conversation_loops_entry_orchestrates(tmp_path) -> None:
    structure = SimpleNamespace(global_data_dir=tmp_path)
    fake_service = MagicMock()
    with (
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.create_standard_output_structure",
            return_value=structure,
        ),
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.create_output_service",
            return_value=fake_service,
        ) as create_svc,
        patch.object(ConversationLoopDetector, "detect_loops", return_value=[_loop()]),
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.save_loop_data"
        ) as save,
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.create_loop_network"
        ) as net,
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.create_loop_timeline"
        ) as timeline,
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.create_loop_act_analysis"
        ) as acts,
        patch(
            "transcriptx.core.analysis.conversation_loops.analysis.create_analysis_summary"
        ) as summary,
    ):
        result = analyze_conversation_loops(
            [{"speaker": "Alice", "text": "?", "start": 0, "end": 1}],
            "base",
            str(tmp_path),
        )
    assert result["total_loops"] == 1
    create_svc.assert_called_once()
    save.assert_called_once()
    net.assert_called_once()
    timeline.assert_called_once()
    acts.assert_called_once()
    summary.assert_called_once()
    assert net.call_args.kwargs.get("output_service") is fake_service
    assert timeline.call_args.kwargs.get("output_service") is fake_service
    assert acts.call_args.kwargs.get("output_service") is fake_service
