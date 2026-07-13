"""Tests for file-only target resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

import transcriptx.core.services.group_service as group_service_module
import transcriptx.core.store.group_manifest_store as group_store_module
from transcriptx.core.pipeline.target_resolver import (
    AnalysisScope,
    FileTranscriptMember,
    GroupRef,
    TranscriptRef,
    resolve_analysis_target,
)
from transcriptx.core.store.group_manifest_store import GroupManifestStore


def _configure_project_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
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


def test_resolve_transcript_path_returns_file_member(tmp_path: Path) -> None:
    transcript_file = tmp_path / "nested" / "transcript.json"
    transcript_file.parent.mkdir(parents=True, exist_ok=True)
    transcript_file.write_text("{}", encoding="utf-8")

    scope, members = resolve_analysis_target(TranscriptRef(path=str(transcript_file)))

    assert isinstance(scope, AnalysisScope)
    assert scope.scope_type == "transcript"
    assert scope.display_name == "transcript"
    assert len(members) == 1
    assert isinstance(members[0], FileTranscriptMember)
    assert members[0].file_path == str(transcript_file.resolve())
    assert members[0].file_name == "transcript.json"
    assert members[0].source == "file"


def test_resolve_group_path_uses_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure_project_root(monkeypatch, tmp_path)
    transcript = project_root / "transcripts" / "one.json"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text("{}", encoding="utf-8")

    store = GroupManifestStore()
    group = store.create_group(name="Team", members=[transcript])

    scope, members = resolve_analysis_target(
        GroupRef(path=str(project_root / "groups" / f"{group.group_id}.group.json"))
    )

    assert scope.scope_type == "group"
    assert scope.uuid == group.group_id
    assert len(members) == 1
    assert members[0].file_path == str(transcript.resolve())


def test_resolve_group_with_no_members_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure_project_root(monkeypatch, tmp_path)
    transcript = project_root / "transcripts" / "one.json"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text("{}", encoding="utf-8")
    store = GroupManifestStore()
    group = store.create_group(name="SoonEmpty", members=[transcript])
    monkeypatch.setattr(
        group_service_module.GroupService,
        "get_members",
        staticmethod(lambda _group_id: []),
    )
    with pytest.raises(ValueError, match="no members"):
        resolve_analysis_target(GroupRef(path=group.group_id))


def test_transcript_path_must_exist(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_analysis_target(TranscriptRef(path=str(tmp_path / "missing.json")))
