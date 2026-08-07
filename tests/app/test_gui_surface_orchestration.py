"""Tests for gui surface orchestration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.app.controllers.batch_controller import BatchController
from transcriptx.app.controllers.settings_controller import SettingsController
from transcriptx.app.controllers.speaker_controller import SpeakerController
from transcriptx.app.models.errors import ValidationError, WorkflowExecutionError
from transcriptx.app.models.requests import (
    BatchAnalysisRequest,
    SpeakerIdentificationRequest,
)
from transcriptx.app.models.results import (
    AnalysisResult,
    BatchAnalysisResult,
    SpeakerIdentificationResult,
)
from transcriptx.app.module_resolution import get_module_info_list, resolve_modules
from transcriptx.app.output_capture import capture_output
from transcriptx.app.workflows.batch import run_batch_analysis
from transcriptx.app.workflows.speaker import identify_speakers


@pytest.mark.unit
def test_resolve_modules_rejects_invalid_custom_module_ids() -> None:
    with pytest.raises(ValueError, match="Invalid modules"):
        resolve_modules(["/tmp/t.json"], custom_ids=["not_real_module"])


@pytest.mark.unit
def test_resolve_modules_uses_defaults_then_mode_filter(monkeypatch) -> None:
    monkeypatch.setattr(
        "transcriptx.app.module_resolution.get_default_modules",
        lambda *_args, **_kwargs: ["stats", "sentiment"],
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.selection.filter_modules_by_mode",
        lambda selected, mode: (
            [m for m in selected if m == "stats"] if mode == "quick" else selected
        ),
    )
    selected = resolve_modules(["/tmp/t.json"], mode="quick")
    assert selected == ["stats"]


@pytest.mark.unit
def test_get_module_info_list_filters_missing_entries(monkeypatch) -> None:
    monkeypatch.setattr(
        "transcriptx.app.module_resolution.get_available_modules",
        lambda: ["stats", "missing"],
    )
    monkeypatch.setattr(
        "transcriptx.app.module_resolution.get_module_info",
        lambda module: {"module": module} if module == "stats" else None,
    )
    infos = get_module_info_list()
    assert infos == [{"module": "stats"}]


@pytest.mark.unit
def test_capture_output_collects_stdout_and_stderr() -> None:
    with capture_output() as (stdout_buf, stderr_buf):
        print("hello stdout")
        import sys

        print("hello stderr", file=sys.stderr)
    assert "hello stdout" in stdout_buf.getvalue()
    assert "hello stderr" in stderr_buf.getvalue()


@pytest.mark.unit
def test_settings_controller_effective_config_and_storage_roots(
    monkeypatch, tmp_path: Path
) -> None:
    fake_config = SimpleNamespace(to_dict=lambda: {"core_mode": True})
    monkeypatch.setattr(
        "transcriptx.app.controllers.settings_controller.get_config",
        lambda: fake_config,
    )
    monkeypatch.setattr(
        "transcriptx.app.controllers.settings_controller.PATHS",
        SimpleNamespace(
            recordings_dir=tmp_path / "recordings",
            transcripts_dir=tmp_path / "transcripts",
            outputs_dir=tmp_path / "outputs",
            config_dir=tmp_path / "config",
            state_dir=tmp_path / "state",
        ),
    )
    controller = SettingsController()
    assert controller.get_effective_config() == {"core_mode": True}
    roots = controller.get_storage_roots()
    assert roots["outputs_dir"] == tmp_path / "outputs"


@pytest.mark.unit
def test_batch_controller_validates_missing_transcript_path(tmp_path: Path) -> None:
    request = BatchAnalysisRequest(transcript_paths=[tmp_path / "missing.json"])
    with pytest.raises(ValidationError, match="Transcript not found"):
        BatchController().run_batch_analysis(request)


@pytest.mark.unit
def test_batch_controller_wraps_unexpected_errors(monkeypatch, tmp_path: Path) -> None:
    transcript = tmp_path / "ok.json"
    transcript.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.app.controllers.batch_controller.run_batch_analysis",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    request = BatchAnalysisRequest(transcript_paths=[transcript])
    with pytest.raises(WorkflowExecutionError, match="boom"):
        BatchController().run_batch_analysis(request)


@pytest.mark.unit
def test_speaker_controller_maps_validation_and_workflow_errors(
    monkeypatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "s.json"
    transcript.write_text("{}", encoding="utf-8")
    request = SpeakerIdentificationRequest(transcript_paths=[transcript])

    monkeypatch.setattr(
        "transcriptx.app.controllers.speaker_controller.identify_speakers",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError("no file")),
    )
    with pytest.raises(ValidationError, match="no file"):
        SpeakerController().identify_speakers(request)

    monkeypatch.setattr(
        "transcriptx.app.controllers.speaker_controller.identify_speakers",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("bad state")),
    )
    with pytest.raises(WorkflowExecutionError, match="bad state"):
        SpeakerController().identify_speakers(request)


@pytest.mark.unit
def test_run_batch_analysis_reports_folder_error(tmp_path: Path) -> None:
    result = run_batch_analysis(BatchAnalysisRequest(folder=tmp_path / "missing"))
    assert result.success is False
    assert result.transcript_count == 0
    assert result.errors


@pytest.mark.unit
def test_run_batch_analysis_aggregates_successes_and_errors(
    monkeypatch, tmp_path: Path
) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    request = BatchAnalysisRequest(transcript_paths=[first, second])

    def _fake_run_analysis(req, _progress):
        if req.transcript_path == first:
            return AnalysisResult(
                success=True,
                run_dir=tmp_path / "run-a",
                manifest_path=tmp_path / "run-a" / ".transcriptx" / "manifest.json",
                modules_executed=["stats"],
                warnings=[],
                errors=[],
            )
        return AnalysisResult(
            success=False,
            run_dir=tmp_path / "run-b",
            manifest_path=tmp_path / "run-b" / ".transcriptx" / "manifest.json",
            modules_executed=[],
            warnings=[],
            errors=["pipeline failed"],
            status="failed",
        )

    monkeypatch.setattr(
        "transcriptx.app.workflows.batch.run_analysis", _fake_run_analysis
    )
    result = run_batch_analysis(request)
    assert result.success is False
    assert result.transcript_count == 2
    assert any("b.json: pipeline failed" in e for e in result.errors)
    assert len(result.runs) == 1
    assert result.runs[0].run_dir == tmp_path / "run-a"
    assert result.runs[0].transcript_path == first


@pytest.mark.unit
def test_run_batch_analysis_emits_progress_without_fractional_pct(
    monkeypatch, tmp_path: Path
) -> None:
    """Batch stage progress must not pass 0–1 pct (collapses the live UI bar)."""
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    request = BatchAnalysisRequest(transcript_paths=[first, second])

    stage_progress: list[tuple[str, float | None]] = []
    logs: list[str] = []
    stage_starts: list[str] = []

    class _RecordingProgress:
        def on_stage_start(self, stage_name: str) -> None:
            stage_starts.append(stage_name)

        def on_stage_progress(self, message: str, pct: float | None = None) -> None:
            stage_progress.append((message, pct))

        def on_stage_complete(self, stage_name: str) -> None:
            return None

        def on_log(self, message: str, level: str = "info") -> None:
            logs.append(message)

        def on_event(self, event) -> None:
            return None

    def _fake_run_analysis(req, _progress):
        return AnalysisResult(
            success=True,
            run_dir=tmp_path / f"run-{req.transcript_path.stem}",
            manifest_path=tmp_path
            / f"run-{req.transcript_path.stem}"
            / ".transcriptx"
            / "manifest.json",
            modules_executed=["stats"],
            warnings=[],
            errors=[],
        )

    monkeypatch.setattr(
        "transcriptx.app.workflows.batch.run_analysis", _fake_run_analysis
    )
    result = run_batch_analysis(request, progress=_RecordingProgress())
    assert result.success is True
    assert stage_starts == ["batch_analysis", "batch_analysis"]
    assert len(stage_progress) == 2
    assert all(pct is None for _, pct in stage_progress)
    assert "Processing 1/2: a.json" in stage_progress[0][0]
    assert "Processing 2/2: b.json" in stage_progress[1][0]
    assert any("Analyzing a.json" in line for line in logs)
    assert any("Analyzing b.json" in line for line in logs)


@pytest.mark.unit
def test_identify_speakers_happy_path_with_rename(monkeypatch, tmp_path: Path) -> None:
    transcript = tmp_path / "speaker.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    renamed = tmp_path / "speaker_renamed.json"

    monkeypatch.setattr(
        "transcriptx.app.workflows.speaker.load_segments", lambda *_: []
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.speaker.build_speaker_map",
        lambda *_args, **_kwargs: {"SPEAKER_00": "Alice"},
    )
    renamed_calls: list[str] = []
    monkeypatch.setattr(
        "transcriptx.app.workflows.speaker.rename_transcript_after_speaker_mapping",
        lambda p: renamed_calls.append(p),
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.speaker.get_current_transcript_path_from_state",
        lambda _p: str(renamed),
    )

    result = identify_speakers(
        SpeakerIdentificationRequest(transcript_paths=[transcript], skip_rename=False)
    )
    assert result.success is True
    assert result.speakers_identified == 1
    assert result.updated_paths == [renamed]
    assert renamed_calls == [str(transcript)]


@pytest.mark.unit
def test_identify_speakers_handles_missing_files_and_workflow_exceptions(
    monkeypatch, tmp_path: Path
) -> None:
    missing = tmp_path / "missing.json"
    broken = tmp_path / "broken.json"
    broken.write_text("{}", encoding="utf-8")

    def _raise_for_broken(path: str):
        if path == str(broken):
            raise RuntimeError("speaker parsing failed")
        return []

    monkeypatch.setattr(
        "transcriptx.app.workflows.speaker.load_segments",
        _raise_for_broken,
    )

    result = identify_speakers(
        SpeakerIdentificationRequest(
            transcript_paths=[missing, broken], skip_rename=True
        )
    )
    assert result.success is False
    assert result.updated_paths == []
    assert any("Transcript file not found" in e for e in result.errors)
    assert any("speaker parsing failed" in e for e in result.errors)


@pytest.mark.unit
def test_batch_controller_happy_path_passes_result(monkeypatch) -> None:
    expected = BatchAnalysisResult(
        success=True, transcript_count=1, errors=[], message="ok"
    )
    monkeypatch.setattr(
        "transcriptx.app.controllers.batch_controller.run_batch_analysis",
        lambda *_args, **_kwargs: expected,
    )
    result = BatchController().run_batch_analysis(
        BatchAnalysisRequest(transcript_paths=[Path(__file__)])
    )
    assert result is expected


@pytest.mark.unit
def test_speaker_controller_happy_path_passes_result(
    monkeypatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "ok.json"
    transcript.write_text("{}", encoding="utf-8")
    expected = SpeakerIdentificationResult(
        success=True,
        updated_paths=[transcript],
        speakers_identified=2,
        errors=[],
    )
    monkeypatch.setattr(
        "transcriptx.app.controllers.speaker_controller.identify_speakers",
        lambda *_args, **_kwargs: expected,
    )
    result = SpeakerController().identify_speakers(
        SpeakerIdentificationRequest(transcript_paths=[transcript])
    )
    assert result is expected
