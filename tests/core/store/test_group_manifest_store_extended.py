"""Tests for group manifest store extended."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.domain.group import Group
from transcriptx.core.store import group_manifest_store as gms
from transcriptx.core.store.group_manifest_store import (
    GroupManifestStore,
    canonicalize_group_member_paths,
    manifest_path_for,
)


def test_group_manifest_roundtrip_and_member_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    groups = tmp_path / "groups"
    transcripts.mkdir()
    groups.mkdir()
    monkeypatch.setattr(gms, "_TRANSCRIPTS_DIR", transcripts)
    monkeypatch.setattr(gms, "_GROUPS_DIR", groups)

    store = GroupManifestStore()

    a = transcripts / "a_group_test.json"
    b = transcripts / "nested" / "b_group_test.json"
    b.parent.mkdir(parents=True, exist_ok=True)
    a.write_text("{}", encoding="utf-8")
    b.write_text("{}", encoding="utf-8")

    group = store.create_group(name="Test Group", members=[a, b])

    manifest_path = manifest_path_for(group.group_id)
    assert manifest_path.exists()
    assert manifest_path.parent == groups

    loaded = store.load_by_id(group.group_id)
    assert isinstance(loaded, Group)
    assert loaded.group_id == group.group_id
    assert loaded.name == "Test Group"
    assert loaded.members

    members = store.resolve_group_members(loaded)
    member_paths = {Path(m.file_path) for m in members}
    assert a in member_paths
    assert b in member_paths
    # Preserve manifest member order.
    assert [Path(m.file_path) for m in members] == [a, b]


def test_canonicalize_group_member_paths_dedupes_absolute_and_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    monkeypatch.setattr(gms, "_TRANSCRIPTS_DIR", transcripts)

    p = transcripts / "canon_dedupe_group_test.json"
    p.write_text("{}", encoding="utf-8")
    abs_s = str(p.resolve())
    rel_under_tx = str(p.relative_to(transcripts.resolve()))
    merged = canonicalize_group_member_paths([abs_s, rel_under_tx, abs_s])
    assert len(merged) == 1
    assert merged == canonicalize_group_member_paths([abs_s])
