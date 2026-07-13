"""GroupManifestStore.resolve_group_identifier edge cases."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import transcriptx.core.store.group_manifest_store as group_store_module
from transcriptx.core.store.group_manifest_store import GroupManifestStore


def _configure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "groups").mkdir()
    monkeypatch.setattr(group_store_module, "PROJECT_ROOT", project_root, raising=False)
    monkeypatch.setattr(
        group_store_module, "_GROUPS_DIR", project_root / "groups", raising=False
    )
    return project_root


@pytest.mark.unit
def test_resolve_group_identifier_by_id_and_manifest_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure(monkeypatch, tmp_path)
    store = GroupManifestStore()
    transcript = project_root / "transcripts" / "a.json"
    transcript.parent.mkdir(parents=True)
    transcript.write_text("{}", encoding="utf-8")
    group = store.create_group(
        name="G",
        members=["transcripts/a.json"],
        description=None,
    )
    by_id = store.resolve_group_identifier(group.group_id)
    assert by_id.group_id == group.group_id

    manifest = project_root / "groups" / f"{group.group_id}.group.json"
    by_path = store.resolve_group_identifier(str(manifest))
    assert by_path.group_id == group.group_id


@pytest.mark.unit
def test_resolve_group_identifier_rejects_wrong_suffix_and_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = _configure(monkeypatch, tmp_path)
    store = GroupManifestStore()
    weird = project_root / "groups" / "not-a-group.json"
    weird.write_text(json.dumps({"group_id": "x"}), encoding="utf-8")
    with pytest.raises(ValueError, match="\\.group\\.json"):
        store.resolve_group_identifier(str(weird))
    with pytest.raises(ValueError, match="No group manifest"):
        store.resolve_group_identifier("missing-group-id")
