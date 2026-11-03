"""Theme J Narrow: derived SQLite store for Speakers / profile_id gallery.

File/sidecar layout remains source of truth. This DB is rebuildable.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Sequence

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS speaker_profiles (
    profile_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    path TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profile_links (
    profile_id TEXT NOT NULL,
    transcript_stem TEXT NOT NULL,
    diarized_id TEXT,
    PRIMARY KEY (profile_id, transcript_stem, diarized_id)
);
CREATE INDEX IF NOT EXISTS idx_profile_links_profile
    ON profile_links(profile_id);
"""


def default_db_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / "state" / "analytics_derived.sqlite"


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn


def rebuild_from_rows(
    conn: sqlite3.Connection,
    *,
    profiles: Sequence[dict[str, Any]],
    links: Sequence[dict[str, Any]],
) -> None:
    conn.execute("DELETE FROM profile_links")
    conn.execute("DELETE FROM speaker_profiles")
    conn.executemany(
        "INSERT OR REPLACE INTO speaker_profiles(profile_id, display_name, path) "
        "VALUES (:profile_id, :display_name, :path)",
        [
            {
                "profile_id": str(row["profile_id"]),
                "display_name": str(row.get("display_name") or ""),
                "path": str(row.get("path") or ""),
            }
            for row in profiles
        ],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO profile_links(profile_id, transcript_stem, diarized_id) "
        "VALUES (:profile_id, :transcript_stem, :diarized_id)",
        [
            {
                "profile_id": str(row["profile_id"]),
                "transcript_stem": str(row.get("transcript_stem") or ""),
                "diarized_id": str(row.get("diarized_id") or ""),
            }
            for row in links
        ],
    )
    conn.commit()


def profiles_for_gallery(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT p.profile_id, p.display_name, p.path,
               COUNT(l.transcript_stem) AS link_count
        FROM speaker_profiles p
        LEFT JOIN profile_links l ON l.profile_id = p.profile_id
        GROUP BY p.profile_id
        ORDER BY p.display_name COLLATE NOCASE, p.profile_id
        """
    ).fetchall()
    return [dict(r) for r in rows]


def collect_profile_rows(
    profiles_dir: str | Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Scan file-backed speaker profiles + links (same globs as aggregates)."""
    import json

    root = Path(profiles_dir)
    profiles: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    if not root.is_dir():
        return profiles, links
    for path in sorted(root.glob("*.speaker_profile.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pid = str(data.get("profile_id") or path.stem.replace(".speaker_profile", ""))
        profiles.append(
            {
                "profile_id": pid,
                "display_name": data.get("display_name") or data.get("name") or pid,
                "path": str(path),
            }
        )
    for path in sorted(root.glob("*.speaker_link.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        links.append(
            {
                "profile_id": str(data.get("profile_id") or ""),
                "transcript_stem": str(
                    data.get("transcript_stem") or data.get("stem") or ""
                ),
                "diarized_id": str(
                    data.get("diarized_id") or data.get("speaker_id") or ""
                ),
            }
        )
    return profiles, links


def rebuild_from_profiles_dir(data_dir: str | Path, profiles_dir: str | Path) -> Path:
    db_path = default_db_path(data_dir)
    profiles, links = collect_profile_rows(profiles_dir)
    conn = connect(db_path)
    try:
        rebuild_from_rows(conn, profiles=profiles, links=links)
    finally:
        conn.close()
    return db_path
