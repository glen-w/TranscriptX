from typing import Any

from transcriptx.core.analysis.aggregation import ner as ner_aggregation  # type: ignore[import]
from transcriptx.core.pipeline.result_envelope import (  # type: ignore[import]
    PerTranscriptResult,
)
from transcriptx.core.pipeline.speaker_normalizer import (  # type: ignore[import]
    CanonicalSpeakerMap,
)
from transcriptx.core.domain.transcript_set import TranscriptSet  # type: ignore[import]
from transcriptx.io.transcript_service import TranscriptService  # type: ignore[import]


def test_aggregate_ner_group_canonical_and_unidentified(monkeypatch: Any) -> None:
    segments_map = {
        "a.json": [
            {"speaker": "Alice", "text": "Apple in Paris", "id": "s1"},
            {"speaker": "SPEAKER_00", "text": "Acme in Berlin", "id": "s2"},
        ],
        "b.json": [
            {"speaker": "Alicia", "text": "Apple and Acme", "id": "s3"},
        ],
    }

    def fake_load_segments(
        self: Any, transcript_path: str, use_cache: bool = True
    ) -> list[dict]:
        return segments_map[transcript_path]

    def fake_extract_named_entities(text: str) -> list[tuple[str, str]]:
        entities = []
        if "Apple" in text:
            entities.append(("Apple", "ORG"))
        if "Paris" in text:
            entities.append(("Paris", "GPE"))
        if "Acme" in text:
            entities.append(("Acme", "ORG"))
        if "Berlin" in text:
            entities.append(("Berlin", "GPE"))
        return entities

    monkeypatch.setattr(TranscriptService, "load_segments", fake_load_segments)
    monkeypatch.setattr(ner_aggregation, "extract_named_entities", fake_extract_named_entities)

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

    transcript_set = TranscriptSet.create(["a.json", "b.json"], name="Group")

    tables, summary, mentions_index = ner_aggregation.aggregate_ner_group(
        results, canonical_map, transcript_set
    )

    speaker_rows = tables["by_speaker"]
    assert all(row["speaker"] == "Alice" for row in speaker_rows)
    assert all(row["speaker"] != "SPEAKER_00" for row in speaker_rows)

    apple_row = next(
        row for row in speaker_rows if row["entity"] == "apple" and row["entity_type"] == "ORG"
    )
    assert apple_row["mentions"] == 2

    assert summary["excluded_unidentified_mentions"] > 0
    assert ("a", "s1") in mentions_index
    assert mentions_index[("a", "s1")]["speaker"] == "Alice"
