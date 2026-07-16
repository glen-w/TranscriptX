"""Edge-case unit tests for 0.3.5 insights/voice group aggregators."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.aggregation import insights as insights_mod
from transcriptx.core.analysis.aggregation import voice as voice_mod
from transcriptx.core.analysis.aggregation.insights import aggregate_insights_group
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _ts() -> TranscriptSet:
    return TranscriptSet.create(["/x/a.json"], name="G", key="gk")


def _cmap() -> CanonicalSpeakerMap:
    return CanonicalSpeakerMap(
        transcript_to_speakers={"/x/a.json": {"1": 7}},
        canonical_to_display={7: "Alice"},
        transcript_to_display={"/x/a.json": {"1": "Alice"}},
    )


def _result(module_results: dict) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path="/x/a.json",
        transcript_key="a",
        run_id="r0",
        order_index=0,
        output_dir="o1",
        module_results=module_results,
    )


@pytest.mark.unit
def test_theme_score_dict_scalar_and_invalid() -> None:
    assert insights_mod._theme_score({"score": {"total": "2.5"}}) == 2.5
    assert insights_mod._theme_score({"score": {"total": "x"}}) is None
    assert insights_mod._theme_score({"score": 3}) == 3.0
    assert insights_mod._theme_score({"score": "bad"}) is None
    assert insights_mod._theme_score({}) is None


@pytest.mark.unit
def test_insights_artifact_relpath_and_empty_aggregate() -> None:
    assert insights_mod._artifact_relpath({}, "insights") is None
    assert (
        insights_mod._artifact_relpath(
            {"artifacts": [{"relative_path": "insights/x.json"}]}, "insights"
        )
        == "insights/x.json"
    )
    assert (
        insights_mod._artifact_relpath(
            {"artifacts": ["bad", {"path": "other.txt"}, {"path": "insights/y.json"}]},
            "insights",
        )
        == "insights/y.json"
    )
    assert aggregate_insights_group([], _cmap(), _ts()) is None
    assert (
        aggregate_insights_group(
            [_result({"insights": {"payload": {}}})], _cmap(), _ts()
        )
        is None
    )


@pytest.mark.unit
def test_aggregate_insights_skips_malformed_lists_and_blank_phrases() -> None:
    out = aggregate_insights_group(
        [
            _result(
                {
                    "insights": {
                        "payload": {
                            "key_themes": "bad",
                            "recurring_ideas": [{"phrase": ""}, {"text": "ok"}],
                            "notable_moments": "bad",
                        },
                        "artifacts": [
                            {"relative_path": "modules/insights/insights.json"}
                        ],
                    }
                }
            )
        ],
        _cmap(),
        _ts(),
    )
    assert out is not None
    assert out["session_rows"][0]["theme_count"] == 0
    assert len(out["content_rows"]) == 1
    assert out["content_rows"][0]["text"] == "ok"
    assert out["content_rows"][0]["source_artifact_relpath"] == (
        "modules/insights/insights.json"
    )


@pytest.mark.unit
def test_voice_baseline_median_and_artifact_relpath() -> None:
    assert voice_mod._baseline_median(None, "pitch") is None
    assert voice_mod._baseline_median({}, "pitch") is None
    assert voice_mod._baseline_median({"pitch": "x"}, "pitch") is None
    assert voice_mod._baseline_median({"pitch": {"median": None}}, "pitch") is None
    assert voice_mod._baseline_median({"pitch": {"median": "bad"}}, "pitch") is None
    assert voice_mod._baseline_median({"pitch": {"median": "1.5"}}, "pitch") == 1.5
    assert voice_mod._artifact_relpath({"artifacts": []}, "voice") is None
    assert (
        voice_mod._artifact_relpath(
            {"artifacts": [{"relative_path": "voice_mismatch.json"}]},
            "voice_mismatch",
        )
        == "voice_mismatch.json"
    )
