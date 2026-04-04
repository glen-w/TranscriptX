from __future__ import annotations

import pandas as pd
import pytest

from transcriptx.core.analysis.topic_modeling.visualization import (
    _parse_speaker_names,
    create_speaker_topic_engagement_heatmap,
)
from transcriptx.core.viz.specs import HeatmapMatrixSpec


class _DummyOutputService:
    def __init__(self) -> None:
        self.specs: list[HeatmapMatrixSpec] = []

    def save_chart(self, spec, chart_type=None):
        self.specs.append(spec)
        return {"static": "/tmp/fake.png", "chart_type": chart_type}


def test_parse_speaker_names_deduplicates_with_whitespace() -> None:
    assert _parse_speaker_names(" Ana / Fede / Ana /  ") == ["Ana", "Fede"]


def test_speaker_topic_heatmap_expands_multi_speaker_rows_with_conservation() -> None:
    docs = [
        {"speaker": "Ana", "dominant_topic": 0},
        {"speaker": "Ana / Fede", "dominant_topic": 0},
        {"speaker": "Ana / Fede / Filka", "dominant_topic": 1},
        {"speaker": "Ana / Fede / Ana", "dominant_topic": 1},
    ]
    output_service = _DummyOutputService()

    create_speaker_topic_engagement_heatmap(
        docs,
        base_name="fixture",
        output_structure={},
        lda_topics=[],
        output_service=output_service,
    )

    assert len(output_service.specs) == 1
    spec = output_service.specs[0]
    assert spec.y_labels == ["Ana", "Fede", "Filka"]
    assert spec.x_labels == ["T0", "T1"]

    matrix = spec.z
    assert pytest.approx(sum(sum(row) for row in matrix), abs=1e-9) == len(docs)

    row_by_speaker = {speaker: matrix[idx] for idx, speaker in enumerate(spec.y_labels)}
    assert row_by_speaker["Ana"] == pytest.approx([1.5, 5.0 / 6.0], abs=1e-9)
    assert row_by_speaker["Fede"] == pytest.approx([0.5, 5.0 / 6.0], abs=1e-9)
    assert row_by_speaker["Filka"] == pytest.approx([0.0, 1.0 / 3.0], abs=1e-9)


def test_speaker_topic_heatmap_single_speaker_matches_legacy_counting() -> None:
    docs = [
        {"speaker": "Ana", "dominant_topic": 0},
        {"speaker": "Fede", "dominant_topic": 1},
        {"speaker": "Ana", "dominant_topic": 1},
        {"speaker": "Filka", "dominant_topic": 1},
    ]
    output_service = _DummyOutputService()

    create_speaker_topic_engagement_heatmap(
        docs,
        base_name="fixture",
        output_structure={},
        lda_topics=[],
        output_service=output_service,
    )

    assert len(output_service.specs) == 1
    spec = output_service.specs[0]

    legacy = (
        pd.crosstab(
            pd.Series([d["speaker"] for d in docs]),
            pd.Series([d["dominant_topic"] for d in docs]),
        )
        .sort_index(axis=0)
        .sort_index(axis=1)
    )

    assert spec.y_labels == legacy.index.tolist()
    assert spec.x_labels == [f"T{int(topic)}" for topic in legacy.columns.tolist()]
    assert spec.z == legacy.values.tolist()
