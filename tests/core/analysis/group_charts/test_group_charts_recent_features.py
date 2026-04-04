"""Unit tests for recently tightened group chart paths (tics pooled, highlights/moments, prosody overlay)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.helpers import member_session_label
from transcriptx.core.analysis.group_charts.highlights_moments import (
    HighlightsGroupChartGenerator,
    MomentsGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.tics_group_charts import (
    TicsGroupChartGenerator,
)
from transcriptx.core.analysis.voice.prosody_overlay_segments import (
    PROSODY_OVERLAY_Y_FIELD,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult

# --- Tics pooled (session bars + corpus by_tic) ---


def test_tics_can_generate_from_pooled_by_tic_only() -> None:
    gen = TicsGroupChartGenerator()
    assert gen.can_generate(
        {
            "session_rows": [],
            "speaker_rows": [],
            "tics_pooled": {"by_tic": {"um": 2, "like": 1}},
        }
    )


def test_tics_can_generate_from_pooled_total_only() -> None:
    gen = TicsGroupChartGenerator()
    assert gen.can_generate({"tics_pooled": {"total_tics": 4}})
    assert not gen.can_generate({"tics_pooled": {"total_tics": 0}})
    assert not gen.can_generate({"tics_pooled": {}})


def test_tics_can_generate_false_when_empty() -> None:
    gen = TicsGroupChartGenerator()
    assert not gen.can_generate({"session_rows": [], "speaker_rows": []})


def test_tics_generate_pooled_bar_writes_chart(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    gen = TicsGroupChartGenerator()
    root = tmp_path / "group_run"
    root.mkdir(parents=True)
    ts = TranscriptSet.create(transcript_ids=["/x/a.json"], name="G", key="k")
    ctx = GroupChartContext(
        group_run_root=root,
        group_run_id="run1",
        agg_id="tics",
        transcript_set=ts,
        group_uuid="gu1",
    )
    outcome = {
        "session_rows": [],
        "speaker_rows": [],
        "tics_pooled": {"by_tic": {"uh": 1, "um": 3}},
    }
    paths = gen.generate(ctx, outcome)
    assert paths
    assert any(p.suffix.lower() in {".png", ".html"} for p in paths)


# --- Highlights / moments (content_rows aggregates) ---


def test_highlights_can_generate_requires_content_rows() -> None:
    gen = HighlightsGroupChartGenerator()
    assert not gen.can_generate({"content_rows": []})
    assert gen.can_generate({"content_rows": [{"order_index": 0, "kind": "x"}]})


def test_moments_can_generate_requires_content_rows() -> None:
    gen = MomentsGroupChartGenerator()
    assert not gen.can_generate({})
    assert gen.can_generate({"content_rows": [{"order_index": 1}]})


def test_highlights_generate_session_counts_without_scores(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    gen = HighlightsGroupChartGenerator()
    root = tmp_path / "gr"
    root.mkdir()
    ts = TranscriptSet.create(transcript_ids=["/t/a.json"], name="G", key="k")
    ctx = GroupChartContext(
        group_run_root=root,
        group_run_id="r1",
        agg_id="highlights",
        transcript_set=ts,
    )
    outcome = {
        "content_rows": [
            {"order_index": 0},
            {"order_index": 0},
            {"order_index": 1},
        ],
        "session_rows": [
            {"order_index": 0, "session_label": "Alpha"},
            {"order_index": 1, "session_label": "Beta"},
        ],
    }
    paths = gen.generate(ctx, outcome)
    assert paths


def test_highlights_generate_adds_mean_score_chart_when_numeric_scores(
    tmp_path: Path,
) -> None:
    pytest.importorskip("matplotlib")
    gen = HighlightsGroupChartGenerator()
    root = tmp_path / "gr"
    root.mkdir()
    ts = TranscriptSet.create(transcript_ids=["/t/a.json"], name="G", key="k")
    ctx = GroupChartContext(
        group_run_root=root,
        group_run_id="r1",
        agg_id="highlights",
        transcript_set=ts,
    )
    outcome = {
        "content_rows": [
            {"order_index": 0, "score": 2.0},
            {"order_index": 0, "score": 4.0},
        ],
        "session_rows": [{"order_index": 0, "session_label": "S1"}],
    }
    paths = gen.generate(ctx, outcome)
    assert paths
    assert len(paths) >= 2


def test_moments_generate_mean_score_chart(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    gen = MomentsGroupChartGenerator()
    root = tmp_path / "gr"
    root.mkdir()
    ts = TranscriptSet.create(transcript_ids=["/t/a.json"], name="G", key="k")
    ctx = GroupChartContext(
        group_run_root=root,
        group_run_id="r1",
        agg_id="moments",
        transcript_set=ts,
    )
    outcome = {
        "content_rows": [{"order_index": 0, "score": 10.0}],
        "session_rows": [{"order_index": 0}],
    }
    paths = gen.generate(ctx, outcome)
    assert paths


# --- Prosody overlay helpers (prefix filter + segment JSON contract) ---


def test_prosody_allowed_key_prefixes() -> None:
    from transcriptx.core.analysis.group_charts import prosody_charts as pc

    assert pc._allowed_prosody_key("prosody.mean_rms_db")
    assert pc._allowed_prosody_key("voice_features.energy_mean")
    assert pc._allowed_prosody_key("voice_charts_core.foo")
    assert not pc._allowed_prosody_key("stats.total_words")
    assert not pc._allowed_prosody_key("raw")


def test_prosody_chart_keys_keep_only_allowed_prefixes() -> None:
    from transcriptx.core.analysis.group_charts import prosody_charts as pc

    rows = [
        {
            "order_index": 0,
            "prosody.x": 1.0,
            "stats.words": 99,
            "noise": 3,
        }
    ]
    keys = pc._prosody_chart_keys(rows)
    assert "prosody.x" in keys
    assert "stats.words" not in keys


def test_load_member_prosody_segments_requires_matching_y_field(
    tmp_path: Path,
) -> None:
    from transcriptx.core.analysis.group_charts import prosody_charts as pc

    transcript_path = str(tmp_path / "meet_transcript.json")
    out_dir = tmp_path / "run_out"
    global_dir = out_dir / "prosody_dashboard" / "data" / "global"
    global_dir.mkdir(parents=True)
    artifact = global_dir / "meet_prosody_overlay_segments.v1.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "y_field": "wrong_field",
                "segments": [{"start": 0.0, PROSODY_OVERLAY_Y_FIELD: -20.0}],
            }
        ),
        encoding="utf-8",
    )
    result = PerTranscriptResult(
        transcript_path=transcript_path,
        transcript_key="k",
        run_id="r",
        order_index=0,
        output_dir=str(out_dir),
        module_results={},
    )
    assert pc._load_member_prosody_segments(result) == []


def test_load_member_prosody_segments_parses_valid_payload(tmp_path: Path) -> None:
    from transcriptx.core.analysis.group_charts import prosody_charts as pc

    transcript_path = str(tmp_path / "meet_transcript.json")
    out_dir = tmp_path / "run_out"
    global_dir = out_dir / "prosody_dashboard" / "data" / "global"
    global_dir.mkdir(parents=True)
    artifact = global_dir / "meet_prosody_overlay_segments.v1.json"
    segs = [
        {"start": 0.0, PROSODY_OVERLAY_Y_FIELD: -10.0},
        {"start": 1.0, PROSODY_OVERLAY_Y_FIELD: -12.0},
    ]
    artifact.write_text(
        json.dumps(
            {"schema_version": 1, "y_field": PROSODY_OVERLAY_Y_FIELD, "segments": segs}
        ),
        encoding="utf-8",
    )
    result = PerTranscriptResult(
        transcript_path=transcript_path,
        transcript_key="k",
        run_id="r",
        order_index=0,
        output_dir=str(out_dir),
        module_results={},
    )
    loaded = pc._load_member_prosody_segments(result)
    assert len(loaded) == 2


# --- Pauses / prosody: shared overlay session label semantics ---


def test_pauses_session_label_matches_transcript_set_order(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text("[]", encoding="utf-8")
    second.write_text("[]", encoding="utf-8")
    ts = TranscriptSet.create(
        transcript_ids=[str(second), str(first)], name="G", key="k"
    )
    result = PerTranscriptResult(
        transcript_path=str(first),
        transcript_key="k",
        run_id="r",
        order_index=0,
        output_dir=str(tmp_path / "o"),
        module_results={},
    )
    label = member_session_label(result, ts)
    assert label.startswith("S2 ")


def test_pauses_session_label_falls_back_to_order_index(tmp_path: Path) -> None:
    ts = TranscriptSet.create(transcript_ids=["/only/x.json"], name="G", key="k")
    result = PerTranscriptResult(
        transcript_path="/other/y.json",
        transcript_key="k",
        run_id="r",
        order_index=4,
        output_dir=str(tmp_path / "o"),
        module_results={},
    )
    label = member_session_label(result, ts)
    assert label.startswith("S5 ")
