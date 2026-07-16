"""Unit tests for shared group chart path and session label helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from transcriptx.core.analysis.group_charts.helpers import (
    chart_artifact_paths,
    member_session_label,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult


def test_chart_artifact_paths_filters_suffixes_and_preserves_order() -> None:
    svc = SimpleNamespace(
        _artifacts=[
            {"path": "/a/ignore.txt"},
            {"path": "/a/one.png"},
            {},
            {"path": "/b/two.HTML"},
            {"path": "/c/three.html"},
        ]
    )
    out = chart_artifact_paths(svc)  # type: ignore[arg-type]
    assert out == [
        Path("/a/one.png"),
        Path("/b/two.HTML"),
        Path("/c/three.html"),
    ]


def test_member_session_label_uses_transcript_set_order() -> None:
    ts = TranscriptSet.create(["/sessions/a.wav", "/sessions/b.wav"])
    r = PerTranscriptResult(
        transcript_path="/sessions/b.wav",
        transcript_key="k",
        run_id="r",
        order_index=0,
        output_dir="/out",
        module_results={},
    )
    assert member_session_label(r, ts) == "S2 b"


def test_member_session_label_falls_back_to_order_index() -> None:
    ts = TranscriptSet.create(["/only/one.wav"])
    r = PerTranscriptResult(
        transcript_path="/not/in/set.wav",
        transcript_key="k",
        run_id="r",
        order_index=4,
        output_dir="/out",
        module_results={},
    )
    assert member_session_label(r, ts) == "S5 set"


def test_member_session_label_truncates_to_48_chars() -> None:
    long_stem = "x" * 60
    path = f"/p/{long_stem}.wav"
    ts = TranscriptSet.create([path])
    r = PerTranscriptResult(
        transcript_path=path,
        transcript_key="k",
        run_id="r",
        order_index=0,
        output_dir="/out",
        module_results={},
    )
    label = member_session_label(r, ts)
    assert len(label) == 48
    assert label.startswith("S1 ")


def test_make_group_output_service_has_no_outcome_param() -> None:
    import inspect

    from transcriptx.core.analysis.group_charts.helpers import make_group_output_service

    sig = inspect.signature(make_group_output_service)
    assert "outcome" not in sig.parameters
    assert "module_name" in sig.parameters
    assert "agg_id" in sig.parameters
