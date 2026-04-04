"""Tests for cross-session overlay ordering and session caps."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from transcriptx.core.analysis.group_charts.overlay_series import (
    DEFAULT_MAX_GROUP_OVERLAY_SESSIONS,
    cap_per_transcript_results_for_overlay,
    sort_per_transcript_results_for_overlay,
)
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult


def _result(path: str, order_index: int) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path=path,
        transcript_key="k",
        run_id="run",
        order_index=order_index,
        output_dir="/tmp/out",
        module_results={},
    )


def test_sort_orders_by_order_index_then_stem() -> None:
    a = _result("/data/beta.wav", 0)
    b = _result("/data/alpha.wav", 0)
    c = _result("/data/zed.wav", 1)
    ordered = sort_per_transcript_results_for_overlay([c, a, b])
    assert [r.transcript_path for r in ordered] == [
        b.transcript_path,
        a.transcript_path,
        c.transcript_path,
    ]


def test_sort_non_int_order_index_sorts_last() -> None:
    bad = SimpleNamespace(
        transcript_path="/x/a.wav",
        transcript_key="k",
        run_id="r",
        order_index="nope",
        output_dir="/tmp",
        module_results={},
    )
    good = _result("/x/b.wav", 0)
    ordered = sort_per_transcript_results_for_overlay([bad, good])
    assert ordered[0] is good
    assert ordered[1] is bad


def test_cap_truncates_after_sort() -> None:
    rows = [
        _result(f"/t/{name}.wav", idx) for idx, name in [(1, "z"), (0, "m"), (0, "a")]
    ]
    capped = cap_per_transcript_results_for_overlay(rows, max_sessions=2)
    assert len(capped) == 2
    assert [Path(r.transcript_path).stem for r in capped] == ["a", "m"]


def test_cap_uses_default_max_sessions() -> None:
    rows = [
        _result(f"/s/{i}.wav", 0) for i in range(DEFAULT_MAX_GROUP_OVERLAY_SESSIONS + 3)
    ]
    capped = cap_per_transcript_results_for_overlay(rows)
    assert len(capped) == DEFAULT_MAX_GROUP_OVERLAY_SESSIONS
