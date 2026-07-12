"""Unit tests for dag_pipeline_factory create/run helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from transcriptx.core.pipeline.dag_pipeline_factory import (
    create_dag_pipeline,
    run_dag_pipeline,
)
from transcriptx.core.pipeline.run_options import SpeakerRunOptions


@pytest.mark.unit
def test_create_dag_pipeline_uses_registry_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_registry = object()
    fake_dag = MagicMock()

    monkeypatch.setattr(
        "transcriptx.core.pipeline.dag_pipeline_factory.build_dag_registry_from_module_registry",
        lambda: fake_registry,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.dag_pipeline_factory.DAGPipeline",
        lambda registry: fake_dag if registry is fake_registry else None,
    )
    assert create_dag_pipeline() is fake_dag


@pytest.mark.unit
def test_run_dag_pipeline_builds_context_executes_and_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    context = MagicMock()
    dag = MagicMock()
    dag.logger = MagicMock()
    dag.execute_pipeline.return_value = {"ok": True, "modules_run": ["stats"]}

    monkeypatch.setattr(
        "transcriptx.core.pipeline.dag_pipeline_factory.create_dag_pipeline",
        lambda: dag,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.dag_pipeline_factory.resolve_output_dir_for_run",
        lambda *_a, **_k: str(tmp_path / "out"),
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.dag_pipeline_factory.build_execute_pipeline_context",
        lambda *_a, **_k: (context, 3),
    )

    result = run_dag_pipeline(
        transcript_path=str(transcript),
        selected_modules=["stats"],
        speaker_options=SpeakerRunOptions(),
    )
    assert result == {"ok": True, "modules_run": ["stats"]}
    dag.execute_pipeline.assert_called_once()
    kw = dag.execute_pipeline.call_args.kwargs
    assert kw["context"] is context
    assert kw["named_speaker_count"] == 3
    assert kw["selected_modules"] == ["stats"]
    context.close.assert_called_once()


@pytest.mark.unit
def test_run_dag_pipeline_closes_even_when_execute_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    context = MagicMock()
    dag = MagicMock()
    dag.logger = MagicMock()
    dag.execute_pipeline.side_effect = RuntimeError("boom")

    monkeypatch.setattr(
        "transcriptx.core.pipeline.dag_pipeline_factory.create_dag_pipeline",
        lambda: dag,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.dag_pipeline_factory.resolve_output_dir_for_run",
        lambda *_a, **_k: str(tmp_path / "out"),
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.dag_pipeline_factory.build_execute_pipeline_context",
        lambda *_a, **_k: (context, 0),
    )

    with pytest.raises(RuntimeError, match="boom"):
        run_dag_pipeline(str(transcript), ["stats"])
    context.close.assert_called_once()


@pytest.mark.unit
def test_run_dag_pipeline_swallows_close_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    context = MagicMock()
    context.close.side_effect = OSError("close failed")
    dag = MagicMock()
    dag.logger = MagicMock()
    dag.execute_pipeline.return_value = {"ok": True}

    monkeypatch.setattr(
        "transcriptx.core.pipeline.dag_pipeline_factory.create_dag_pipeline",
        lambda: dag,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.dag_pipeline_factory.resolve_output_dir_for_run",
        lambda *_a, **_k: str(tmp_path / "out"),
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.dag_pipeline_factory.build_execute_pipeline_context",
        lambda *_a, **_k: (context, 1),
    )

    assert run_dag_pipeline(str(transcript), []) == {"ok": True}
    context.close.assert_called_once()
