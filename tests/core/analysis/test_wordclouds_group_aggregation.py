from typing import Any

from transcriptx.core.analysis.aggregation.wordclouds import (  # type: ignore[import]
    aggregate_wordclouds_group,
)
from transcriptx.core.pipeline.result_envelope import (  # type: ignore[import]
    PerTranscriptResult,
)
from transcriptx.core.pipeline.speaker_normalizer import (  # type: ignore[import]
    CanonicalSpeakerMap,
)
from transcriptx.io.transcript_service import TranscriptService  # type: ignore[import]


def test_aggregate_wordclouds_group_combines_canonical(monkeypatch: Any) -> None:
    segments_map = {
        "a.json": [
            {"speaker": "Alice", "text": "Hello there"},
            {"speaker": "SPEAKER_00", "text": "um um"},
            {"text": "[noise]"},
        ],
        "b.json": [
            {"speaker": "Alicia", "text": "General   Kenobi"},
        ],
    }

    def fake_load_segments(
        self, transcript_path: str, use_cache: bool = True
    ) -> list[dict]:
        return segments_map[transcript_path]

    monkeypatch.setattr(TranscriptService, "load_segments", fake_load_segments)

    results = [
        PerTranscriptResult(
            transcript_path="a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="out/a",
            module_results={},
        ),
        PerTranscriptResult(
            transcript_path="b.json",
            transcript_key="b",
            run_id="r2",
            order_index=1,
            output_dir="out/b",
            module_results={},
        ),
    ]

    canonical_map = CanonicalSpeakerMap(
        transcript_to_speakers={
            "a.json": {"Alice": 1, "SPEAKER_00": 2},
            "b.json": {"Alicia": 1},
        },
        canonical_to_display={1: "Alice", 2: "SPEAKER_00"},
        transcript_to_display={
            "a.json": {"Alice": "Alice", "SPEAKER_00": "SPEAKER_00"},
            "b.json": {"Alicia": "Alicia"},
        },
    )

    grouped, summary = aggregate_wordclouds_group(results, canonical_map)

    assert grouped is not None
    assert summary is not None
    assert list(grouped.keys()) == ["Alice"]
    assert grouped["Alice"] == ["Hello there", "General Kenobi"]
    assert summary["speaker_count"] == 1
    assert summary["per_speaker_chunk_counts"]["Alice"] == 2
    assert summary["global_includes_unidentified"] is False
    assert "SPEAKER_00" in summary["excluded_speakers"]
    assert summary["excluded_chunks"] == 2
    assert summary["excluded_chars"] == len("um um") + len("[noise]")
    assert summary["grouped_hash"]
