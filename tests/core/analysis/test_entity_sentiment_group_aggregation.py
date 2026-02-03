from typing import Any

from transcriptx.core.analysis.aggregation.entity_sentiment import (  # type: ignore[import]
    aggregate_entity_sentiment_group,
)
from transcriptx.core.domain.transcript_set import TranscriptSet  # type: ignore[import]
from transcriptx.core.pipeline.result_envelope import (  # type: ignore[import]
    PerTranscriptResult,
)
from transcriptx.core.pipeline.speaker_normalizer import (  # type: ignore[import]
    CanonicalSpeakerMap,
)


def test_entity_sentiment_aggregation_excludes_unidentified() -> None:
    mentions_index = {
        ("a", "s1"): {
            "speaker": "Alice",
            "entities": [("apple", "ORG"), ("paris", "GPE")],
        },
        ("a", "s2"): {
            "speaker": None,
            "entities": [("acme", "ORG")],
        },
        ("b", "s3"): {
            "speaker": "Alice",
            "entities": [("apple", "ORG")],
        },
    }

    sentiment_a = [
        {"id": "s1", "text": "Apple", "sentiment": {"compound": 0.5, "pos": 0.6, "neu": 0.3, "neg": 0.1}},
        {"id": "s2", "text": "Acme", "sentiment": {"compound": -0.2, "pos": 0.1, "neu": 0.4, "neg": 0.5}},
    ]
    sentiment_b = [
        {"id": "s3", "text": "Apple", "sentiment": {"compound": -0.5, "pos": 0.1, "neu": 0.3, "neg": 0.6}},
    ]

    results = [
        PerTranscriptResult(
            transcript_path="a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="out/a",
            module_results={"sentiment": {"segments_with_sentiment": sentiment_a}},
        ),
        PerTranscriptResult(
            transcript_path="b.json",
            transcript_key="b",
            run_id="r2",
            order_index=1,
            output_dir="out/b",
            module_results={"sentiment": {"segments_with_sentiment": sentiment_b}},
        ),
    ]

    canonical_map = CanonicalSpeakerMap(
        transcript_to_speakers={},
        canonical_to_display={},
        transcript_to_display={},
    )
    transcript_set = TranscriptSet.create(["a.json", "b.json"], name="Group")

    tables, summary = aggregate_entity_sentiment_group(
        results, canonical_map, transcript_set, mentions_index
    )

    speaker_rows = tables["by_speaker"]
    assert all(row["speaker"] == "Alice" for row in speaker_rows)

    apple_row = next(row for row in speaker_rows if row["entity"] == "apple")
    assert apple_row["mentions"] == 2
    assert abs(apple_row["mean_sentiment"] - 0.0) < 1e-6
    assert summary["top_positive"]
