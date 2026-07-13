"""SubjectService group subject resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import transcriptx.core.store.group_manifest_store as group_store_module
import transcriptx.core.services.group_service as group_service_module
from transcriptx.core.pipeline.target_resolver import GroupRef
from transcriptx.core.services.group_service import GroupService
from transcriptx.core.store.group_manifest_store import GroupManifestStore
from transcriptx.web.services.subject_service import SubjectService


def _configure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
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


@pytest.mark.unit
def test_resolve_current_subject_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure(monkeypatch, tmp_path)
    transcript = project_root / "transcripts" / "a.json"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps({"segments": []}), encoding="utf-8")
    group = GroupService.create_or_get_group(
        name="Studio Group",
        group_type="group",
        transcript_refs=[str(transcript)],
    )
    subject = SubjectService.resolve_current_subject(
        {"subject_type": "group", "subject_id": group.group_id}
    )
    assert subject is not None
    assert subject.subject_type == "group"
    assert isinstance(subject.ref, GroupRef)
    assert subject.scope.scope_type == "group"
    assert subject.display.badge == "Group"
    assert subject.display.name == "Studio Group"
    assert subject.display.member_count == 1
    assert len(subject.members) == 1


@pytest.mark.unit
def test_resolve_current_subject_missing_group_returns_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure(monkeypatch, tmp_path)
    assert (
        SubjectService.resolve_current_subject(
            {"subject_type": "group", "subject_id": "no-such-group"}
        )
        is None
    )


@pytest.mark.unit
def test_resolve_current_subject_rejects_bad_type() -> None:
    assert SubjectService.resolve_current_subject({"subject_type": "other"}) is None
    assert (
        SubjectService.resolve_current_subject(
            {"subject_type": "group", "subject_id": ""}
        )
        is None
    )
