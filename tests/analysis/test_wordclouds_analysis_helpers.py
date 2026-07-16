"""Offline unit tests for wordclouds analysis helpers with stubbed I/O."""

from __future__ import annotations

from collections import Counter
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.wordclouds import analysis as wc


@pytest.mark.unit
def test_group_texts_by_speaker_named_and_fallback() -> None:
    segments = [
        {"speaker": "Alice", "speaker_db_id": 1, "text": "hello world"},
        {"speaker": "Bob", "speaker_db_id": 2, "text": "hi there"},
        {"speaker": "Alice", "speaker_db_id": 1, "text": "again"},
    ]
    with patch.object(wc, "_get_ignored_ids", return_value=set()):
        grouped = wc.group_texts_by_speaker(segments)
    assert "Alice" in grouped
    assert "Bob" in grouped
    assert len(grouped["Alice"]) == 2


@pytest.mark.unit
def test_group_texts_by_speaker_ignores_ids_and_falls_back() -> None:
    segments = [
        {"speaker": "SPEAKER_00", "text": "diag only"},
        {"speaker": "SPEAKER_01", "text": "also diag"},
    ]
    with patch.object(wc, "_get_ignored_ids", return_value=set()):
        grouped = wc.group_texts_by_speaker(segments)
    # Unidentified display names go to fallback when no eligible named speakers
    assert grouped
    assert any("diag" in " ".join(texts) for texts in grouped.values())


@pytest.mark.unit
def test_group_texts_skips_ignored_display_names() -> None:
    segments = [
        {"speaker": "Alice", "speaker_db_id": 1, "text": "keep"},
        {"speaker": "Bob", "speaker_db_id": 2, "text": "drop"},
    ]
    with patch.object(wc, "_get_ignored_ids", return_value={"Bob"}):
        grouped = wc.group_texts_by_speaker(segments)
    assert "Alice" in grouped
    assert "Bob" not in grouped


@pytest.mark.unit
def test_wordclouds_analyze_uses_eligibility_filtered_segments() -> None:
    module = wc.WordcloudsAnalysis()
    module._eligibility_result = {
        "filtered_segments": [
            {"speaker": "Alice", "content_text": "alpha beta"},
            {"speaker": "Bob", "content_text": "gamma"},
            {"speaker": "", "content_text": "ignore"},
            "skip-me",
        ],
        "tic_mask": ["um", "uh"],
    }
    result = module.analyze([{"speaker": "X", "text": "unused"}])
    assert result["grouped_texts"]["Alice"] == ["alpha beta"]
    assert result["grouped_texts"]["Bob"] == ["gamma"]
    assert result["tic_list"] == ["um", "uh"]
    assert result["eligibility_fallback"] is False


@pytest.mark.unit
def test_wordclouds_analyze_fallback_builds_tic_list() -> None:
    module = wc.WordcloudsAnalysis()
    module._eligibility_result = {}
    segments = [
        {"speaker": "Alice", "speaker_db_id": 1, "text": "hello there"},
    ]
    with (
        patch.object(wc, "group_texts_by_speaker", return_value={"Alice": ["hello"]}),
        patch(
            "transcriptx.core.analysis.tics.extract_tics_and_top_words",
            return_value=({"Alice": {"um": 2}}, {}),
        ),
        patch(
            "transcriptx.core.utils.nlp_utils.build_tic_mask",
            return_value={"um"},
        ),
    ):
        result = module.analyze(segments)
    assert result["eligibility_fallback"] is True
    assert "um" in result["tic_list"]


@pytest.mark.unit
def test_run_from_context_clears_eligibility() -> None:
    module = wc.WordcloudsAnalysis()
    ctx = MagicMock()
    ctx.get_analysis_result.return_value = {"filtered_segments": []}
    with patch.object(
        wc.AnalysisModule, "run_from_context", return_value={"ok": True}
    ) as parent:
        out = module.run_from_context(ctx)
    assert out == {"ok": True}
    parent.assert_called_once()
    assert module._eligibility_result is None


@pytest.mark.unit
def test_run_all_wordclouds_empty_grouped_returns_early(tmp_path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    structure = SimpleNamespace(
        transcript_dir=str(tmp_path),
        global_data_dir=tmp_path / "g",
        speaker_data_dir=tmp_path / "s",
    )
    with (
        patch.object(
            wc, "create_standard_output_structure", return_value=structure
        ),
        patch.object(wc, "create_output_service", return_value=MagicMock()),
        patch.object(wc, "notify_user") as notify,
        patch.object(wc, "generate_wordcloud") as gen,
    ):
        wc.run_all_wordclouds(str(transcript), [], grouped_texts={})
    notify.assert_called()
    gen.assert_not_called()


@pytest.mark.unit
def test_run_all_wordclouds_load_failure_notifies(tmp_path) -> None:
    transcript = tmp_path / "missing.json"
    structure = SimpleNamespace(transcript_dir=str(tmp_path))
    with (
        patch.object(
            wc, "create_standard_output_structure", return_value=structure
        ),
        patch.object(wc, "create_output_service", return_value=MagicMock()),
        patch.object(wc, "load_segments", side_effect=RuntimeError("boom")),
        patch.object(wc, "notify_user") as notify,
    ):
        wc.run_all_wordclouds(str(transcript), [])
    notify.assert_called()


@pytest.mark.unit
def test_run_all_wordclouds_with_stubbed_generators(tmp_path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    structure = SimpleNamespace(
        transcript_dir=str(tmp_path),
        global_data_dir=tmp_path / "g",
        speaker_data_dir=tmp_path / "s",
    )
    structure.global_data_dir.mkdir()
    structure.speaker_data_dir.mkdir()
    fake_fig = MagicMock()
    fake_ax = MagicMock()
    fake_wc = MagicMock()
    fake_wc_cls = MagicMock(
        return_value=MagicMock(generate_from_frequencies=MagicMock(return_value=fake_wc))
    )
    fake_token = MagicMock(text="noun", pos_="NOUN")
    fake_doc = [fake_token]

    with (
        patch.object(
            wc, "create_standard_output_structure", return_value=structure
        ),
        patch.object(wc, "create_output_service", return_value=MagicMock()),
        patch.object(
            wc, "generate_wordcloud", return_value=Counter({"hello": 2})
        ) as gen_basic,
        patch.object(wc, "save_freq_json_csv"),
        patch.object(wc, "generate_tfidf_wordclouds") as tfidf,
        patch.object(wc, "generate_bigram_wordclouds") as bigrams,
        patch.object(wc, "generate_bigram_tfidf_wordclouds") as bigram_tfidf,
        patch.object(wc, "generate_tic_wordclouds") as tics,
        patch.object(wc, "generate_pos_wordclouds") as pos,
        patch.object(
            wc, "tokenize_and_filter", return_value=["alpha", "beta", "gamma"]
        ),
        patch.object(wc, "_get_wordcloud_class", return_value=fake_wc_cls),
        patch.object(wc, "_wordcloud_figure", return_value=(fake_fig, fake_ax)),
        patch.object(wc, "save_global_chart", return_value="/tmp/chart.png"),
        patch.object(wc, "_build_terms_payload", return_value={"terms": []}),
        patch.object(wc, "_save_terms_json", return_value="/tmp/terms.json"),
        patch.object(wc, "_relative_to_transcript", return_value="rel"),
        patch.object(wc, "_save_wordcloud_view"),
        patch.object(wc, "nlp", return_value=fake_doc),
        patch.object(wc, "ALL_STOPWORDS", set()),
        patch.object(wc, "plt", MagicMock()),
    ):
        wc.run_all_wordclouds(
            str(transcript),
            ["um"],
            transcript_dir=str(tmp_path),
            grouped_texts={"Alice": ["alpha beta gamma"], "Bob": ["hello world"]},
        )

    assert gen_basic.call_count >= 2  # speakers + global
    tfidf.assert_called_once()
    bigrams.assert_called_once()
    bigram_tfidf.assert_called_once()
    tics.assert_called_once()
    assert pos.call_count == 3


@pytest.mark.unit
def test_run_all_wordclouds_tolerates_generator_errors(tmp_path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    structure = SimpleNamespace(transcript_dir=str(tmp_path))
    with (
        patch.object(
            wc, "create_standard_output_structure", return_value=structure
        ),
        patch.object(wc, "create_output_service", return_value=MagicMock()),
        patch.object(wc, "generate_wordcloud", side_effect=RuntimeError("fail")),
        patch.object(wc, "generate_tfidf_wordclouds", side_effect=RuntimeError("x")),
        patch.object(wc, "generate_bigram_wordclouds", side_effect=RuntimeError("x")),
        patch.object(
            wc, "generate_bigram_tfidf_wordclouds", side_effect=RuntimeError("x")
        ),
        patch.object(wc, "generate_tic_wordclouds", side_effect=RuntimeError("x")),
        patch.object(wc, "generate_pos_wordclouds", side_effect=RuntimeError("x")),
        patch.object(
            wc, "tokenize_and_filter", side_effect=RuntimeError("bigram fail")
        ),
        patch.object(wc, "nlp", side_effect=RuntimeError("pos fail")),
        patch.object(wc, "notify_user"),
        patch.object(wc, "plt", MagicMock()),
    ):
        # Should not raise
        wc.run_all_wordclouds(
            str(transcript),
            [],
            transcript_dir=str(tmp_path),
            grouped_texts={"Alice": ["text here"]},
        )


@pytest.mark.unit
def test_generate_wordclouds_uses_temp_and_run_all(tmp_path) -> None:
    segments = [
        {"speaker": "Alice", "speaker_db_id": 1, "text": "hello"},
    ]
    with (
        patch.object(wc, "create_output_service", return_value=MagicMock()),
        patch.object(wc, "group_texts_by_speaker", return_value={"Alice": ["hello"]}),
        patch.object(wc, "load_tics", return_value=["um"]),
        patch.object(wc, "run_all_wordclouds") as run_all,
    ):
        wc.generate_wordclouds(segments, "base", str(tmp_path))
    run_all.assert_called_once()
    assert run_all.call_args.kwargs.get("transcript_dir") == str(tmp_path)


@pytest.mark.unit
def test_save_results_delegates_to_run_all() -> None:
    module = wc.WordcloudsAnalysis()
    output_service = MagicMock()
    output_service.transcript_path = "/tmp/t.json"
    structure = SimpleNamespace(transcript_dir="/tmp/out")
    output_service.get_output_structure.return_value = structure
    with patch.object(wc, "run_all_wordclouds") as run_all:
        module._save_results(
            {"tic_list": ["um"], "grouped_texts": {"A": ["x"]}},
            output_service,
        )
    run_all.assert_called_once_with(
        "/tmp/t.json",
        ["um"],
        transcript_dir="/tmp/out",
        grouped_texts={"A": ["x"]},
    )


@pytest.mark.unit
def test_getattr_active_output_service() -> None:
    with patch.object(wc._wc_output_bridge, "_ACTIVE_OUTPUT_SERVICE", "svc"):
        assert wc.__getattr__("_ACTIVE_OUTPUT_SERVICE") == "svc"
    with pytest.raises(AttributeError):
        wc.__getattr__("nope")
