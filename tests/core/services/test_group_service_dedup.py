"""GroupService dedup and transcript existence validation."""

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


@pytest.mark.unit
def test_create_or_get_reuses_identical_member_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure_project_root(monkeypatch, tmp_path)
    t1 = _write_transcript(project_root, "transcripts/a.json")
    t2 = _write_transcript(project_root, "transcripts/b.json")

    first, created_first = GroupService.create_or_get_group_with_status(
        name="One",
        group_type="group",
        transcript_refs=[str(t1), str(t2)],
    )
    second, created_second = GroupService.create_or_get_group_with_status(
        name="Two",
        group_type="group",
        transcript_refs=[str(t1), str(t2)],
    )
    assert created_first is True
    assert created_second is False
    assert first.group_id == second.group_id
    reused = GroupService.create_or_get_group(
        name="Three",
        group_type="group",
        transcript_refs=[str(t1), str(t2)],
    )
    assert reused.group_id == first.group_id


@pytest.mark.unit
def test_create_or_get_order_sensitive_members(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure_project_root(monkeypatch, tmp_path)
    t1 = _write_transcript(project_root, "transcripts/a.json")
    t2 = _write_transcript(project_root, "transcripts/b.json")
    g1, _ = GroupService.create_or_get_group_with_status(
        name="AB",
        group_type="group",
        transcript_refs=[str(t1), str(t2)],
    )
    g2, created = GroupService.create_or_get_group_with_status(
        name="BA",
        group_type="group",
        transcript_refs=[str(t2), str(t1)],
    )
    assert created is True
    assert g1.group_id != g2.group_id


@pytest.mark.unit
def test_validate_transcripts_exist_raises_for_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure_project_root(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="not found"):
        GroupService.validate_transcripts_exist(
            [str(tmp_path / "missing" / "nope.json")]
        )


@pytest.mark.unit
def test_create_or_get_requires_at_least_one_member(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure_project_root(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="at least one"):
        GroupService.create_or_get_group_with_status(
            name="Empty",
            group_type="group",
            transcript_refs=[],
        )
