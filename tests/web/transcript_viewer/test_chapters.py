"""Unit tests for transcript viewer chapters (topic_shift spans panel)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.web.transcript_viewer.chapters import (
    CHAPTER_JUMP_KEY,
    CHAPTER_PENDING_KEY,
    apply_deferred_chapter_jump,
    clear_chapter_jump,
    format_chapter_time_range,
    load_chapter_rows,
    queue_chapter_jump,
    sticky_chapter_jump,
)


def _write_run_results(run_root: Path, *, modules_run: list[str] | None = None) -> None:
    payload = {
        "schema_version": 1,
        "run_id": "r1",
        "transcript_key": "sess",
        "modules_enabled": modules_run or ["topic_shift"],
        "modules_run": modules_run or ["topic_shift"],
        "modules_failed": [],
        "modules_skipped": [],
        "errors": [],
        "module_outcomes": [],
    }
    (run_root / "run_results.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_spans(run_root: Path, spans: list[dict]) -> Path:
    data = run_root / "topic_shift" / "data" / "global"
    data.mkdir(parents=True)
    path = data / "topic_shift.spans.json"
    path.write_text(
        json.dumps({"analytical_status": "success", "coverage_spans": spans}),
        encoding="utf-8",
    )
    return data


@pytest.mark.unit
def test_load_chapter_rows_none_and_absent(tmp_path: Path) -> None:
    assert load_chapter_rows(None) == []
    empty = tmp_path / "empty"
    empty.mkdir()
    assert load_chapter_rows(empty) == []


@pytest.mark.unit
def test_load_chapter_rows_corrupt_spans_returns_empty(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    data = run_root / "topic_shift" / "data" / "global"
    data.mkdir(parents=True)
    (data / "topic_shift.spans.json").write_text("{not-json", encoding="utf-8")
    _write_run_results(run_root)
    assert load_chapter_rows(run_root) == []


@pytest.mark.unit
def test_load_chapter_rows_skips_non_dict_spans(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    _write_spans(
        run_root,
        [
            "bad",
            {
                "span_id": "s1",
                "index": 0,
                "label": "Opening",
                "time_start": 0.0,
                "time_end": 5.0,
                "viewer_target_source_index": 1,
            },
        ],
    )
    _write_run_results(run_root)
    rows = load_chapter_rows(run_root)
    assert len(rows) == 1
    assert rows[0].span_id == "s1"


@pytest.mark.unit
def test_load_chapter_rows_strength_from_events(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    data = _write_spans(
        run_root,
        [
            {
                "span_id": "s1",
                "index": 0,
                "label": "Opening",
                "time_start": 0.0,
                "time_end": 10.0,
                "viewer_target_source_index": 2,
                "leading_boundary_id": "ev1",
            }
        ],
    )
    (data / "topic_shift.events.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": "ev1",
                        "evidence": [{"normalized_strength": 0.75}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _write_run_results(run_root)
    rows = load_chapter_rows(run_root)
    assert rows[0].strength == pytest.approx(0.75)
    assert rows[0].leading_boundary_id == "ev1"


@pytest.mark.unit
def test_load_chapter_rows_overall_summary_ui_mode(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    data = _write_spans(
        run_root,
        [
            {
                "span_id": "s1",
                "index": 0,
                "label": "Segment 1",
                "keyword_hints": ["agenda"],
                "time_start": 0.0,
                "time_end": 30.0,
                "viewer_target_source_index": 0,
            }
        ],
    )
    (data / "topic_shift.enrichment.json").write_text(
        json.dumps(
            {
                "ui_mode": "overall_summary",
                "outcome": "success",
                "overall_summary": "Meeting overview.",
                "entries": [
                    {
                        "span_id": "s1",
                        "title": "Should not win in overall mode",
                        "summary": "ignored",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _write_run_results(run_root)
    rows = load_chapter_rows(run_root)
    assert rows[0].title == "Agenda"
    assert rows[0].summary == "Meeting overview."


@pytest.mark.unit
def test_deterministic_label_fallback_without_hints(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    _write_spans(
        run_root,
        [
            {
                "span_id": "s1",
                "index": 3,
                "label": "",
                "time_start": 0.0,
                "time_end": 1.0,
                "viewer_target_source_index": 0,
            }
        ],
    )
    _write_run_results(run_root)
    rows = load_chapter_rows(run_root)
    assert rows[0].title == "Chapter 4"


@pytest.mark.unit
def test_sticky_and_clear_chapter_jump() -> None:
    state: dict = {}
    assert sticky_chapter_jump(state) is None
    state[CHAPTER_JUMP_KEY] = 9
    assert sticky_chapter_jump(state) == 9
    state[CHAPTER_JUMP_KEY] = "9"
    assert sticky_chapter_jump(state) is None
    clear_chapter_jump(state)
    assert state[CHAPTER_JUMP_KEY] is None


@pytest.mark.unit
def test_queue_chapter_jump_play_false_and_deferred_noop() -> None:
    state: dict = {"transcript_search": "keep"}
    queue_chapter_jump(state, source_index=4, play=False)
    assert state[CHAPTER_PENDING_KEY] == {"jump_index": 4, "play": False}
    assert state["transcript_viewer_force_segments_tab"] is True
    # No-op when force flag already consumed / absent.
    del state["transcript_viewer_force_segments_tab"]
    apply_deferred_chapter_jump(state)
    assert state["transcript_search"] == "keep"


@pytest.mark.unit
def test_format_chapter_time_range() -> None:
    text = format_chapter_time_range(0.0, 65.0)
    assert "–" in text
    assert text.startswith("0")
    assert "1" in text.split("–", 1)[1]
