from __future__ import annotations

from pathlib import Path

from transcriptx.core.domain.group import Group
from transcriptx.core.store.group_manifest_store import (
    GroupManifestStore,
    canonicalize_group_member_paths,
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
    # Preserve manifest member order.
    assert [Path(m.file_path) for m in members] == [a, b]


def test_canonicalize_group_member_paths_dedupes_absolute_and_relative() -> None:
    transcripts_root = PATHS.transcripts_dir
    p = transcripts_root / "canon_dedupe_group_test.json"
    p.write_text("{}", encoding="utf-8")
    try:
        abs_s = str(p.resolve())
        rel_under_tx = str(p.relative_to(transcripts_root.resolve()))
        merged = canonicalize_group_member_paths([abs_s, rel_under_tx, abs_s])
        assert len(merged) == 1
        assert merged == canonicalize_group_member_paths([abs_s])
    finally:
        p.unlink(missing_ok=True)
