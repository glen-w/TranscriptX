from __future__ import annotations

from pathlib import Path

from transcriptx.core.domain.group import Group
from transcriptx.core.store.group_manifest_store import (
    GroupManifestStore,
    manifest_path_for,
)
from transcriptx.core.utils.paths import PATHS


def test_group_manifest_roundtrip_and_member_resolution(tmp_path: Path) -> None:
    store = GroupManifestStore()

    # Create member transcripts under the real transcripts_dir so helper invariants hold.
    transcripts_root = PATHS.transcripts_dir
    a = transcripts_root / "a_group_test.json"
    b = transcripts_root / "nested" / "b_group_test.json"
    b.parent.mkdir(parents=True, exist_ok=True)
    a.write_text("{}", encoding="utf-8")
    b.write_text("{}", encoding="utf-8")

    group = store.create_group(name="Test Group", members=[a, b])

    manifest_path = manifest_path_for(group.group_id)
    assert manifest_path.exists()

    loaded = store.load_by_id(group.group_id)
    assert isinstance(loaded, Group)
    assert loaded.group_id == group.group_id
    assert loaded.name == "Test Group"
    assert loaded.members

    members = store.resolve_group_members(loaded)
    member_paths = {Path(m.file_path) for m in members}
    assert a in member_paths
    assert b in member_paths
