from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.analysis.group_charts import interactions_charts as ic
from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.domain.transcript_set import TranscriptSet


def test_parse_interactions_pooled_validates_schema_and_rows() -> None:
    assert ic._parse_interactions_pooled({}) is None
    assert (
        ic._parse_interactions_pooled({"interactions_pooled": {"schema_version": 2}})
        is None
    )
    parsed = ic._parse_interactions_pooled(
        {
            "interactions_pooled": {
                "schema_version": 1,
                "speakers": [
                    {"canonical_speaker_id": 1, "display_name": "Alice"},
                    {"canonical_speaker_id": "x"},
                ],
            }
        }
    )
    assert parsed is not None
    assert len(parsed) == 1


def test_any_positive_counts_and_top_speakers_sorting() -> None:
    speakers = [
        {
            "canonical_speaker_id": 2,
            "display_name": "Bob",
            "interruptions_initiated": 3,
        },
        {
            "canonical_speaker_id": 1,
            "display_name": "Alice",
            "interruptions_initiated": 3,
        },
        {
            "canonical_speaker_id": 3,
            "display_name": "Carol",
            "interruptions_initiated": 0,
        },
    ]
    assert ic._any_positive_counts(speakers)
    labels, vals = ic._top_speakers_by_metric(speakers, "interruptions_initiated")
    assert labels == ["Alice", "Bob"]
    assert vals == [3.0, 3.0]


def test_interactions_can_generate_from_session_or_pooled(monkeypatch) -> None:
    gen = ic.InteractionsGroupChartGenerator()

    class _SessionTrue:
        def can_generate(self, _outcome):
            return True

    class _SessionFalse:
        def can_generate(self, _outcome):
            return False

    monkeypatch.setattr(gen, "_session", _SessionTrue())
    assert gen.can_generate({}) is True

    monkeypatch.setattr(gen, "_session", _SessionFalse())
    assert (
        gen.can_generate(
            {
                "interactions_pooled": {
                    "schema_version": 1,
                    "speakers": [
                        {"canonical_speaker_id": 1, "interruptions_initiated": 2}
                    ],
                }
            }
        )
        is True
    )
    assert (
        gen.can_generate({"interactions_pooled": {"schema_version": 1, "speakers": []}})
        is False
    )


@pytest.mark.heavy
@pytest.mark.slow
def test_interactions_generate_emits_pooled_charts(monkeypatch, tmp_path: Path) -> None:
    gen = ic.InteractionsGroupChartGenerator()

    class _SessionNone:
        def generate(self, _ctx, _outcome):
            return None

    class _DummySvc:
        def __init__(self, **_kwargs):
            self._artifacts = []

        def save_chart(self, spec, chart_type="bar"):
            self._artifacts.append(
                {
                    "path": str(tmp_path / f"{spec.name}.png"),
                    "chart_type": chart_type,
                }
            )

    monkeypatch.setattr(gen, "_session", _SessionNone())
    monkeypatch.setattr(ic, "GroupChartOutputService", _DummySvc)
    monkeypatch.setattr(
        ic,
        "chart_artifact_paths",
        lambda svc: [Path(a["path"]) for a in svc._artifacts],
    )
    ctx = GroupChartContext(
        group_run_root=tmp_path,
        group_run_id="r1",
        agg_id="interactions",
        transcript_set=TranscriptSet.create(
            transcript_ids=["/tmp/a.json"],
            name="g",
            key="k",
        ),
        group_uuid="g1",
    )
    outcome = {
        "interactions_pooled": {
            "schema_version": 1,
            "speakers": [
                {
                    "canonical_speaker_id": 1,
                    "display_name": "Alice",
                    "interruptions_initiated": 4,
                    "interruptions_received": 1,
                },
                {
                    "canonical_speaker_id": 2,
                    "display_name": "Bob",
                    "interruptions_initiated": 2,
                    "interruptions_received": 3,
                },
            ],
        }
    }
    paths = gen.generate(ctx, outcome)
    assert paths is not None
    assert len(paths) >= 1
