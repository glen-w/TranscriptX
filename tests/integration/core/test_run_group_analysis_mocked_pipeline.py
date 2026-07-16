"""integration_core: run_group_analysis success path with mocked pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.app.models.requests import GroupAnalysisRequest
from transcriptx.app.progress import NullProgress
from transcriptx.app.workflows.analysis import run_group_analysis

pytestmark = [pytest.mark.integration_core, pytest.mark.unit]


@pytest.mark.integration_core
def test_run_group_analysis_success_with_mocked_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    transcript = tmp_path / "member.json"
    transcript.write_text(
        '{"segments": [{"speaker": "A", "text": "hi", "start": 0, "end": 1}]}',
        encoding="utf-8",
    )
    request = GroupAnalysisRequest(
        group_uuid="00000000-0000-0000-0000-000000000200",
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
        lambda **_kwargs: {
            # Non-existent path: avoid Path("") → cwd truth projection.
            "group_output_dir": str(tmp_path / "missing_group_output"),
            "errors": [],
            "modules_run": ["stats"],
            "status": "completed",
            "aggregation_warnings": [],
        },
    )

    result = run_group_analysis(request, progress=NullProgress(), snapshot=snapshot)

    assert result.success is True
    assert result.status == "completed"
    assert result.modules_executed == ["stats"]
    assert snapshot.get("status") == "completed"
    assert snapshot.get("phase") == "completed"
