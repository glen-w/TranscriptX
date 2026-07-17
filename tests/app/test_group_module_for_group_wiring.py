"""Group analysis readiness accepts modules with supports_group=true."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.app.models.requests import GroupAnalysisRequest
from transcriptx.app.workflows.analysis import (
    _resolve_modules,
    validate_group_analysis_readiness,
)


@pytest.mark.unit
def test_resolve_modules_accepts_formerly_unsupported_for_group() -> None:
    selected, error = _resolve_modules(
        ["stats", "voice_contours", "transcript_output"],
        ["/tmp/a.json"],
        for_group=True,
    )
    assert error is None
    assert selected == ["stats", "voice_contours", "transcript_output"]


@pytest.mark.unit
def test_resolve_modules_group_defaults_omit_exclude_from_default() -> None:
    selected, error = _resolve_modules(None, ["/tmp/a.json"], for_group=True)
    assert error is None
    assert "voice_contours" not in selected
    assert "corrections" not in selected


@pytest.mark.unit
def test_validate_group_readiness_accepts_voice_contours(tmp_path: Path) -> None:
    member = tmp_path / "a.json"
    member.write_text("{}", encoding="utf-8")
    request = GroupAnalysisRequest(
        group_uuid="group-1",
        modules=["stats", "voice_contours"],
        mode="quick",
    )
    fake_member = MagicMock()
    fake_member.file_path = str(member)
    with (
        patch(
            "transcriptx.app.workflows.analysis.get_config",
            return_value=MagicMock(group_analysis=MagicMock(enabled=True)),
        ),
        patch(
            "transcriptx.app.workflows.analysis.resolve_analysis_target",
            return_value=(MagicMock(), [fake_member]),
        ),
    ):
        errors = validate_group_analysis_readiness(request)
    assert not any("not supported for group analysis" in err for err in errors)
