"""Tests for dag pipeline run helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import transcriptx.core.pipeline.dag_pipeline_run as run_helpers


def test_gating_named_speaker_count_prefers_larger_context_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(run_helpers, "named_speaker_count_for_path", lambda _p: 2)
    context = SimpleNamespace(runtime_flags={"named_speaker_keys": {"A", "B", "C"}})
    assert run_helpers.gating_named_speaker_count("/tmp/t.json", context) == 3


def test_gating_named_speaker_count_returns_none_when_lookup_fails_without_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        run_helpers,
        "named_speaker_count_for_path",
        lambda _p: (_ for _ in ()).throw(RuntimeError("no sidecar")),
    )
    assert run_helpers.gating_named_speaker_count("/tmp/t.json", None) is None


def test_resolve_output_dir_for_run_uses_path_core_when_missing_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils._path_core.get_transcript_dir",
        lambda _p: "/tmp/from-core",
    )
    assert (
        run_helpers.resolve_output_dir_for_run("/tmp/t.json", None) == "/tmp/from-core"
    )


def test_resolve_output_dir_for_run_keeps_explicit_override() -> None:
    assert (
        run_helpers.resolve_output_dir_for_run("/tmp/t.json", "/tmp/explicit")
        == "/tmp/explicit"
    )


def test_build_execute_pipeline_context_returns_context_and_gating_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ctx = SimpleNamespace(
        validate=lambda: True,
        get_segments=lambda: [{"speaker": "A"}],
        runtime_flags={"named_speaker_keys": {"A"}},
    )
    monkeypatch.setattr(run_helpers, "PipelineContext", lambda *_a, **_k: fake_ctx)
    monkeypatch.setattr(run_helpers, "gating_named_speaker_count", lambda *_a, **_k: 1)
    debug_calls: list[str] = []
    logger = SimpleNamespace(debug=lambda msg: debug_calls.append(msg))

    context, count = run_helpers.build_execute_pipeline_context(
        logger,
        transcript_path="/tmp/t.json",
        speaker_options=SimpleNamespace(include_unidentified=False, anonymise=False),
        output_dir="/tmp/out",
        transcript_key="tk",
        run_id="rid",
    )

    assert context is fake_ctx
    assert count == 1
    assert debug_calls and "Created PipelineContext" in debug_calls[0]


def test_build_execute_pipeline_context_closes_context_and_raises_on_failed_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = {"value": False}
    fake_ctx = SimpleNamespace(
        validate=lambda: False,
        close=lambda: closed.__setitem__("value", True),
        get_segments=lambda: [],
        runtime_flags={},
    )
    monkeypatch.setattr(run_helpers, "PipelineContext", lambda *_a, **_k: fake_ctx)
    logger = SimpleNamespace(debug=lambda _msg: None)

    with pytest.raises(ValueError, match="PipelineContext validation failed"):
        run_helpers.build_execute_pipeline_context(
            logger,
            transcript_path="/tmp/t.json",
            speaker_options=SimpleNamespace(
                include_unidentified=False, anonymise=False
            ),
            output_dir="/tmp/out",
            transcript_key="tk",
            run_id="rid",
        )
    assert closed["value"] is True
