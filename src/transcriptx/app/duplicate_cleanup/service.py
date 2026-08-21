"""Application façade for library duplicate detection and removal. No Streamlit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Sequence

from transcriptx.app.corpus_inventory.models import InventoryRow, TranscriptRef
from transcriptx.app.duplicate_cleanup.detect import detect_duplicate_groups
from transcriptx.app.duplicate_cleanup.execute import (
    archived_original_path,
    execute_preview,
)
from transcriptx.app.duplicate_cleanup.models import (
    DuplicateAuthorization,
    DuplicateGroup,
    DuplicatePreview,
    DuplicateResult,
    MemberRole,
)
from transcriptx.app.duplicate_cleanup.scan import (
    list_audio_files,
    list_transcript_files,
    resolve_path,
)


def _plan_id(groups: Sequence[DuplicateGroup]) -> str:
    payload = [
        {
            "kind": group.kind.value,
            "keeper": str(resolve_path(group.keeper.fingerprint.path)),
            "extras": [
                str(resolve_path(member.fingerprint.path)) for member in group.extras
            ],
        }
        for group in groups
    ]
    blob = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _inventory_rows(transcript_paths: Sequence[Path]) -> dict[str, InventoryRow]:
    from transcriptx.app.corpus_inventory.service import CorpusInventory
    from transcriptx.core.utils.slug_manager import list_all_transcripts

    by_source: dict[str, dict] = {}
    try:
        for entry in list_all_transcripts():
            source = entry.get("source_path")
            if source:
                by_source[str(resolve_path(Path(str(source))))] = entry
    except Exception:
        pass
    refs: list[TranscriptRef] = []
    for path in transcript_paths:
        entry = by_source.get(str(resolve_path(path)), {})
        refs.append(
            TranscriptRef(
                path=path,
                base_name=path.stem,
                slug=entry.get("slug") if isinstance(entry, dict) else None,
                transcript_key=(
                    entry.get("transcript_key") if isinstance(entry, dict) else None
                ),
            )
        )
    try:
        inventory = CorpusInventory()
        rows = inventory.list_rows(refs)
    except Exception:
        return {}
    mapping: dict[str, InventoryRow] = {}
    for row in rows:
        mapping[str(resolve_path(row.transcript_path))] = row
    return mapping


def _protected_originals(groups: Sequence[DuplicateGroup]) -> set[str]:
    protected: set[str] = set()
    for group in groups:
        keeper = group.keeper
        if keeper.role is not MemberRole.TRANSCRIPT:
            continue
        original = archived_original_path(keeper.fingerprint.path)
        if original is not None:
            protected.add(str(resolve_path(original)))
    return protected


def _strip_protected(
    groups: Sequence[DuplicateGroup], protected: set[str]
) -> list[DuplicateGroup]:
    if not protected:
        return list(groups)
    out: list[DuplicateGroup] = []
    for group in groups:
        extras = tuple(
            member
            for member in group.extras
            if str(resolve_path(member.fingerprint.path)) not in protected
        )
        if not extras:
            continue
        out.append(
            DuplicateGroup(
                group_id=group.group_id,
                kind=group.kind,
                keeper=group.keeper,
                extras=extras,
                unique_transcript_at_risk=any(
                    member.unique_transcript_at_risk for member in extras
                ),
            )
        )
    return out


class DuplicateCleanupService:
    """Discover, preview, and delete duplicate recordings and transcripts."""

    def __init__(
        self,
        *,
        recordings_dir: Path | None = None,
        imports_dir: Path | None = None,
        audio_paths: Sequence[Path] | None = None,
        transcript_paths: Sequence[Path] | None = None,
        find_linked: Callable[[Path], list[Path]] | None = None,
        inventory_rows: Callable[[Sequence[Path]], dict[str, InventoryRow]] | None = None,
    ) -> None:
        self.recordings_dir = recordings_dir
        self.imports_dir = imports_dir
        self._audio_paths = audio_paths
        self._transcript_paths = transcript_paths
        self._find_linked = find_linked
        self._inventory_rows = inventory_rows or _inventory_rows

    def preview(self) -> DuplicatePreview:
        audio = (
            list(self._audio_paths)
            if self._audio_paths is not None
            else list_audio_files(
                self.recordings_dir, imports_dir=self.imports_dir
            )
        )
        transcripts = (
            list(self._transcript_paths)
            if self._transcript_paths is not None
            else list_transcript_files()
        )
        rows = self._inventory_rows(transcripts)
        groups, warnings = detect_duplicate_groups(
            audio_paths=audio,
            transcript_paths=transcripts,
            rows=rows,
            find_linked=self._find_linked,
        )
        groups = _strip_protected(groups, _protected_originals(groups))
        extra_count = sum(len(group.extras) for group in groups)
        size_estimate = sum(
            member.fingerprint.size
            for group in groups
            for member in group.extras
        )
        unique_warnings = sum(
            1 for group in groups if group.unique_transcript_at_risk
        )
        plan_id = _plan_id(groups)
        return DuplicatePreview(
            plan_id=plan_id,
            groups=tuple(groups),
            extra_count=extra_count,
            size_estimate_bytes=size_estimate,
            unique_transcript_warnings=unique_warnings,
            warnings=tuple(warnings),
            can_execute=extra_count > 0,
        )

    def execute(
        self, preview: DuplicatePreview, auth: DuplicateAuthorization
    ) -> DuplicateResult:
        return execute_preview(preview, auth)
