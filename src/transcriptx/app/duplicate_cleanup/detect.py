"""Group library files by exact bytes, canonical transcript content, and audio links."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Callable, Iterable, Sequence

from transcriptx.app.corpus_inventory.models import InventoryRow
from transcriptx.app.duplicate_cleanup.keep import pick_keeper
from transcriptx.app.duplicate_cleanup.models import (
    DuplicateGroup,
    DuplicateKind,
    DuplicateMember,
    FileFingerprint,
    MemberRole,
)
from transcriptx.app.duplicate_cleanup.scan import fingerprint_file, resolve_path
from transcriptx.core.audio.linked_transcripts import find_transcripts_for_audio
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def _path_key(path: Path) -> str:
    return str(resolve_path(path))


def _title(path: Path) -> str:
    return path.stem or path.name


def _hash_id(parts: Iterable[str]) -> str:
    blob = "\n".join(sorted(parts))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, key: str) -> None:
        self._parent.setdefault(key, key)

    def find(self, key: str) -> str:
        parent = self._parent.setdefault(key, key)
        if parent != key:
            parent = self.find(parent)
            self._parent[key] = parent
        return parent

    def union(self, left: str, right: str) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        if root_left < root_right:
            self._parent[root_right] = root_left
        else:
            self._parent[root_left] = root_right

    def components(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for key in self._parent:
            grouped[self.find(key)].append(key)
        return grouped


def _fingerprints_for_duplicate_sizes(
    paths: Sequence[Path],
) -> tuple[list[FileFingerprint], list[str]]:
    """Hash only files whose size is shared by at least one other file."""
    by_size: dict[int, list[Path]] = defaultdict(list)
    warnings: list[str] = []
    for path in paths:
        try:
            by_size[path.stat().st_size].append(path)
        except OSError as exc:
            warnings.append(f"Could not stat {path.name}: {exc}")
    fingerprints: list[FileFingerprint] = []
    for group in by_size.values():
        if len(group) < 2:
            continue
        for path in group:
            fp = fingerprint_file(path)
            if fp is None:
                warnings.append(f"Could not hash {path.name}")
                continue
            fingerprints.append(fp)
    return fingerprints, warnings


def _group_by_sha(fingerprints: Sequence[FileFingerprint]) -> dict[str, list[FileFingerprint]]:
    grouped: dict[str, list[FileFingerprint]] = defaultdict(list)
    for fp in fingerprints:
        grouped[fp.sha256].append(fp)
    return {digest: items for digest, items in grouped.items() if len(items) >= 2}


def _content_hash(path: Path) -> str | None:
    try:
        from transcriptx.io.transcript_loader import load_canonical_transcript

        canonical = load_canonical_transcript(str(path))
    except Exception as exc:
        logger.debug("Skipping content hash for %s: %s", path, exc)
        return None
    return canonical.content_hash


def _member(
    fp: FileFingerprint,
    role: MemberRole,
    *,
    is_keeper: bool = False,
    unique_at_risk: bool = False,
) -> DuplicateMember:
    return DuplicateMember(
        role=role,
        fingerprint=fp,
        title=_title(fp.path),
        is_keeper=is_keeper,
        unique_transcript_at_risk=unique_at_risk,
    )


def _kind_for(
    members: Sequence[DuplicateMember],
    *,
    in_audio_bytes: bool,
    in_transcript_bytes: bool,
    in_transcript_content: bool,
) -> DuplicateKind:
    roles = {member.role for member in members}
    if roles == {MemberRole.AUDIO}:
        return DuplicateKind.AUDIO_BYTES
    if roles == {MemberRole.TRANSCRIPT}:
        if in_transcript_bytes and not in_transcript_content:
            return DuplicateKind.TRANSCRIPT_BYTES
        if in_transcript_content and not in_transcript_bytes:
            return DuplicateKind.TRANSCRIPT_CONTENT
        return DuplicateKind.TRANSCRIPT_BYTES if in_transcript_bytes else DuplicateKind.TRANSCRIPT_CONTENT
    if MemberRole.AUDIO in roles and MemberRole.TRANSCRIPT in roles:
        return DuplicateKind.LINKED_UNIT
    if in_audio_bytes:
        return DuplicateKind.AUDIO_BYTES
    return DuplicateKind.TRANSCRIPT_CONTENT


def detect_duplicate_groups(
    *,
    audio_paths: Sequence[Path],
    transcript_paths: Sequence[Path],
    rows: dict[str, InventoryRow] | None = None,
    find_linked: Callable[[Path], list[Path]] | None = None,
    fingerprint: Callable[[Path], FileFingerprint | None] | None = None,
    archived_originals: set[str] | None = None,
) -> tuple[list[DuplicateGroup], list[str]]:
    """Return duplicate groups (2+ members) and non-fatal scan warnings."""
    inventory = rows or {}
    find = find_linked or find_transcripts_for_audio
    take_fp = fingerprint or fingerprint_file
    protected = archived_originals or set()
    warnings: list[str] = []

    audio_fps, audio_warn = _fingerprints_for_duplicate_sizes(audio_paths)
    warnings.extend(audio_warn)
    transcript_fps, tx_warn = _fingerprints_for_duplicate_sizes(transcript_paths)
    warnings.extend(tx_warn)

    audio_byte_groups = _group_by_sha(audio_fps)
    transcript_byte_groups = _group_by_sha(transcript_fps)

    content_groups: dict[str, list[Path]] = defaultdict(list)
    for path in transcript_paths:
        digest = _content_hash(path)
        if digest is None:
            warnings.append(f"Could not read canonical content for {path.name}")
            continue
        content_groups[digest].append(path)
    content_groups = {
        digest: items for digest, items in content_groups.items() if len(items) >= 2
    }

    uf = _UnionFind()
    audio_keys: set[str] = set()
    fingerprints: dict[str, FileFingerprint] = {}

    def remember(fp: FileFingerprint, role: MemberRole) -> str:
        key = _path_key(fp.path)
        fingerprints[key] = fp
        uf.add(key)
        if role is MemberRole.AUDIO:
            audio_keys.add(key)
        return key

    for fp in audio_fps:
        remember(fp, MemberRole.AUDIO)
    for fp in transcript_fps:
        remember(fp, MemberRole.TRANSCRIPT)
    for path in transcript_paths:
        key = _path_key(path)
        if key not in fingerprints:
            fp = take_fp(path)
            if fp is None:
                continue
            remember(fp, MemberRole.TRANSCRIPT)
        else:
            uf.add(key)

    audio_byte_keys: set[str] = set()
    for items in audio_byte_groups.values():
        keys = [remember(fp, MemberRole.AUDIO) for fp in items]
        audio_byte_keys.update(keys)
        for extra in keys[1:]:
            uf.union(keys[0], extra)

    transcript_byte_keys: set[str] = set()
    for items in transcript_byte_groups.values():
        keys = [remember(fp, MemberRole.TRANSCRIPT) for fp in items]
        transcript_byte_keys.update(keys)
        for extra in keys[1:]:
            uf.union(keys[0], extra)

    transcript_content_keys: set[str] = set()
    for items in content_groups.values():
        keys = [_path_key(path) for path in items]
        for key, path in zip(keys, items):
            if key not in fingerprints:
                fp = take_fp(path)
                if fp is None:
                    continue
                remember(fp, MemberRole.TRANSCRIPT)
            else:
                uf.add(key)
            transcript_content_keys.add(key)
        present = [key for key in keys if key in fingerprints]
        for extra in present[1:]:
            uf.union(present[0], extra)

    hashed_duplicate_transcripts = transcript_byte_keys | transcript_content_keys
    unique_transcript_keys = {
        _path_key(path)
        for path in transcript_paths
        if _path_key(path) not in hashed_duplicate_transcripts
    }

    for items in audio_byte_groups.values():
        for fp in items:
            audio_key = _path_key(fp.path)
            try:
                linked = find(fp.path)
            except Exception as exc:
                warnings.append(f"Could not resolve transcripts for {fp.path.name}: {exc}")
                continue
            for transcript in linked:
                t_key = _path_key(transcript)
                if t_key not in fingerprints:
                    t_fp = take_fp(transcript)
                    if t_fp is None:
                        continue
                    remember(t_fp, MemberRole.TRANSCRIPT)
                    if t_key not in hashed_duplicate_transcripts:
                        unique_transcript_keys.add(t_key)
                uf.union(audio_key, t_key)

    groups: list[DuplicateGroup] = []
    for _root, keys in uf.components().items():
        if len(keys) < 2:
            continue
        members: list[DuplicateMember] = []
        for key in keys:
            fp = fingerprints.get(key)
            if fp is None:
                continue
            role = MemberRole.AUDIO if key in audio_keys else MemberRole.TRANSCRIPT
            members.append(_member(fp, role))
        if len(members) < 2:
            continue

        keeper_src = pick_keeper(members, inventory)
        extras_src = [
            member
            for member in members
            if _path_key(member.fingerprint.path) != _path_key(keeper_src.fingerprint.path)
        ]
        # Never delete an archived original that belongs to the keeper.
        filtered_extras: list[DuplicateMember] = []
        for member in extras_src:
            extra_key = _path_key(member.fingerprint.path)
            if extra_key in protected:
                warnings.append(
                    f"Keeping archived original of retained transcript: {member.fingerprint.path.name}"
                )
                continue
            filtered_extras.append(member)
        if not filtered_extras:
            continue

        unique_at_risk = False
        extras: list[DuplicateMember] = []
        for member in filtered_extras:
            at_risk = (
                member.role is MemberRole.TRANSCRIPT
                and _path_key(member.fingerprint.path) in unique_transcript_keys
            )
            if at_risk:
                unique_at_risk = True
            extras.append(
                _member(
                    member.fingerprint,
                    member.role,
                    unique_at_risk=at_risk,
                )
            )
        keeper = _member(keeper_src.fingerprint, keeper_src.role, is_keeper=True)
        in_audio = any(_path_key(m.fingerprint.path) in audio_byte_keys for m in members)
        in_tx_bytes = any(
            _path_key(m.fingerprint.path) in transcript_byte_keys for m in members
        )
        in_tx_content = any(
            _path_key(m.fingerprint.path) in transcript_content_keys for m in members
        )
        groups.append(
            DuplicateGroup(
                group_id=_hash_id(_path_key(m.fingerprint.path) for m in members),
                kind=_kind_for(
                    members,
                    in_audio_bytes=in_audio,
                    in_transcript_bytes=in_tx_bytes,
                    in_transcript_content=in_tx_content,
                ),
                keeper=keeper,
                extras=tuple(
                    sorted(extras, key=lambda item: str(item.fingerprint.path))
                ),
                unique_transcript_at_risk=unique_at_risk,
            )
        )

    groups.sort(key=lambda group: (group.kind.value, group.group_id))
    return groups, warnings
