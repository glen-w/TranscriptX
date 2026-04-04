"""Tests for stats report payload and rendering."""

from __future__ import annotations

from pathlib import Path
import json

import pytest

from transcriptx.core.analysis.stats.stats_report import (  # type: ignore[import]
    build_stats_payload,
    render_stats_markdown,
    render_stats_txt,
)


class DummyContext:
    def __init__(self, base_name: str, transcript_dir: Path, results: dict) -> None:
        self._base_name = base_name
        self._dir = str(transcript_dir)
        self._results = results

    def get_analysis_result(self, module_id: str) -> object | None:
        return self._results.get(module_id)

    def get_base_name(self) -> str:
        return self._base_name

    def get_transcript_dir(self) -> str:
        return self._dir

    def get_run_id(self) -> str:
        return "run_123"

    def get_transcript_key(self) -> str:
        return "transcript_key_abc"


def _make_segments(missing_timestamps: bool = False) -> list[dict]:
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Hello world",
            "start": 0.0,
            "end": 3.0,
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "How are you today",
            "start": 3.0,
            "end": 6.0,
        },
    ]
    if missing_timestamps:
        segments.append(
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Missing time",
            }
        )
    return segments


def _make_stats_results() -> dict:
    return {
        "speaker_stats": [
            (120.0, "Alice", 600, 10, 0.02, 60.0),
            (60.0, "Bob", 300, 5, 0.01, 60.0),
        ],
        "sentiment_summary": {
            "Alice": {"compound": 0.1, "pos": 0.2, "neu": 0.7, "neg": 0.1},
            "Bob": {"compound": -0.1, "pos": 0.1, "neu": 0.8, "neg": 0.1},
        },
    }


def test_payload_keys_and_render_no_placeholders(tmp_path: Path) -> None:
    base_name = "sample"
    context = DummyContext(base_name, tmp_path, results={})

    payload = build_stats_payload(
        context,
        _make_segments(),
        _make_stats_results(),
        module_data={},
    )

    assert "meta" in payload
    assert "modules" in payload
    assert "overview" in payload
    assert "speakers" in payload
    assert "insights" in payload
    assert "warnings" in payload

    md = render_stats_markdown(payload)
    txt = render_stats_txt(payload)

    assert "No data available" not in md
    assert "No data available" not in txt
    assert 0 <= payload["speakers"][0]["pct_total_words"] <= 1


@pytest.mark.parametrize(
    "modules_run, modules_skipped, modules_failed, expected_status",
    [
        (["sentiment"], [], [], "succeeded"),
        ([], [], ["sentiment"], "failed"),
        ([], [{"module": "sentiment", "execution_status": "blocked"}], [], "blocked"),
        ([], [{"module": "sentiment", "execution_status": "skipped"}], [], "skipped"),
        ([], [], [], "enabled"),
    ],
)
def test_module_status_truth_table(
    tmp_path: Path,
    modules_run: list[str],
    modules_skipped: list[dict],
    modules_failed: list[str],
    expected_status: str,
) -> None:
    base_name = "sample"
    context = DummyContext(base_name, tmp_path, results={})
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "r1",
                "transcript_key": "t1",
                "modules_enabled": ["sentiment"],
                "modules_run": modules_run,
                "modules_skipped": modules_skipped,
                "modules_failed": modules_failed,
                "errors": [],
            }
        )
    )

    payload = build_stats_payload(
        context,
        _make_segments(),
        _make_stats_results(),
        module_data={},
    )

    assert payload["modules"]["sentiment"]["status"] == expected_status


def test_sentiment_missing_timestamps_fallback(tmp_path: Path) -> None:
    base_name = "sample"
    context = DummyContext(base_name, tmp_path, results={})

    payload = build_stats_payload(
        context,
        _make_segments(missing_timestamps=True),
        _make_stats_results(),
        module_data={},
    )

    sentiment = payload.get("sentiment", {})
    delta = sentiment.get("opening_vs_closing_delta", {})
    assert delta.get("method") == "by_count"
    assert any("Missing timestamps" in warning for warning in payload["warnings"])


def test_module_status_heuristic_marks_non_canonical_when_run_results_missing(
    tmp_path: Path,
) -> None:
    """When run_results is absent but artifacts exist, reason states heuristic / not canonical."""
    base_name = "sample"
    context = DummyContext(base_name, tmp_path, results={})
    # No run_results.json — create one expected sentiment artifact path
    sent_path = (
        tmp_path
        / "sentiment"
        / "data"
        / "global"
        / f"{base_name}_sentiment_summary.json"
    )
    sent_path.parent.mkdir(parents=True, exist_ok=True)
    sent_path.write_text("{}")

    payload = build_stats_payload(
        context,
        _make_segments(),
        _make_stats_results(),
        module_data={},
    )
    status = payload["modules"]["sentiment"]["status"]
    reason = payload["modules"]["sentiment"]["reason"]
    assert status == "unknown"
    assert "diagnostic" in reason.lower() or "unknown" in reason.lower()
    assert "run_results.json missing" in reason


def test_stats_payload_module_statuses_use_canonical_vocabulary(tmp_path: Path) -> None:
    base_name = "sample"
    context = DummyContext(base_name, tmp_path, results={})
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "r1",
                "transcript_key": "t1",
                "modules_enabled": ["sentiment"],
                "modules_run": [],
                "modules_skipped": [],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    payload = build_stats_payload(
        context,
        _make_segments(),
        _make_stats_results(),
        module_data={},
    )
    allowed = {
        "requested",
        "enabled",
        "blocked",
        "skipped",
        "failed",
        "succeeded",
        "unknown",
    }
    for mod in payload["modules"].values():
        assert mod["status"] in allowed
