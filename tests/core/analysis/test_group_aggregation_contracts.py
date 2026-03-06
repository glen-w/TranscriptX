from typing import Any

from transcriptx.core.analysis.aggregation.emotion import aggregate_emotion_group
from transcriptx.core.analysis.aggregation.interactions import (
    aggregate_interactions_group,
)
from transcriptx.core.analysis.aggregation.schema import (
    validate_session_rows,
    validate_speaker_rows,
)
from transcriptx.core.analysis.aggregation.sentiment import aggregate_sentiment_group
from transcriptx.core.analysis.aggregation.topics import aggregate_topics_group
from transcriptx.core.analysis.stats.aggregation import aggregate_stats_group
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap
from transcriptx.io.transcript_service import TranscriptService


def _build_canonical_map() -> CanonicalSpeakerMap:
    return CanonicalSpeakerMap(
        transcript_to_speakers={"a.json": {"Alice": 1}},
        canonical_to_display={1: "Alice"},
        transcript_to_display={"a.json": {"Alice": "Alice"}},
    )


def _build_transcript_set() -> TranscriptSet:
    return TranscriptSet.create(["a.json"], name="Group")


def test_stats_group_contract() -> None:
    results = [
        PerTranscriptResult(
            transcript_path="a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="out/a",
            module_results={
                "stats": {
                    "payload": {
                        "speaker_stats": [(10.0, "Alice", 100, 10, 0.1, 0.0)],
                        "sentiment_summary": {
                            "Alice": {
                                "compound": 0.2,
                                "pos": 0.3,
                                "neu": 0.4,
                                "neg": 0.1,
                            }
                        },
                    }
                }
            },
        )
    ]
    outcome = aggregate_stats_group(
        results, _build_canonical_map(), _build_transcript_set()
    )
    assert outcome is not None
    ok_sessions, _ = validate_session_rows(outcome["session_rows"])
    ok_speakers, _ = validate_speaker_rows(outcome["speaker_rows"])
    assert ok_sessions
    assert ok_speakers


def test_sentiment_group_contract() -> None:
    results = [
        PerTranscriptResult(
            transcript_path="a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="out/a",
            module_results={
                "sentiment": {
                    "payload": {
                        "speaker_stats": {
                            "Alice": {
                                "count": 2,
                                "compound_mean": 0.1,
                                "pos_mean": 0.2,
                                "neu_mean": 0.6,
                                "neg_mean": 0.2,
                            }
                        },
                        "global_stats": {
                            "count": 2,
                            "compound_mean": 0.1,
                            "pos_mean": 0.2,
                            "neu_mean": 0.6,
                            "neg_mean": 0.2,
                        },
                    }
                }
            },
        )
    ]
    outcome = aggregate_sentiment_group(
        results, _build_canonical_map(), _build_transcript_set()
    )
    assert outcome is not None
    ok_sessions, _ = validate_session_rows(outcome["session_rows"])
    ok_speakers, _ = validate_speaker_rows(outcome["speaker_rows"])
    assert ok_sessions
    assert ok_speakers


def test_emotion_group_contract() -> None:
    results = [
        PerTranscriptResult(
            transcript_path="a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="out/a",
            module_results={
                "emotion": {
                    "payload": {
                        "speaker_stats": {"Alice": {"joy": 0.7, "sad": 0.3}},
                        "global_stats": {"joy": 0.6, "sad": 0.4},
                    }
                }
            },
        )
    ]
    outcome = aggregate_emotion_group(
        results, _build_canonical_map(), _build_transcript_set()
    )
    assert outcome is not None
    ok_sessions, _ = validate_session_rows(outcome["session_rows"])
    ok_speakers, _ = validate_speaker_rows(outcome["speaker_rows"])
    assert ok_sessions
    assert ok_speakers


def test_interactions_group_contract() -> None:
    results = [
        PerTranscriptResult(
            transcript_path="a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="out/a",
            module_results={
                "interactions": {
                    "payload": {
                        "interruption_initiated": {"Alice": 2},
                        "interruption_received": {"Alice": 1},
                        "responses_initiated": {"Alice": 3},
                        "responses_received": {"Alice": 2},
                        "dominance_scores": {"Alice": 0.5},
                        "total_interactions_count": 5,
                        "unique_speakers": 1,
                    }
                }
            },
        )
    ]
    outcome = aggregate_interactions_group(
        results, _build_canonical_map(), _build_transcript_set()
    )
    assert outcome is not None
    ok_sessions, _ = validate_session_rows(outcome["session_rows"])
    ok_speakers, _ = validate_speaker_rows(outcome["speaker_rows"])
    assert ok_sessions
    assert ok_speakers


def test_topic_modeling_group_contract(monkeypatch: Any) -> None:
    def fake_load_segments(
        self: Any, transcript_path: str, use_cache: bool = True
    ) -> list[dict]:
        return [
            {"speaker": "Alice", "text": "alpha beta", "start": 0.0},
            {"speaker": "Alice", "text": "beta gamma", "start": 1.0},
            {"speaker": "Alice", "text": "gamma delta", "start": 2.0},
        ]

    def fake_lda_analysis(
        texts: list[str], speakers: list[str | None], time_labels: list[float]
    ) -> dict:
        return {
            "topics": [{"topic_id": 0, "words": ["alpha", "beta"]}],
            "doc_topics": [[0.7], [0.2], [0.1]],
        }

    monkeypatch.setattr(TranscriptService, "load_segments", fake_load_segments)
    monkeypatch.setattr(
        "transcriptx.core.analysis.aggregation.topics.perform_enhanced_lda_analysis",
        fake_lda_analysis,
    )

    results = [
        PerTranscriptResult(
            transcript_path="a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="out/a",
            module_results={},
        )
    ]
    outcome = aggregate_topics_group(
        results, _build_canonical_map(), _build_transcript_set()
    )
    assert outcome is not None
    ok_sessions, _ = validate_session_rows(outcome["session_rows"])
    ok_speakers, _ = validate_speaker_rows(outcome["speaker_rows"])
    assert ok_sessions
    assert ok_speakers
