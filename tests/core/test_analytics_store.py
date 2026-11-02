"""Theme J Narrow derived SQLite store."""

from __future__ import annotations

import json

from transcriptx.core.analytics_store import (
    collect_profile_rows,
    connect,
    profiles_for_gallery,
    rebuild_from_profiles_dir,
)


def test_rebuild_gallery(tmp_path) -> None:
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "p1.speaker_profile.json").write_text(
        json.dumps({"profile_id": "p1", "display_name": "Ada"}),
        encoding="utf-8",
    )
    (profiles_dir / "p1.speaker_link.json").write_text(
        json.dumps(
            {
                "profile_id": "p1",
                "transcript_stem": "meeting",
                "diarized_id": "SPEAKER_00",
            }
        ),
        encoding="utf-8",
    )
    db = rebuild_from_profiles_dir(tmp_path / "data", profiles_dir)
    conn = connect(db)
    try:
        rows = profiles_for_gallery(conn)
    finally:
        conn.close()
    assert rows[0]["profile_id"] == "p1"
    assert rows[0]["display_name"] == "Ada"
    assert rows[0]["link_count"] == 1
    collected, links = collect_profile_rows(profiles_dir)
    assert len(collected) == 1 and len(links) == 1
