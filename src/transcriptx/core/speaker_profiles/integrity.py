"""Integrity scan and algorithmic rebuild helpers (Phase 1, no required SQLite)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from transcriptx.core.speaker_profiles.aggregates import list_profiles
from transcriptx.core.speaker_profiles.hashing import sha256_file
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.layout import (
    events_dir,
    links_dir,
    operations_dir,
    profiles_dir,
)
from transcriptx.core.speaker_profiles.models import (
    SpeakerProfileEventV1,
    SpeakerProfileLinkV1,
    SpeakerProfileOperationV1,
    SpeakerProfileV1,
)
from transcriptx.core.speaker_profiles.operations import relative_link_path, relative_profile_path
from transcriptx.core.speaker_profiles.recovery import (
    affected_relpaths,
    classify_operation,
    list_operations_detailed,
)
from transcriptx.core.speaker_profiles.store_io import parse_model


RecoveryClass = Literal[
    "complete",
    "proven_aborted",
    "partial",
    "ambiguous",
    "needs_repair",
]


@dataclass(frozen=True)
class BlockingOperationInfo:
    operation_id: str
    recovery_class: RecoveryClass
    phase: str
    affected_relpaths: tuple[str, ...]
    profile_ids: tuple[str, ...]
    link_file_keys: tuple[str, ...]


@dataclass(frozen=True)
class IntegrityReport:
    profiles_scanned: int
    links_scanned: int
    events_scanned: int
    operations_scanned: int
    link_key_mismatches: tuple[str, ...]
    corrupt_profiles: tuple[str, ...]
    corrupt_links: tuple[str, ...]
    corrupt_events: tuple[str, ...]
    corrupt_operations: tuple[str, ...]
    blocking_operations: tuple[str, ...]
    blocking_details: tuple[BlockingOperationInfo, ...]
    duplicate_link_keys: tuple[str, ...]
    ok: bool
    avatar_issues: tuple[str, ...] = ()
    voice_issues: tuple[str, ...] = ()


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


def _entity_ids_from_relpaths(
    relpaths: set[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    profile_ids: list[str] = []
    link_keys: list[str] = []
    for rel in sorted(relpaths):
        if rel.startswith("profiles/") and rel.endswith(".speaker_profile.json"):
            stem = Path(rel).name[: -len(".speaker_profile.json")]
            profile_ids.append(stem)
        elif rel.startswith("links/") and rel.endswith(".speaker_link.json"):
            stem = Path(rel).name[: -len(".speaker_link.json")]
            link_keys.append(stem)
    return tuple(profile_ids), tuple(link_keys)


def run_integrity_scan(root: Path) -> IntegrityReport:
    root = Path(root)
    profiles = (
        list(profiles_dir(root).glob("*.speaker_profile.json"))
        if profiles_dir(root).exists()
        else []
    )
    link_paths = (
        list(links_dir(root).glob("*.speaker_link.json"))
        if links_dir(root).exists()
        else []
    )
    event_paths = (
        list(events_dir(root).glob("*.speaker_event.json"))
        if events_dir(root).exists()
        else []
    )
    op_paths = (
        list(operations_dir(root).glob("*.op.json"))
        if operations_dir(root).exists()
        else []
    )

    mismatches: list[str] = []
    corrupt_profiles: list[str] = []
    corrupt_links: list[str] = []
    corrupt_events: list[str] = []
    seen_keys: dict[str, str] = {}
    duplicates: list[str] = []
    avatar_issues: list[str] = []
    claimed_avatar_paths: set[str] = set()

    for path in profiles:
        try:
            profile = parse_model(SpeakerProfileV1, path)
        except Exception:
            corrupt_profiles.append(str(path))
            continue
        if profile.avatar_relpath:
            claimed_avatar_paths.add(profile.avatar_relpath)
            asset = root / profile.avatar_relpath
            if not asset.is_file():
                avatar_issues.append(f"avatar_missing:{profile.profile_id}")
            else:
                try:
                    from transcriptx.core.speaker_profiles.avatars import (
                        verify_avatar_bytes,
                    )
                    from transcriptx.core.speaker_profiles.path_safety import (
                        assert_not_symlink,
                    )

                    assert_not_symlink(asset, what="avatar integrity")
                    data = asset.read_bytes()
                    if profile.avatar_sha256 and not verify_avatar_bytes(
                        data, expected_sha256=profile.avatar_sha256
                    ):
                        avatar_issues.append(f"avatar_hash_mismatch:{profile.profile_id}")
                except Exception:
                    avatar_issues.append(f"avatar_corrupt:{profile.profile_id}")

    assets_root = profiles_dir(root) / "assets"
    if assets_root.is_dir():
        for asset in assets_root.glob("*/avatar.webp"):
            rel = str(asset.relative_to(root)).replace("\\", "/")
            if rel not in claimed_avatar_paths:
                avatar_issues.append(f"avatar_orphan:{rel}")

    voice_issues: list[str] = []
    wipe_receipt = root / "voice" / "wipe_receipt.json"
    if wipe_receipt.is_file():
        try:
            import json

            receipt = json.loads(wipe_receipt.read_text(encoding="utf-8"))
            pending = receipt.get("pending_paths") or []
            if pending:
                voice_issues.append(f"wipe_incomplete:{len(pending)}")
            else:
                voice_issues.append("wipe_receipt_stale")
        except Exception:
            voice_issues.append("wipe_receipt_corrupt")
    try:
        from transcriptx.core.speaker_profiles.voice.privacy import VoicePrivacyStore

        privacy = VoicePrivacyStore(root).read()
        if privacy.wipe_required:
            voice_issues.append("wipe_required")
    except Exception:
        pass
    samples_dir = root / "voice" / "samples"
    if samples_dir.is_dir():
        for path in samples_dir.glob("*.voice_sample.json"):
            try:
                from transcriptx.core.speaker_profiles.voice.models import VoiceSampleV1

                parse_model(VoiceSampleV1, path)
            except Exception:
                voice_issues.append(f"voice_sample_corrupt:{path.name}")
    emb_dir = root / "voice" / "embeddings"
    if emb_dir.is_dir():
        for path in emb_dir.glob("*.voice_embedding.json"):
            try:
                from transcriptx.core.speaker_profiles.voice.models import VoiceEmbeddingV1

                emb = parse_model(VoiceEmbeddingV1, path)
                vec = root / "voice" / "vectors" / f"{emb.embedding_id}.npy"
                if not vec.is_file():
                    voice_issues.append(f"voice_vector_missing:{emb.embedding_id}")
            except Exception:
                voice_issues.append(f"voice_embedding_corrupt:{path.name}")

    for path in link_paths:
        try:
            link = parse_model(SpeakerProfileLinkV1, path)
        except Exception:
            corrupt_links.append(str(path))
            continue
        expected = link_file_key(link.managed_transcript_id, link.local_speaker_key)
        stem = path.name[: -len(".speaker_link.json")]
        if stem != expected:
            mismatches.append(str(path))
        if expected in seen_keys:
            duplicates.append(expected)
        else:
            seen_keys[expected] = str(path)

    for path in event_paths:
        try:
            parse_model(SpeakerProfileEventV1, path)
        except Exception:
            corrupt_events.append(str(path))

    ops_result = list_operations_detailed(root)
    corrupt_operations = tuple(ops_result.corrupt_paths)

    blocking_details: list[BlockingOperationInfo] = []
    blocking_ids: list[str] = []
    for op in ops_result.operations:
        if op.phase == "complete":
            continue
        receipt = op.receipt or {}
        if op.phase == "failed" and receipt.get("abort_class") == "proven_aborted":
            continue
        report = classify_operation(root, op)
        if not report.blocking:
            continue
        rels = affected_relpaths(op)
        profile_ids, link_keys = _entity_ids_from_relpaths(rels)
        blocking_ids.append(op.operation_id)
        blocking_details.append(
            BlockingOperationInfo(
                operation_id=op.operation_id,
                recovery_class=report.recovery_class,
                phase=op.phase,
                affected_relpaths=tuple(sorted(rels)),
                profile_ids=profile_ids,
                link_file_keys=link_keys,
            )
        )

    ok = not (
        mismatches
        or corrupt_profiles
        or corrupt_links
        or corrupt_events
        or corrupt_operations
        or duplicates
        or blocking_ids
        or avatar_issues
        or voice_issues
    )
    return IntegrityReport(
        profiles_scanned=len(profiles),
        links_scanned=len(link_paths),
        events_scanned=len(event_paths),
        operations_scanned=len(op_paths),
        link_key_mismatches=tuple(mismatches),
        corrupt_profiles=tuple(corrupt_profiles),
        corrupt_links=tuple(corrupt_links),
        corrupt_events=tuple(corrupt_events),
        corrupt_operations=corrupt_operations,
        blocking_operations=tuple(blocking_ids),
        blocking_details=tuple(blocking_details),
        duplicate_link_keys=tuple(sorted(set(duplicates))),
        ok=ok,
        avatar_issues=tuple(avatar_issues),
        voice_issues=tuple(voice_issues),
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


def intersected_entities(
    report: IntegrityReport,
) -> tuple[set[str], set[str]]:
    """Profile ids and link file keys intersected by blocking operations."""
    profiles: set[str] = set()
    links: set[str] = set()
    for detail in report.blocking_details:
        profiles.update(detail.profile_ids)
        links.update(detail.link_file_keys)
    return profiles, links


# Re-export helpers used by callers that previously imported relative paths here.
__all__ = [
    "BlockingOperationInfo",
    "IntegrityReport",
    "ReverseLookupStats",
    "intersected_entities",
    "rebuild_freshness_token",
    "reverse_lookup_link",
    "run_integrity_scan",
    "scan_bound_for_listing",
    "relative_link_path",
    "relative_profile_path",
]
