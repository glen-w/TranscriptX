"""Integrity scan and algorithmic rebuild helpers (Phase 1, no required SQLite)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from transcriptx.core.speaker_profiles.aggregates import list_profiles
from transcriptx.core.speaker_profiles.hashing import sha256_file
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.layout import (
    events_dir,
    links_dir,
    operations_dir,
    profiles_dir,
)
from transcriptx.core.speaker_profiles.models import SpeakerProfileLinkV1
from transcriptx.core.speaker_profiles.recovery import list_operations
from transcriptx.core.speaker_profiles.store_io import parse_model


@dataclass(frozen=True)
class IntegrityReport:
    profiles_scanned: int
    links_scanned: int
    events_scanned: int
    operations_scanned: int
    link_key_mismatches: tuple[str, ...]
    corrupt_links: tuple[str, ...]
    blocking_operations: tuple[str, ...]
    duplicate_link_keys: tuple[str, ...]
    ok: bool


@dataclass(frozen=True)
class ReverseLookupStats:
    """Algorithmic assertion helper for hashed link path lookup."""

    examined_paths: int
    found: bool


def reverse_lookup_link(
    *,
    root: Path,
    managed_transcript_id: str,
    local_speaker_key: str,
) -> ReverseLookupStats:
    """O(1) hashed-path lookup — does not scan the full link tree."""
    key = link_file_key(managed_transcript_id, local_speaker_key)
    path = links_dir(root) / f"{key}.speaker_link.json"
    return ReverseLookupStats(examined_paths=1, found=path.is_file())


def run_integrity_scan(root: Path) -> IntegrityReport:
    root = Path(root)
    profiles = list(profiles_dir(root).glob("*.speaker_profile.json")) if profiles_dir(root).exists() else []
    link_paths = list(links_dir(root).glob("*.speaker_link.json")) if links_dir(root).exists() else []
    event_paths = list(events_dir(root).glob("*.speaker_event.json")) if events_dir(root).exists() else []
    op_paths = list(operations_dir(root).glob("*.op.json")) if operations_dir(root).exists() else []

    mismatches: list[str] = []
    corrupt: list[str] = []
    seen_keys: dict[str, str] = {}
    duplicates: list[str] = []

    for path in link_paths:
        try:
            link = parse_model(SpeakerProfileLinkV1, path)
        except Exception:
            corrupt.append(str(path))
            continue
        expected = link_file_key(link.managed_transcript_id, link.local_speaker_key)
        stem = path.name[: -len(".speaker_link.json")]
        if stem != expected:
            mismatches.append(str(path))
        if expected in seen_keys:
            duplicates.append(expected)
        else:
            seen_keys[expected] = str(path)

    blocking = [
        op.operation_id
        for op in list_operations(root)
        if op.phase not in {"complete"}
        and not (
            op.phase == "failed"
            and (op.receipt or {}).get("abort_class") == "proven_aborted"
        )
    ]

    ok = not (mismatches or corrupt or duplicates or blocking)
    return IntegrityReport(
        profiles_scanned=len(profiles),
        links_scanned=len(link_paths),
        events_scanned=len(event_paths),
        operations_scanned=len(op_paths),
        link_key_mismatches=tuple(mismatches),
        corrupt_links=tuple(corrupt),
        blocking_operations=tuple(blocking),
        duplicate_link_keys=tuple(sorted(set(duplicates))),
        ok=ok,
    )


def rebuild_freshness_token(root: Path) -> str:
    """Byte-stable token over profile listing metadata (rebuild idempotence)."""
    import hashlib
    import json

    items = list_profiles(root=root)
    payload = [
        {
            "profile_id": i.profile_id,
            "status": i.status,
            "updated_at": i.updated_at,
            "link_count": i.link_count,
            "needs_repair": i.needs_repair,
        }
        for i in items
    ]
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def scan_bound_for_listing(root: Path) -> tuple[int, int]:
    """Return (files_scanned, records_parsed) for list_profiles hot path."""
    pref = profiles_dir(root)
    if not pref.is_dir():
        return (0, 0)
    files = list(pref.glob("*.speaker_profile.json"))
    parsed = 0
    for path in files:
        if sha256_file(path) is not None:
            parsed += 1
    return (len(files), parsed)
