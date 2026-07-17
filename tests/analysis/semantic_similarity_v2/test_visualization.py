"""Chart contract tests for semantic_similarity_v2 visualizations."""

from __future__ import annotations

import json

from transcriptx.core.output.output_service import create_output_service
from transcriptx.core.analysis.semantic_similarity_v2.visualization import (
    create_visualizations_v2,
)


class FakeOutputService:
    def __init__(self) -> None:
        self.saved_specs = []

    def save_chart(self, spec):
        self.saved_specs.append(spec)
        return {"static": f"/tmp/{spec.name}.png", "dynamic": None}


def test_create_visualizations_v2_emits_legacy_equivalent_chart_specs() -> None:
    output_service = FakeOutputService()
    results = {
        "speaker_repetitions": {
            "Alice": [
                {
                    "segment1": {"speaker": "Alice", "text": "one two three"},
                    "segment2": {"speaker": "Alice", "text": "one two again"},
                    "similarity": 0.91,
                    "type": "self",
                }
            ],
            "Bob": [
                {
                    "segment1": {"speaker": "Bob", "text": "four five six"},
                    "segment2": {"speaker": "Bob", "text": "four five again"},
                    "similarity": 0.87,
                    "type": "self",
                }
            ],
        },
        "cross_speaker_repetitions": [
            {
                "segment1": {"speaker": "Alice", "text": "shared idea"},
                "segment2": {"speaker": "Bob", "text": "same idea"},
                "similarity": 0.82,
                "type": "cross",
                "agreement_type": "paraphrase",
            }
        ],
    }

    paths = create_visualizations_v2(
        results, output_service, "sample_transcript", "SEMANTIC_V2"
    )

    assert len(paths) == 6
    assert {spec.module for spec in output_service.saved_specs} == {
        "semantic_similarity_v2"
    }
    assert {spec.viz_id for spec in output_service.saved_specs} == {
        "semantic_similarity_v2.speaker_repetition_frequency.global",
        "semantic_similarity_v2.agreement_disagreement_breakdown.global",
        "semantic_similarity_v2.similarity_distribution.global",
        "semantic_similarity_v2.speaker_repetitions.global",
        "semantic_similarity_v2.classification.global",
        "semantic_similarity_v2.speaker_similarity.global",
    }


def test_create_visualizations_v2_records_chart_artifact_metadata(tmp_path) -> None:
    transcript_path = tmp_path / "sample.json"
    transcript_path.write_text("{}", encoding="utf-8")
    output_service = create_output_service(
        str(transcript_path),
        "semantic_similarity_v2",
        output_dir=str(tmp_path / "run"),
        run_id="run-v2",
    )
    results = {
        "speaker_repetitions": {
            "Alice": [
                {
                    "segment1": {"speaker": "Alice", "text": "one two three"},
                    "segment2": {"speaker": "Alice", "text": "one two again"},
                    "similarity": 0.91,
                    "type": "self",
                }
            ],
        },
        "cross_speaker_repetitions": [
            {
                "segment1": {"speaker": "Alice", "text": "shared idea"},
                "segment2": {"speaker": "Bob", "text": "same idea"},
                "similarity": 0.82,
                "type": "cross",
                "agreement_type": "paraphrase",
            }
        ],
    }

    create_visualizations_v2(results, output_service, "sample", "SEMANTIC_V2")

    # OutputService may redirect transcript_dir into OUTPUTS_DIR; read from there.
    metadata_path = output_service._artifact_metadata_path
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    emitted_viz_ids = {item["viz_id"] for item in metadata.values()}
    assert "semantic_similarity_v2.similarity_distribution.global" in emitted_viz_ids
    assert "semantic_similarity_v2.speaker_repetitions.global" in emitted_viz_ids
    assert all(item["module"] == "semantic_similarity_v2" for item in metadata.values())
