"""Tests for file-backed GroupService."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import transcriptx.core.services.group_service as group_service_module
import transcriptx.core.store.group_manifest_store as group_store_module
from transcriptx.core.services.group_service import GroupService
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


def _write_transcript(project_root: Path, rel_path: str) -> Path:
    transcript_path = project_root / rel_path
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(json.dumps({"segments": []}), encoding="utf-8")
    return transcript_path


def test_create_and_resolve_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure_project_root(monkeypatch, tmp_path)
    t1 = _write_transcript(project_root, "transcripts/a.json")
    t2 = _write_transcript(project_root, "transcripts/b.json")

    group, created = GroupService.create_or_get_group_with_status(
        name="Team A",
        group_type="group",
        transcript_refs=[str(t1), str(t2)],
        description="Example",
    )

    assert created is True
    assert group.name == "Team A"
    manifest_path = project_root / "groups" / f"{group.group_id}.group.json"
    assert manifest_path.exists()

    resolved = GroupService.resolve_group_identifier(group.group_id)
    assert resolved.group_id == group.group_id
    assert resolved.members == ["transcripts/a.json", "transcripts/b.json"]
    assert GroupService.get_members(group.group_id)[0].file_path == str(t1.resolve())


def test_update_membership_and_rename(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure_project_root(monkeypatch, tmp_path)
    t1 = _write_transcript(project_root, "transcripts/one.json")
    t2 = _write_transcript(project_root, "transcripts/two.json")

    group = GroupService.create_or_get_group(
        name="Before",
        group_type="group",
        transcript_refs=[str(t1)],
    )

    renamed = GroupService.rename_group(group.group_id, "After")
    assert renamed.name == "After"

    updated = GroupService.update_membership(group.group_id, [str(t1), str(t2)])
    assert updated.members == ["transcripts/one.json", "transcripts/two.json"]


def test_delete_group_removes_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure_project_root(monkeypatch, tmp_path)
    t1 = _write_transcript(project_root, "transcripts/delete.json")

    group = GroupService.create_or_get_group(
        name="Delete Me",
        group_type="group",
        transcript_refs=[str(t1)],
    )
    manifest_path = project_root / "groups" / f"{group.group_id}.group.json"
    assert manifest_path.exists()

    assert GroupService.delete_group(group.group_id) is True
    assert not manifest_path.exists()
    assert GroupService.list_groups() == []


def test_list_groups_best_effort_skips_broken_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure_project_root(monkeypatch, tmp_path)
    t1 = _write_transcript(project_root, "transcripts/ok.json")
    group = GroupService.create_or_get_group(
        name="Good",
        group_type="group",
        transcript_refs=[str(t1)],
    )
    bad_path = project_root / "groups" / "deadbeef-dead-dead-dead-deadbeef0001.group.json"
    bad_path.write_text(
        json.dumps(
            {
                "version": 1,
                "group_id": "deadbeef-dead-dead-dead-deadbeef0001",
                "name": "Broken",
                "members": ["data/transcripts/does_not_exist.json"],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    store = group_service_module._STORE
    groups, warnings = store.list_groups_best_effort()
    assert len(groups) == 1
    assert groups[0].group_id == group.group_id
    assert len(warnings) == 1
    assert "does_not_exist" in warnings[0]
