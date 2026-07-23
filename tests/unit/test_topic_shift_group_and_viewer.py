"""Aggregation + chapters loader smoke for topic_shift."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.analysis.topic_shift.aggregation import aggregate_topic_shift
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.web.transcript_viewer.chapters import (
    consume_chapter_pending,
    load_chapter_rows,
    queue_chapter_jump,
)


def test_aggregate_topic_shift_cohorts(tmp_path: Path) -> None:
    key = "tfidf|None|topic_shift_semantics_v1"
    path_a = str(tmp_path / "a.json")
    path_b = str(tmp_path / "b.json")
    results = [
        PerTranscriptResult(
            transcript_path=path_a,
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir=str(tmp_path / "a"),
            module_results={
                "topic_shift": {
                    "stats": {
                        "analytical_status": "success",
                        "n_shifts": 2,
                        "valid_duration_seconds": 3600,
                        "shifts_per_hour": 2.0,
                        "median_span_duration": 10.0,
                        "longest_span_duration": 20.0,
                        "backend": "tfidf",
                        "model_name": None,
                        "semantics_version": "topic_shift_semantics_v1",
                        "provenance_compatibility_key": key,
                    }
                }
            },
        ),
        PerTranscriptResult(
            transcript_path=path_b,
            transcript_key="b",
            run_id="r1",
            order_index=1,
            output_dir=str(tmp_path / "b"),
            module_results={
                "topic_shift": {
                    "stats": {
                        "analytical_status": "no_shift_detected",
                        "n_shifts": 0,
                        "valid_duration_seconds": 3600,
                        "shifts_per_hour": 0.0,
                        "median_span_duration": 3600.0,
                        "longest_span_duration": 3600.0,
                        "backend": "tfidf",
                        "model_name": None,
                        "semantics_version": "topic_shift_semantics_v1",
                        "provenance_compatibility_key": key,
                    }
                }
            },
        ),
    ]
    tset = TranscriptSet.create(
        ["a", "b"],
        metadata={
            "transcript_id_map": {path_a: "a", path_b: "b"},
            "transcript_key_map": {"a": "a", "b": "b"},
        },
    )
    out = aggregate_topic_shift(results, {}, tset)
    assert out is not None
    rows = out["session_rows"]
    assert len(rows) == 2
    assert all(r["included_in_comparison"] for r in rows)
    pooled = out["topic_shift_pooled"]
    assert pooled["comparable_key"] == key
    assert pooled.get("incompatible_member_count", 0) == 0


def test_load_chapters_and_pending_jump(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    data = run_root / "topic_shift" / "data" / "global"
    data.mkdir(parents=True)
    spans = {
        "analytical_status": "success",
        "coverage_spans": [
            {
                "span_id": "s1",
                "index": 0,
                "label": "Opening",
                "time_start": 0.0,
                "time_end": 12.0,
                "viewer_target_source_index": 3,
                "leading_boundary_id": None,
            }
        ],
    }
    (data / "topic_shift.spans.json").write_text(json.dumps(spans), encoding="utf-8")
    rr = {
        "schema_version": 2,
        "run_id": "r1",
        "transcript_key": "sess",
        "modules_enabled": ["topic_shift"],
        "modules_run": ["topic_shift"],
        "modules_failed": [],
        "modules_skipped": [],
        "errors": [],
        "module_outcomes": [],
    }
    (run_root / "run_results.json").write_text(json.dumps(rr), encoding="utf-8")
    rows = load_chapter_rows(run_root)
    assert len(rows) == 1
    assert rows[0].title == "Opening"
    assert rows[0].viewer_target_source_index == 3
    state: dict = {"transcript_search": "stale"}
    queue_chapter_jump(state, source_index=3, play=True)
    assert state["transcript_viewer_chapter_jump"] == 3
    assert state["transcript_viewer_tab"] == "segments"
    assert state["transcript_viewer_tab_control"] == "Segments"
    assert state["transcript_search"] == ""
    pending = consume_chapter_pending(state)
    assert pending == {"jump_index": 3, "play": True}
    assert consume_chapter_pending(state) is None


def test_chapter_titles_prefer_hints_and_rewrite_segment_label(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    data = run_root / "topic_shift" / "data" / "global"
    data.mkdir(parents=True)
    spans = {
        "analytical_status": "success",
        "coverage_spans": [
            {
                "span_id": "s1",
                "index": 0,
                "label": "Segment 1 · 00:00–01:00",
                "keyword_hints": ["budget", "finance", "planning"],
                "time_start": 0.0,
                "time_end": 60.0,
                "viewer_target_source_index": 0,
            },
            {
                "span_id": "s2",
                "index": 1,
                "label": "Segment 2 · 01:00–02:00",
                "keyword_hints": [],
                "time_start": 60.0,
                "time_end": 120.0,
                "viewer_target_source_index": 5,
            },
        ],
    }
    (data / "topic_shift.spans.json").write_text(json.dumps(spans), encoding="utf-8")
    (run_root / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "r1",
                "transcript_key": "sess",
                "modules_enabled": ["topic_shift"],
                "modules_run": ["topic_shift"],
                "modules_failed": [],
                "modules_skipped": [],
                "errors": [],
                "module_outcomes": [],
            }
        ),
        encoding="utf-8",
    )
    rows = load_chapter_rows(run_root)
    assert rows[0].title == "Budget · Finance · Planning"
    assert rows[1].title == "Chapter 2 · 01:00–02:00"


def test_chapter_titles_prefer_llm_enrichment(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    data = run_root / "topic_shift" / "data" / "global"
    data.mkdir(parents=True)
    spans = {
        "analytical_status": "success",
        "coverage_spans": [
            {
                "span_id": "s1",
                "index": 0,
                "label": "Segment 1 · 00:00–01:00",
                "keyword_hints": ["budget"],
                "time_start": 0.0,
                "time_end": 60.0,
                "viewer_target_source_index": 0,
            }
        ],
    }
    (data / "topic_shift.spans.json").write_text(json.dumps(spans), encoding="utf-8")
    enrich = {
        "ui_mode": "chapter_titles",
        "outcome": "success",
        "entries": [
            {
                "span_id": "s1",
                "title": "Q3 budget review",
                "summary": "Discussed forecast.",
            }
        ],
    }
    (data / "topic_shift.enrichment.json").write_text(
        json.dumps(enrich), encoding="utf-8"
    )
    (run_root / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "r1",
                "transcript_key": "sess",
                "modules_enabled": ["topic_shift"],
                "modules_run": ["topic_shift"],
                "modules_failed": [],
                "modules_skipped": [],
                "errors": [],
                "module_outcomes": [],
            }
        ),
        encoding="utf-8",
    )
    rows = load_chapter_rows(run_root)
    assert rows[0].title == "Q3 budget review"
    assert rows[0].summary == "Discussed forecast."


def test_moments_point_event_seeds_segment_refs() -> None:
    from transcriptx.core.analysis.dynamics.moments import MomentsAnalysis
    from transcriptx.core.models.events import Event

    analysis = MomentsAnalysis(
        {
            "merge_seconds": 0.0,
            "top_n": 5,
            "max_span_seconds": 120.0,
            "weight_map": {"topic_shift": 1.0},
            "diversity_bonus": 0.0,
            "multi_speaker_bonus": 0.0,
        }
    )
    segments = [
        {"start": 0.0, "end": 1.0, "text": "hello there friend", "speaker": "A"},
        {"start": 1.0, "end": 2.0, "text": "second utterance here", "speaker": "B"},
        {"start": 2.0, "end": 3.0, "text": "third utterance here", "speaker": "A"},
    ]
    event = Event(
        event_id="e1",
        kind="topic_shift",
        time_start=1.5,
        time_end=1.5,
        speaker=None,
        segment_start_idx=1,
        segment_end_idx=1,
        severity=0.8,
        score=0.8,
        evidence=[],
        links=[],
    )
    out = analysis.analyze(
        segments,
        topic_shift_data={"events": [event]},
        transcript_hash="testhash",
    )
    moments = out["moments"]
    assert len(moments) == 1
    assert 1 in moments[0]["segment_refs"]
    assert float(moments[0]["time_end"]) > float(moments[0]["time_start"])


def test_nearest_renderable_source_index_snaps() -> None:
    from transcriptx.core.analysis.topic_shift.spans import nearest_renderable_source_index

    assert nearest_renderable_source_index(5, renderable=[0, 2, 8, 10]) == 8
    assert nearest_renderable_source_index(2, renderable=[0, 2, 8]) == 2
    assert nearest_renderable_source_index(1, renderable=[]) is None
