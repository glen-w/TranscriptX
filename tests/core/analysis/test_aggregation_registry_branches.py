"""Tests for aggregation registry branches."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.analysis.aggregation.registry import (
    AggregationEntry,
    _aggregate_moments,
    _aggregate_prosody,
    _aggregate_summary_blob,
    _artifact_relpath,
    _extract_highlight_items,
    _resolve_prosody_summary_path,
    _warning_payload_shape,
    build_registry,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _transcript_set(tmp_path: Path) -> TranscriptSet:
    return TranscriptSet.create(
        [str(tmp_path / "a.json")],
        name="G",
        key="gk",
    )


def _speaker_map() -> CanonicalSpeakerMap:
    return CanonicalSpeakerMap(
        transcript_to_speakers={},
        canonical_to_display={},
        transcript_to_display={},
    )


@pytest.mark.unit
def test_extract_highlight_items_collects_cold_open_and_conflict_anchor_quotes() -> (
    None
):
    payload = {
        "sections": {
            "cold_open": {"items": [{"text": "cold"}]},
            "conflict_points": {
                "events": [{"anchor_quote": {"text": "anchor"}}, {"anchor_quote": "x"}]
            },
        }
    }
    items = _extract_highlight_items(payload)
    assert items == [{"text": "cold"}, {"text": "anchor"}]


@pytest.mark.unit
def test_artifact_relpath_prefers_json_highlights_path() -> None:
    rel = _artifact_relpath(
        {
            "artifacts": [
                {"relative_path": "highlights/a.txt"},
                {"path": "highlights/highlights.json"},
            ]
        },
        "highlights",
    )
    assert rel == "highlights/highlights.json"


@pytest.mark.unit
def test_aggregate_moments_payload_shape_warning_when_moments_not_list(
    tmp_path: Path,
) -> None:
    result = PerTranscriptResult(
        transcript_path=str(tmp_path / "a.json"),
        transcript_key="a",
        run_id="r1",
        order_index=0,
        output_dir=str(tmp_path),
        module_results={"moments": {"payload": {"moments": "bad-shape"}}},
    )
    out = _aggregate_moments([result], _speaker_map(), _transcript_set(tmp_path))
    assert out is not None
    assert "warning" in out
    assert out["warning"]["aggregation_key"] == "moments"


@pytest.mark.unit
def test_aggregate_prosody_missing_artifact_returns_warning(tmp_path: Path) -> None:
    transcript_path = tmp_path / "a_transcriptx.json"
    transcript_path.write_text("{}", encoding="utf-8")
    result = PerTranscriptResult(
        transcript_path=str(transcript_path),
        transcript_key="a",
        run_id="r1",
        order_index=0,
        output_dir=str(tmp_path / "out"),
        module_results={},
    )
    out = _aggregate_prosody([result], _speaker_map(), _transcript_set(tmp_path))
    assert out is not None
    assert out["warning"]["code"] == "MISSING_ARTIFACT"
    assert out["warning"]["aggregation_key"] == "prosody"


# --- build_registry contract (module registry uniqueness/schema/selectors) ---


@pytest.mark.unit
def test_build_registry_returns_entries_with_unique_ids() -> None:
    registry = build_registry()
    assert registry
    assert all(isinstance(entry, AggregationEntry) for entry in registry)
    agg_ids = [entry.agg_id for entry in registry]
    assert len(agg_ids) == len(set(agg_ids)), "aggregation ids must be unique"


@pytest.mark.unit
def test_build_registry_deps_reference_known_aggregations() -> None:
    registry = build_registry()
    known = {entry.agg_id for entry in registry}
    for entry in registry:
        for dep in entry.deps:
            assert dep in known, f"{entry.agg_id} declares unknown dep {dep}"


@pytest.mark.unit
def test_build_registry_output_types_are_valid() -> None:
    registry = build_registry()
    for entry in registry:
        assert entry.output_type in {"rows", "blob"}


@pytest.mark.unit
def test_build_registry_selectors_match_their_own_module_id() -> None:
    registry = build_registry()
    by_id = {entry.agg_id: entry for entry in registry}
    # The 'stats' aggregation should select when 'stats' is among selected modules.
    stats = by_id["stats"]
    assert stats.selector(["stats"]) is True
    assert stats.selector(["sentiment"]) is False
    assert stats.selector([]) is False


@pytest.mark.unit
def test_entity_sentiment_depends_on_ner() -> None:
    registry = build_registry()
    by_id = {entry.agg_id: entry for entry in registry}
    assert "ner" in by_id["entity_sentiment"].deps


# --- pure helper coverage ---


@pytest.mark.unit
def test_resolve_prosody_summary_path_empty_output_dir_returns_none() -> None:
    assert _resolve_prosody_summary_path("", "voice_features", "base") is None


@pytest.mark.unit
def test_resolve_prosody_summary_path_missing_file_returns_none(tmp_path: Path) -> None:
    assert (
        _resolve_prosody_summary_path(str(tmp_path), "voice_features", "base") is None
    )


@pytest.mark.unit
def test_resolve_prosody_summary_path_existing_file(tmp_path: Path) -> None:
    summary = (
        tmp_path
        / "voice_features"
        / "data"
        / "global"
        / "base_voice_features_summary.json"
    )
    summary.parent.mkdir(parents=True)
    summary.write_text("{}", encoding="utf-8")
    resolved = _resolve_prosody_summary_path(str(tmp_path), "voice_features", "base")
    assert resolved == summary


@pytest.mark.unit
def test_aggregate_prosody_success_builds_session_rows(tmp_path: Path) -> None:
    base = "talk"
    output_dir = tmp_path / "out"
    summary = (
        output_dir
        / "voice_features"
        / "data"
        / "global"
        / f"{base}_voice_features_summary.json"
    )
    summary.parent.mkdir(parents=True)
    summary.write_text(
        json.dumps(
            {
                "voice_features.mean_pitch": 120.0,
                "prosody.energy": 0.5,
                "other_key": "kept-as-raw",
            }
        ),
        encoding="utf-8",
    )
    transcript_path = tmp_path / f"{base}.json"
    transcript_path.write_text("{}", encoding="utf-8")
    result = PerTranscriptResult(
        transcript_path=str(transcript_path),
        transcript_key=base,
        run_id="r1",
        order_index=0,
        output_dir=str(output_dir),
        module_results={},
    )
    out = _aggregate_prosody([result], _speaker_map(), _transcript_set(tmp_path))
    assert out is not None
    assert "warning" not in out
    rows = out["session_rows"]
    assert len(rows) == 1
    assert rows[0]["voice_features.mean_pitch"] == 120.0
    assert rows[0]["raw"] == {"other_key": "kept-as-raw"}


@pytest.mark.unit
def test_aggregate_summary_blob_none_when_no_payloads(tmp_path: Path) -> None:
    result = PerTranscriptResult(
        transcript_path=str(tmp_path / "a.json"),
        transcript_key="a",
        run_id="r1",
        order_index=0,
        output_dir=str(tmp_path),
        module_results={},
    )
    assert (
        _aggregate_summary_blob([result], _speaker_map(), _transcript_set(tmp_path))
        is None
    )


@pytest.mark.unit
def test_aggregate_summary_blob_collects_payloads(tmp_path: Path) -> None:
    result = PerTranscriptResult(
        transcript_path=str(tmp_path / "a.json"),
        transcript_key="a",
        run_id="r1",
        order_index=0,
        output_dir=str(tmp_path),
        module_results={"summary": {"payload": {"headline": "ok"}}},
    )
    out = _aggregate_summary_blob([result], _speaker_map(), _transcript_set(tmp_path))
    assert out is not None
    assert out["blob_name"] == "summary"
    assert out["blob_payload"]["aggregation_key"] == "summary"
    assert out["blob_payload"]["summaries"] == [{"headline": "ok"}]


@pytest.mark.unit
def test_warning_payload_shape_contract() -> None:
    out = _warning_payload_shape("prosody", ["a", "b"])
    assert out["warning"]["aggregation_key"] == "prosody"
    assert out["warning"]["code"] == "PAYLOAD_SHAPE_UNSUPPORTED"
