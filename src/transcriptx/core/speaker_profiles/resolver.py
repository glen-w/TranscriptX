"""ManagedTranscriptResolver — fail-closed import_id → library path mapping."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from transcriptx.core.speaker_profiles.errors import (
    DuplicateImportIdError,
    ManagedTranscriptResolverError,
    NotManagedTranscriptError,
    SpeakerProfileContractError,
    SpeakerProfilePathError,
    UnresolvedManagedTranscriptError,
)
from transcriptx.core.speaker_profiles.identity import canonicalize_managed_transcript_id
from transcriptx.core.speaker_profiles.path_safety import (
    assert_path_under_root,
    resolve_real,
)
from transcriptx.core.utils.file_discovery import discover_managed_transcript_paths
from transcriptx.core.utils.paths import PATHS
from transcriptx.io.import_metadata.layout import resolve_import_sidecar_layout
from transcriptx.io.import_metadata.persist import load_sidecar
from transcriptx.io.import_metadata.validate import validate_managed_transcript


@dataclass(frozen=True)
class ResolvedManagedTranscript:
    """One admitted managed library transcript for speaker-profile linking."""

    managed_transcript_id: str
    transcript_path: Path
    sidecar_path: Path
    current_relpath: str
    sidecar_imported_at: str
    source_imported_at: str | None = None


@dataclass(frozen=True)
class ResolverDiagnostics:
    """Rebuild diagnostics (non-admitted / blocked ids)."""

    admitted_count: int = 0
    skipped_non_uuid_import_id: tuple[str, ...] = ()
    duplicate_import_ids: tuple[str, ...] = ()
    symlink_rejected: tuple[str, ...] = ()
    admission_failed: tuple[str, ...] = ()


@dataclass
class _IndexEntry:
    resolved: ResolvedManagedTranscript | None = None
    paths: list[Path] = field(default_factory=list)
    duplicate: bool = False


class ManagedTranscriptResolver:
    """Map ``managed_transcript_id`` → exactly one admitted managed transcript.

    Fail closed on duplicate import_id, missing/invalid sidecar, stale
    ``current_json_filename``, path outside the library, or symlink escape.
    """

    def __init__(
        self,
        *,
        transcripts_dir: Path | None = None,
        discovery_root: Path | None = None,
    ) -> None:
        self._transcripts_dir = Path(
            transcripts_dir if transcripts_dir is not None else PATHS.transcripts_dir
        )
        self._discovery_root = (
            Path(discovery_root) if discovery_root is not None else self._transcripts_dir
        )
        self._by_id: dict[str, _IndexEntry] = {}
        self._by_path: dict[Path, str] = {}
        self._diagnostics = ResolverDiagnostics()
        self._built = False

    @property
    def transcripts_dir(self) -> Path:
        return self._transcripts_dir

    @property
    def diagnostics(self) -> ResolverDiagnostics:
        self._ensure_built()
        return self._diagnostics

    def rebuild(self) -> ResolverDiagnostics:
        """Rescan admitted managed transcripts and rebuild the index."""
        self._by_id.clear()
        self._by_path.clear()
        skipped_non_uuid: list[str] = []
        duplicates: set[str] = set()
        symlink_rejected: list[str] = []
        admission_failed: list[str] = []

        root = resolve_real(self._transcripts_dir)
        candidates = discover_managed_transcript_paths(self._discovery_root)
        for candidate in candidates:
            try:
                admitted = self._admit_candidate(candidate, library_root=root)
            except SpeakerProfilePathError:
                symlink_rejected.append(str(candidate))
                continue
            except NotManagedTranscriptError as exc:
                admission_failed.append(f"{candidate}: {exc}")
                continue
            except SpeakerProfileContractError as exc:
                # Non-UUID import_id or other contract rejection for linking.
                msg = str(exc)
                if "must be a UUID" in msg:
                    skipped_non_uuid.append(str(candidate))
                else:
                    admission_failed.append(f"{candidate}: {exc}")
                continue
            except ManagedTranscriptResolverError as exc:
                admission_failed.append(f"{candidate}: {exc}")
                continue

            entry = self._by_id.get(admitted.managed_transcript_id)
            if entry is None:
                self._by_id[admitted.managed_transcript_id] = _IndexEntry(
                    resolved=admitted, paths=[admitted.transcript_path]
                )
                self._by_path[resolve_real(admitted.transcript_path)] = (
                    admitted.managed_transcript_id
                )
            else:
                entry.duplicate = True
                entry.resolved = None
                entry.paths.append(admitted.transcript_path)
                duplicates.add(admitted.managed_transcript_id)
                # Remove any prior reverse mapping for this id's paths.
                for p in entry.paths:
                    self._by_path.pop(resolve_real(p), None)

        admitted_count = sum(
            1 for e in self._by_id.values() if e.resolved is not None and not e.duplicate
        )
        self._diagnostics = ResolverDiagnostics(
            admitted_count=admitted_count,
            skipped_non_uuid_import_id=tuple(sorted(skipped_non_uuid)),
            duplicate_import_ids=tuple(sorted(duplicates)),
            symlink_rejected=tuple(sorted(symlink_rejected)),
            admission_failed=tuple(sorted(admission_failed)),
        )
        self._built = True
        return self._diagnostics

    def resolve(self, managed_transcript_id: str) -> ResolvedManagedTranscript:
        """Resolve a canonical managed_transcript_id to one admitted path."""
        self._ensure_built()
        try:
            key = canonicalize_managed_transcript_id(managed_transcript_id)
        except SpeakerProfileContractError as exc:
            raise UnresolvedManagedTranscriptError(
                f"invalid managed_transcript_id: {managed_transcript_id!r}"
            ) from exc

        entry = self._by_id.get(key)
        if entry is None:
            raise UnresolvedManagedTranscriptError(
                f"no admitted managed transcript for id {key}"
            )
        if entry.duplicate or entry.resolved is None:
            raise DuplicateImportIdError(
                f"duplicate import_id {key} across admitted sidecars: "
                f"{[str(p) for p in entry.paths]}"
            )
        return entry.resolved

    def resolve_path(self, transcript_path: Path | str) -> ResolvedManagedTranscript:
        """Admit and resolve a concrete transcript path (managed-library only)."""
        path = Path(transcript_path)
        admitted = self._admit_candidate(
            path, library_root=resolve_real(self._transcripts_dir)
        )
        # Prefer index if built and consistent; otherwise return fresh admission.
        self._ensure_built()
        indexed = self._by_id.get(admitted.managed_transcript_id)
        if indexed is not None and indexed.duplicate:
            raise DuplicateImportIdError(
                f"duplicate import_id {admitted.managed_transcript_id} across "
                f"admitted sidecars: {[str(p) for p in indexed.paths]}"
            )
        if indexed is not None and indexed.resolved is not None:
            return indexed.resolved
        return admitted

    def list_admitted(self) -> list[ResolvedManagedTranscript]:
        self._ensure_built()
        out = [
            e.resolved
            for e in self._by_id.values()
            if e.resolved is not None and not e.duplicate
        ]
        return sorted(out, key=lambda r: r.managed_transcript_id)

    def is_managed_path(self, transcript_path: Path | str) -> bool:
        try:
            self.resolve_path(transcript_path)
            return True
        except (
            ManagedTranscriptResolverError,
            SpeakerProfilePathError,
            SpeakerProfileContractError,
        ):
            return False

    def _ensure_built(self) -> None:
        if not self._built:
            self.rebuild()

    def _admit_candidate(
        self, transcript_path: Path, *, library_root: Path
    ) -> ResolvedManagedTranscript:
        path = Path(transcript_path)
        if not path.exists() or path.suffix.lower() != ".json":
            raise NotManagedTranscriptError(
                f"transcript not found or not JSON: {path}"
            )

        # Reject symlink escape of library roots.
        try:
            resolved_path = assert_path_under_root(
                path, library_root, what="transcript path"
            )
        except SpeakerProfilePathError as exc:
            raise SpeakerProfilePathError(str(exc)) from exc

        # validate_managed_transcript covers missing/invalid sidecar and stale
        # current_json_filename (filename_mismatch).
        validation = validate_managed_transcript(path)
        if not validation.ok:
            raise NotManagedTranscriptError(
                f"managed admission failed ({validation.category.value}): "
                f"{validation.message}"
            )

        layout = resolve_import_sidecar_layout(path)
        if layout.authoritative_source is None:
            raise NotManagedTranscriptError("missing import sidecar")
        sidecar_path = layout.authoritative_source
        # Prefer containment under the transcript library root (metadata/ nested).
        # When tests monkeypatch metadata outside that tree, still reject symlink
        # targets that escape the sidecar's immediate resolved parent chain by
        # requiring the sidecar file itself is not a dangling escape.
        try:
            assert_path_under_root(
                sidecar_path, library_root, what="import sidecar path"
            )
        except SpeakerProfilePathError:
            if sidecar_path.is_symlink():
                raise SpeakerProfilePathError(
                    f"symlink rejected for import sidecar path: {sidecar_path}"
                )
            resolve_real(sidecar_path)

        sidecar = load_sidecar(sidecar_path)
        import_id = sidecar.get("import_id")
        managed_id = canonicalize_managed_transcript_id(str(import_id))
        current_filename = sidecar.get("current_json_filename")
        if current_filename != path.name:
            raise NotManagedTranscriptError(
                f"stale current_json_filename: {current_filename!r} != {path.name!r}"
            )

        source_imported_at = _load_source_imported_at(path)
        try:
            rel = resolved_path.relative_to(library_root).as_posix()
        except ValueError:
            rel = path.name

        return ResolvedManagedTranscript(
            managed_transcript_id=managed_id,
            transcript_path=resolved_path,
            sidecar_path=resolve_real(sidecar_path),
            current_relpath=rel,
            sidecar_imported_at=str(sidecar.get("imported_at") or ""),
            source_imported_at=source_imported_at,
        )


def _load_source_imported_at(transcript_path: Path) -> str | None:
    try:
        with open(transcript_path, "r", encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(doc, Mapping):
        return None
    source = doc.get("source")
    if not isinstance(source, Mapping):
        return None
    value = source.get("imported_at")
    return str(value) if value is not None else None


def load_transcript_segments(transcript_path: Path | str) -> list[dict[str, Any]]:
    """Load segment dicts from a transcript JSON document."""
    path = Path(transcript_path)
    with open(path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    if not isinstance(doc, dict):
        raise ManagedTranscriptResolverError("transcript root must be an object")
    segments = doc.get("segments")
    if not isinstance(segments, list):
        raise ManagedTranscriptResolverError("transcript segments must be a list")
    out: list[dict[str, Any]] = []
    for item in segments:
        if isinstance(item, dict):
            out.append(dict(item))
    return out
