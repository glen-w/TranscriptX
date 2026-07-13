"""Tests for app/workflows - prompt-free orchestration."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import transcriptx.core.services.group_service as group_service_module
import transcriptx.core.store.group_manifest_store as group_store_module
from transcriptx.app.models.requests import AnalysisRequest, GroupAnalysisRequest
from transcriptx.app.progress import NullProgress
from transcriptx.app.workflows.analysis import (
    _format_aggregation_warning_message,
    run_analysis,
    run_group_analysis,
    validate_analysis_readiness,
    validate_group_analysis_readiness,
)
from transcriptx.core.services.group_service import GroupService
from transcriptx.core.store.group_manifest_store import GroupManifestStore
from transcriptx.core.utils.config import TranscriptXConfig


def _configure_group_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "groups").mkdir()
    monkeypatch.setattr(group_store_module, "PROJECT_ROOT", project_root, raising=False)
    monkeypatch.setattr(
        group_store_module, "_GROUPS_DIR", project_root / "groups", raising=False
    )
    monkeypatch.setattr(
        group_service_module, "PROJECT_ROOT", project_root, raising=False
    )
    monkeypatch.setattr(
        group_service_module, "_STORE", GroupManifestStore(), raising=False
    )
    return project_root


def _write_transcript(project_root: Path, rel_path: str) -> Path:
    transcript_path = project_root / rel_path
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(json.dumps({"segments": []}), encoding="utf-8")
    return transcript_path


def _group_analysis_config_enabled() -> TranscriptXConfig:
    cfg = TranscriptXConfig()
    cfg.group_analysis.enabled = True
    return cfg


def test_validate_analysis_readiness_nonexistent():
    """Validation fails for non-existent transcript."""
    req = AnalysisRequest(transcript_path=Path("/nonexistent/path.json"))
    errors = validate_analysis_readiness(req)
    assert len(errors) > 0
    assert "not found" in errors[0].lower()


def test_validate_analysis_readiness_invalid_mode():
    """Validation fails for invalid mode."""
    req = AnalysisRequest(transcript_path=Path("."), mode="invalid")
    errors = validate_analysis_readiness(req)
    assert any("mode" in e.lower() for e in errors)


def test_run_analysis_nonexistent_returns_failed_result():
    """run_analysis returns failed result for non-existent path."""
    req = AnalysisRequest(transcript_path=Path("/nonexistent/path.json"))
    result = run_analysis(req, progress=NullProgress())
    assert not result.success
    assert result.status == "failed"
    assert len(result.errors) > 0


def test_validate_group_analysis_readiness_when_disabled():
    """Group analysis validation fails when group analysis is disabled in config."""
    req = GroupAnalysisRequest(group_uuid="test-uuid")
    errors = validate_group_analysis_readiness(req)
    assert len(errors) > 0
    assert "group" in errors[0].lower() or "enabled" in errors[0].lower()


def test_run_group_analysis_validation_failure_returns_failed_result():
    """run_group_analysis returns failed result when validation fails (e.g. group analysis disabled)."""
    req = GroupAnalysisRequest(group_uuid="test-uuid")
    result = run_group_analysis(req, progress=NullProgress())
    assert not result.success
    assert result.status == "failed"
    assert len(result.errors) > 0


def test_validate_group_analysis_readiness_unknown_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure_group_store(monkeypatch, tmp_path)
    req = GroupAnalysisRequest(group_uuid="00000000-0000-0000-0000-000000000001")
    with patch(
        "transcriptx.app.workflows.analysis.get_config",
        return_value=_group_analysis_config_enabled(),
    ):
        errors = validate_group_analysis_readiness(req)
    assert errors
    assert any("manifest" in e.lower() or "found" in e.lower() for e in errors)


def test_validate_group_analysis_readiness_passes_when_enabled_and_members_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure_group_store(monkeypatch, tmp_path)
    t1 = _write_transcript(project_root, "transcripts/g1.json")
    group = GroupService.create_or_get_group(
        name="Workflow Group",
        group_type="group",
        transcript_refs=[str(t1)],
    )
    req = GroupAnalysisRequest(group_uuid=group.group_id, mode="quick")
    with patch(
        "transcriptx.app.workflows.analysis.get_config",
        return_value=_group_analysis_config_enabled(),
    ):
        errors = validate_group_analysis_readiness(req)
    assert errors == []


def test_validate_group_analysis_readiness_fails_when_all_member_files_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure_group_store(monkeypatch, tmp_path)
    t1 = _write_transcript(project_root, "transcripts/missing-soon.json")
    group = GroupService.create_or_get_group(
        name="Gone",
        group_type="group",
        transcript_refs=[str(t1)],
    )
    t1.unlink()
    req = GroupAnalysisRequest(group_uuid=group.group_id)
    with patch(
        "transcriptx.app.workflows.analysis.get_config",
        return_value=_group_analysis_config_enabled(),
    ):
        errors = validate_group_analysis_readiness(req)
    assert errors
    assert any(
        "exist" in e.lower() or "disk" in e.lower() or "mount" in e.lower()
        for e in errors
    )


def test_validate_group_analysis_readiness_invalid_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure_group_store(monkeypatch, tmp_path)
    t1 = _write_transcript(project_root, "transcripts/mode.json")
    group = GroupService.create_or_get_group(
        name="M",
        group_type="group",
        transcript_refs=[str(t1)],
    )
    req = GroupAnalysisRequest(group_uuid=group.group_id, mode="turbo")
    with patch(
        "transcriptx.app.workflows.analysis.get_config",
        return_value=_group_analysis_config_enabled(),
    ):
        errors = validate_group_analysis_readiness(req)
    assert any("mode" in e.lower() for e in errors)


def test_validate_group_analysis_readiness_invalid_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure_group_store(monkeypatch, tmp_path)
    t1 = _write_transcript(project_root, "transcripts/prof.json")
    group = GroupService.create_or_get_group(
        name="P",
        group_type="group",
        transcript_refs=[str(t1)],
    )
    req = GroupAnalysisRequest(
        group_uuid=group.group_id, mode="quick", profile="not_a_profile"
    )
    with patch(
        "transcriptx.app.workflows.analysis.get_config",
        return_value=_group_analysis_config_enabled(),
    ):
        errors = validate_group_analysis_readiness(req)
    assert any("profile" in e.lower() for e in errors)


def test_validate_group_analysis_readiness_invalid_modules(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure_group_store(monkeypatch, tmp_path)
    t1 = _write_transcript(project_root, "transcripts/mod.json")
    group = GroupService.create_or_get_group(
        name="Mod",
        group_type="group",
        transcript_refs=[str(t1)],
    )
    req = GroupAnalysisRequest(
        group_uuid=group.group_id,
        mode="quick",
        modules=["__nonexistent_module_id_for_tests__"],
    )
    with patch(
        "transcriptx.app.workflows.analysis.get_config",
        return_value=_group_analysis_config_enabled(),
    ):
        errors = validate_group_analysis_readiness(req)
    assert any("invalid modules" in e.lower() for e in errors)


def test_format_aggregation_warning_message_dict_branch() -> None:
    msg = _format_aggregation_warning_message(
        {
            "code": "AGG_WARN",
            "message": "skipped row",
            "aggregation_key": "stats.session_rows",
        }
    )
    assert "AGG_WARN" in msg
    assert "stats.session_rows" in msg
    assert "skipped row" in msg


def test_format_aggregation_warning_message_non_dict() -> None:
    assert _format_aggregation_warning_message(42) == "42"


def test_run_analysis_invalid_explicit_modules_fails_without_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    req = AnalysisRequest(
        transcript_path=transcript, mode="quick", modules=["invalid_mod"]
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.get_available_modules",
        lambda: ["stats", "sentiment"],
    )
    result = run_analysis(req, progress=NullProgress())
    assert result.success is False
    assert result.status == "failed"
    assert any("Invalid modules" in e for e in result.errors)


def test_run_analysis_uses_default_modules_when_all_keyword(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    req = AnalysisRequest(transcript_path=transcript, mode="quick", modules=["all"])
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.get_available_modules",
        lambda: ["stats", "sentiment", "all"],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.get_default_modules",
        lambda *_args, **_kwargs: ["stats"],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.filter_modules_by_mode",
        lambda selected, _mode: selected,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.apply_analysis_mode_settings",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.run_analysis_pipeline",
        lambda **_kwargs: {
            "output_dir": str(tmp_path / "out"),
            "modules_run": ["stats"],
            "errors": [],
        },
    )
    result = run_analysis(req, progress=NullProgress())
    assert result.success is True
    assert result.modules_executed == ["stats"]


def test_run_analysis_restores_output_base_dir_after_custom_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    config = TranscriptXConfig()
    config.output.base_output_dir = str(tmp_path / "original")
    req = AnalysisRequest(
        transcript_path=transcript,
        mode="quick",
        modules=["stats"],
        output_dir=tmp_path / "custom",
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.get_available_modules",
        lambda: ["stats"],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.get_default_modules",
        lambda *_args, **_kwargs: ["stats"],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.filter_modules_by_mode",
        lambda selected, _mode: selected,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.apply_analysis_mode_settings",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr("transcriptx.app.workflows.analysis.get_config", lambda: config)
    seen_base_dirs: list[str] = []

    def _fake_run_analysis_pipeline(**_kwargs):
        seen_base_dirs.append(config.output.base_output_dir)
        return {
            "output_dir": str(tmp_path / "out"),
            "modules_run": ["stats"],
            "errors": [],
        }

    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.run_analysis_pipeline",
        _fake_run_analysis_pipeline,
    )

    result = run_analysis(req, progress=NullProgress())

    assert result.success is True
    assert seen_base_dirs == [str(tmp_path / "custom")]
    assert config.output.base_output_dir == str(tmp_path / "original")


def test_run_group_analysis_partial_missing_member_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    present = tmp_path / "present.json"
    present.write_text('{"segments": []}', encoding="utf-8")
    missing = tmp_path / "missing.json"
    request = GroupAnalysisRequest(
        group_uuid="00000000-0000-0000-0000-000000000111",
        mode="quick",
        modules=["stats"],
    )

    class _Present:
        file_path = str(present)

    class _Missing:
        file_path = str(missing)

    captured: dict = {}

    def _fake_resolve_modules(modules, resolved_paths, **_kwargs):
        captured["resolved_paths"] = list(resolved_paths)
        return (["stats"], None)

    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.validate_group_analysis_readiness",
        lambda _request: [],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.resolve_analysis_target",
        lambda _target: (object(), [_Present(), _Missing()]),
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis._resolve_modules",
        _fake_resolve_modules,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.filter_modules_by_mode",
        lambda selected, _mode: selected,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.apply_analysis_mode_settings",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.run_analysis_pipeline",
        lambda **_kwargs: {
            "group_output_dir": str(tmp_path / "group_out"),
            "errors": [],
            "modules_run": ["stats"],
            "status": "completed",
            "aggregation_warnings": [],
        },
    )

    result = run_group_analysis(request, progress=NullProgress())
    assert result.success is True
    assert captured["resolved_paths"] == [str(present)]
    assert any("member paths missing" in w for w in result.warnings)


def test_run_group_analysis_all_member_paths_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    request = GroupAnalysisRequest(
        group_uuid="00000000-0000-0000-0000-000000000112",
        mode="quick",
        modules=["stats"],
    )

    class _Missing:
        file_path = str(tmp_path / "gone.json")

    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.validate_group_analysis_readiness",
        lambda _request: [],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.resolve_analysis_target",
        lambda _target: (object(), [_Missing()]),
    )

    result = run_group_analysis(request, progress=NullProgress())
    assert result.success is False
    assert result.status == "failed"
    assert any("exist on disk" in e for e in result.errors)


def test_run_group_analysis_pipeline_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "member.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    request = GroupAnalysisRequest(
        group_uuid="00000000-0000-0000-0000-000000000113",
        mode="quick",
        modules=["stats"],
    )
    snapshot: dict = {}

    class _Member:
        file_path = str(transcript)

    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.validate_group_analysis_readiness",
        lambda _request: [],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.resolve_analysis_target",
        lambda _target: (object(), [_Member()]),
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.get_available_modules",
        lambda: ["stats"],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.get_default_modules",
        lambda *_args, **_kwargs: ["stats"],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.filter_modules_by_mode",
        lambda selected, _mode: selected,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.apply_analysis_mode_settings",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.run_analysis_pipeline",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("pipeline boom")),
    )

    result = run_group_analysis(request, progress=NullProgress(), snapshot=snapshot)
    assert result.success is False
    assert result.status == "failed"
    assert any("pipeline boom" in e for e in result.errors)
    assert snapshot.get("status") == "failed"


def test_run_group_analysis_merges_chart_failure_warnings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "member.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    request = GroupAnalysisRequest(
        group_uuid="00000000-0000-0000-0000-000000000123",
        mode="quick",
        modules=["stats"],
    )

    class _Member:
        file_path = str(transcript)

    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.validate_group_analysis_readiness",
        lambda _request: [],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.resolve_analysis_target",
        lambda _target: (object(), [_Member()]),
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.get_available_modules",
        lambda: ["stats"],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.get_default_modules",
        lambda *_args, **_kwargs: ["stats"],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.filter_modules_by_mode",
        lambda selected, _mode: selected,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.apply_analysis_mode_settings",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.run_analysis_pipeline",
        lambda **_kwargs: {
            "group_output_dir": str(tmp_path / "missing_group_output"),
            "errors": [],
            "modules_run": ["stats"],
            "status": "completed",
            "aggregation_warnings": [
                {
                    "code": "GROUP_CHART_FAILED",
                    "message": "chart failed",
                    "aggregation_key": "stats",
                }
            ],
        },
    )

    result = run_group_analysis(request, progress=NullProgress())
    assert result.success is True
    assert result.status == "completed"
    assert any("Group chart generation failed" in w for w in result.warnings)
    assert any("GROUP_CHART_FAILED" in w for w in result.warnings)


def test_run_group_analysis_uses_projected_group_truth_status_and_modules(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "member.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    group_output_dir = tmp_path / "group_run"
    group_output_dir.mkdir()
    request = GroupAnalysisRequest(
        group_uuid="00000000-0000-0000-0000-000000000321",
        mode="quick",
        modules=["stats", "sentiment"],
    )

    class _Member:
        file_path = str(transcript)

    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.validate_group_analysis_readiness",
        lambda _request: [],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.resolve_analysis_target",
        lambda _target: (object(), [_Member()]),
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.get_available_modules",
        lambda: ["stats", "sentiment"],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.filter_modules_by_mode",
        lambda selected, _mode: selected,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.apply_analysis_mode_settings",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.run_analysis_pipeline",
        lambda **_kwargs: {
            "group_output_dir": str(group_output_dir),
            "errors": [],
            "modules_run": ["stats", "sentiment"],
            "status": "completed",
        },
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.project_group_outcomes",
        lambda _path: SimpleNamespace(
            status="partial",
            group_outcomes=[
                SimpleNamespace(module_id="stats", status="succeeded"),
                SimpleNamespace(module_id="sentiment", status="failed"),
            ],
        ),
    )

    result = run_group_analysis(request, progress=NullProgress())
    assert result.status == "partial"
    assert result.modules_executed == ["stats"]


def test_run_group_analysis_truth_projection_error_falls_back_and_sets_partial(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "member.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    group_output_dir = tmp_path / "group_run"
    group_output_dir.mkdir()
    request = GroupAnalysisRequest(
        group_uuid="00000000-0000-0000-0000-000000000654",
        mode="quick",
        modules=["stats"],
    )

    class _Member:
        file_path = str(transcript)

    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.validate_group_analysis_readiness",
        lambda _request: [],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.resolve_analysis_target",
        lambda _target: (object(), [_Member()]),
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.get_available_modules",
        lambda: ["stats"],
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.filter_modules_by_mode",
        lambda selected, _mode: selected,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.apply_analysis_mode_settings",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.run_analysis_pipeline",
        lambda **_kwargs: {
            "group_output_dir": str(group_output_dir),
            "errors": ["aggregation failed"],
            "modules_run": [],
            "status": "completed",
        },
    )
    monkeypatch.setattr(
        "transcriptx.app.workflows.analysis.project_group_outcomes",
        lambda _path: (_ for _ in ()).throw(RuntimeError("truth projection failed")),
    )

    result = run_group_analysis(request, progress=NullProgress())
    assert result.status == "partial"
    assert result.modules_executed == ["stats"]
    assert result.errors == ["aggregation failed"]
