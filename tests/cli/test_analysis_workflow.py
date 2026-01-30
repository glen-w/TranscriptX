"""Tests for analysis workflow control flow."""

from __future__ import annotations

from pathlib import Path
import contextlib

from transcriptx.cli import analysis_workflow
import transcriptx.core.utils.state_utils as state_utils


class _ConfirmStub:
    def __init__(self, value: bool) -> None:
        self._value = value

    def ask(self) -> bool:
        return self._value


def test_workflow_missing_transcript_exits(tmp_path: Path, monkeypatch, capsys) -> None:
    missing_path = tmp_path / "missing.json"
    analysis_workflow._run_analysis_workflow_impl(transcript_path=missing_path)
    output = capsys.readouterr().out
    assert "Transcript file not found" in output


def test_workflow_single_transcript_runs_pipeline(tmp_path: Path, monkeypatch) -> None:
    transcript_path = tmp_path / "sample.json"
    transcript_path.write_text('{"segments": []}')

    monkeypatch.setattr(
        analysis_workflow, "select_analysis_mode", lambda: "quick"
    )
    monkeypatch.setattr(
        analysis_workflow, "apply_analysis_mode_settings", lambda mode: None
    )
    monkeypatch.setattr(
        analysis_workflow, "select_analysis_modules", lambda: ["sentiment"]
    )
    monkeypatch.setattr(
        analysis_workflow, "filter_modules_by_mode", lambda modules, mode: modules
    )
    monkeypatch.setattr(
        analysis_workflow, "check_speaker_gate", lambda path: (analysis_workflow.SpeakerGateDecision.PROCEED, None)
    )
    monkeypatch.setattr(
        analysis_workflow, "questionary", type("Q", (), {"confirm": lambda *args, **kwargs: _ConfirmStub(True)})
    )

    called = {"value": False}

    def _run_pipeline(**kwargs):
        called["value"] = True
        return {"errors": []}

    monkeypatch.setattr(analysis_workflow, "run_analysis_pipeline", _run_pipeline)
    monkeypatch.setattr(
        state_utils,
        "get_analysis_history",
        lambda path: {
            "status": "completed",
            "modules_run": ["sentiment"],
            "modules_failed": [],
            "modules_requested": ["sentiment"],
        },
    )
    monkeypatch.setattr(
        analysis_workflow,
        "process_spinner",
        lambda *args, **kwargs: contextlib.nullcontext(
            type("T", (), {"current": 0, "update": lambda self, v: None})()
        ),
    )
    monkeypatch.setattr(
        analysis_workflow,
        "resource_monitor",
        lambda *args, **kwargs: contextlib.nullcontext(),
    )

    analysis_workflow._run_analysis_workflow_impl(transcript_path=transcript_path)
    assert called["value"] is True
