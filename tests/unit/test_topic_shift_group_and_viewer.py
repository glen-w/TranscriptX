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
    state: dict = {}
    queue_chapter_jump(state, source_index=3, play=True)
    pending = consume_chapter_pending(state)
    assert pending == {"jump_index": 3, "play": True}
    assert consume_chapter_pending(state) is None
