"""Folder scan + batch admit for local transcript inboxes."""

from __future__ import annotations

import os
import stat
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import TRANSCRIPTS_IMPORTS_DIR
from transcriptx.io.admit_and_register import (
    AdmitOutcome,
    AdmitOutcomeKind,
    admit_and_register,
)
from transcriptx.io.import_admission import (
    ADMISSION_POLICY_VERSION,
    AdmissionError,
    ManagedArtifactState,
    SCAN_HANDLE_SCHEMA_VERSION,
    assert_within_import_size_limit,
    derive_canonical_target,
    extension_is_supported,
    get_max_folder_import_candidates,
    get_max_import_file_bytes,
    inspect_managed_artifact_state,
    is_under_directory,
    normalize_conflict_stem,
    resolve_transcripts_root,
    sanitize_upload_basename,
)
from transcriptx.io.managed_import_workflow import StagingCleanupPolicy

logger = get_logger()


class CandidateStatus(str, Enum):
    NEW = "new"
    ALREADY_MANAGED = "already_managed"
    NEEDS_REGISTRATION = "needs_registration"
    INCOMPLETE_REPAIRABLE = "incomplete_repairable"
    INCOMPLETE_UNREPAIRABLE = "incomplete_unrepairable"
    INCONSISTENT = "inconsistent"
    STEM_CONFLICT = "stem_conflict"
    TOO_LARGE = "too_large"
    UNREADABLE = "unreadable"
    SYMLINK = "symlink"
    SPECIAL_FILE = "special_file"
    MANAGED_STORAGE = "managed_storage"


ELIGIBLE_STATUSES = frozenset(
    {
        CandidateStatus.NEW,
        CandidateStatus.INCOMPLETE_REPAIRABLE,
        CandidateStatus.NEEDS_REGISTRATION,
    }
)

# Short label + user help for Import Transcript preview (enum values unchanged).
STATUS_PRESENTATION: dict[CandidateStatus, tuple[str, str]] = {
    CandidateStatus.NEW: (
        "New",
        "Not in the library yet — eligible to import.",
    ),
    CandidateStatus.ALREADY_MANAGED: (
        "Already managed",
        "Canonical JSON + sidecar already exist — skip.",
    ),
    CandidateStatus.NEEDS_REGISTRATION: (
        "Needs registration",
        "Managed files exist but library registration is missing — eligible.",
    ),
    CandidateStatus.INCOMPLETE_REPAIRABLE: (
        "Incomplete (repairable)",
        "Partial managed state with safe provenance — eligible to repair.",
    ),
    CandidateStatus.INCOMPLETE_UNREPAIRABLE: (
        "Incomplete (blocked)",
        "Partial managed state without safe repair path — skip.",
    ),
    CandidateStatus.INCONSISTENT: (
        "Inconsistent",
        "Managed artifacts disagree — resolve manually before import.",
    ),
    CandidateStatus.STEM_CONFLICT: (
        "Stem conflict",
        "Multiple files share this stem — resolve duplicates first.",
    ),
    CandidateStatus.TOO_LARGE: (
        "Too large",
        "File exceeds the import size limit.",
    ),
    CandidateStatus.UNREADABLE: (
        "Unreadable",
        "Could not read or sanitize this file.",
    ),
    CandidateStatus.SYMLINK: (
        "Symlink",
        "Symlinks are not imported.",
    ),
    CandidateStatus.SPECIAL_FILE: (
        "Special file",
        "Non-regular files are not imported.",
    ),
    CandidateStatus.MANAGED_STORAGE: (
        "Managed storage",
        "Path resolves into managed transcripts storage — not an inbox.",
    ),
}


def status_label(status: CandidateStatus) -> str:
    label, _help = STATUS_PRESENTATION.get(status, (status.value, ""))
    return label


def status_help(status: CandidateStatus) -> str:
    _label, help_text = STATUS_PRESENTATION.get(status, (status.value, ""))
    return help_text


def is_eligible_status(status: CandidateStatus) -> bool:
    return status in ELIGIBLE_STATUSES


def same_stem_audio_hint(display_stem: str) -> str:
    """Read-only companion audio probe under approved recordings roots."""
    stem = (display_stem or "").strip()
    if not stem:
        return "none"
    try:
        from transcriptx.core.audio.types import SUPPORTED_AUDIO_EXTENSIONS
        from transcriptx.core.utils.rename.audio_association import (
            approved_recordings_roots,
        )
    except Exception:
        return "none"

    for root in approved_recordings_roots():
        try:
            if not root.exists():
                continue
        except OSError:
            continue
        for ext in sorted(SUPPORTED_AUDIO_EXTENSIONS):
            candidate = root / f"{stem}{ext}"
            try:
                if candidate.is_file():
                    return f"found: {candidate.name}"
            except OSError:
                continue
    return "none"


@dataclass(frozen=True)
class FolderImportCandidate:
    path: str
    basename: str
    display_stem: str
    conflict_key: str
    status: CandidateStatus
    secondary_detail: str = ""
    audio_hint: str = "none"
    st_dev: int | None = None
    st_ino: int | None = None
    size: int | None = None
    mtime_ns: int | None = None


@dataclass(frozen=True)
class ScanHandle:
    schema_version: int
    admission_policy_version: int
    resolved_folder: str
    resolved_transcripts_root: str
    max_file_bytes: int
    max_candidates: int
    scan_id: str
    scanned_at: str
    closed_ok: bool
    error: str | None
    candidates: tuple[FolderImportCandidate, ...]

    def to_session_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "admission_policy_version": self.admission_policy_version,
            "resolved_folder": self.resolved_folder,
            "resolved_transcripts_root": self.resolved_transcripts_root,
            "max_file_bytes": self.max_file_bytes,
            "max_candidates": self.max_candidates,
            "scan_id": self.scan_id,
            "scanned_at": self.scanned_at,
            "closed_ok": self.closed_ok,
            "error": self.error,
            # Persist status as the enum value string so session round-trips work.
            # asdict() leaves an Enum; str(CandidateStatus.NEW) is not a valid value.
            "candidates": [
                {**asdict(c), "status": c.status.value} for c in self.candidates
            ],
        }

    @staticmethod
    def from_session_dict(data: dict[str, Any] | None) -> ScanHandle | None:
        if not data or not isinstance(data, dict):
            return None
        try:
            raw_candidates = data.get("candidates") or []
            candidates = tuple(
                FolderImportCandidate(
                    path=str(c["path"]),
                    basename=str(c["basename"]),
                    display_stem=str(c["display_stem"]),
                    conflict_key=str(c["conflict_key"]),
                    status=_coerce_candidate_status(c["status"]),
                    secondary_detail=str(c.get("secondary_detail") or ""),
                    audio_hint=str(c.get("audio_hint") or "none"),
                    st_dev=c.get("st_dev"),
                    st_ino=c.get("st_ino"),
                    size=c.get("size"),
                    mtime_ns=c.get("mtime_ns"),
                )
                for c in raw_candidates
            )
            return ScanHandle(
                schema_version=int(data["schema_version"]),
                admission_policy_version=int(data["admission_policy_version"]),
                resolved_folder=str(data["resolved_folder"]),
                resolved_transcripts_root=str(data["resolved_transcripts_root"]),
                max_file_bytes=int(data["max_file_bytes"]),
                max_candidates=int(data["max_candidates"]),
                scan_id=str(data["scan_id"]),
                scanned_at=str(data["scanned_at"]),
                closed_ok=bool(data["closed_ok"]),
                error=data.get("error"),
                candidates=candidates,
            )
        except (KeyError, TypeError, ValueError):
            return None


def _coerce_candidate_status(raw: Any) -> CandidateStatus:
    if isinstance(raw, CandidateStatus):
        return raw
    return CandidateStatus(raw)


def resolve_absolute_directory(path_text: str) -> Path:
    """Require absolute, expanded, resolved directory; raise user-safe errors."""
    raw = (path_text or "").strip()
    if not raw:
        raise AdmissionError("Folder path is empty.")
    expanded = Path(raw).expanduser()
    if not expanded.is_absolute():
        raise AdmissionError(
            "Folder path must be absolute (for example /Users/you/transcripts-inbox)."
        )
    try:
        resolved = expanded.resolve(strict=False)
    except OSError as exc:
        raise AdmissionError(f"Folder path could not be resolved: {exc}") from exc
    try:
        if not resolved.exists():
            raise AdmissionError("Folder does not exist.")
        if not resolved.is_dir():
            raise AdmissionError("Path is not a directory.")
        # Verify readable by attempting to list.
        os.listdir(resolved)
    except PermissionError as exc:
        raise AdmissionError("Folder is not readable.") from exc
    except AdmissionError:
        raise
    except OSError as exc:
        raise AdmissionError(f"Folder is not accessible: {exc}") from exc
    return resolved


def _reject_managed_folder(folder: Path, transcripts_root: Path) -> None:
    if is_under_directory(folder, transcripts_root):
        raise AdmissionError(
            "Cannot import from the managed transcripts library (or a subdirectory "
            "such as originals/ or imports/). Choose an external inbox folder."
        )


def _open_nofollow_verify(
    path: Path,
    *,
    expected_dev: int | None,
    expected_ino: int | None,
    expected_size: int | None,
    expected_mtime_ns: int | None,
) -> tuple[int, bytes]:
    """Open without following symlinks; verify identity; return (fd closed after read) bytes."""
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(str(path), flags)
    except OSError as exc:
        raise AdmissionError(f"Could not open file safely: {exc}") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise AdmissionError("Path is not a regular file.")
        if expected_dev is not None and st.st_dev != expected_dev:
            raise AdmissionError("File identity changed since scan (device mismatch).")
        if expected_ino is not None and st.st_ino != expected_ino:
            raise AdmissionError("File identity changed since scan (inode mismatch).")
        if expected_size is not None and st.st_size != expected_size:
            raise AdmissionError("File size changed since scan.")
        mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))
        if expected_mtime_ns is not None and mtime_ns != expected_mtime_ns:
            raise AdmissionError("File modification time changed since scan.")
        with os.fdopen(fd, "rb") as handle:
            fd = -1  # ownership transferred
            return -1, handle.read()
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass


def _write_app_snapshot(basename: str, content: bytes) -> Path:
    imports_dir = Path(TRANSCRIPTS_IMPORTS_DIR)
    imports_dir.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_upload_basename(basename)
    dest = imports_dir / f"{uuid.uuid4().hex}_{safe_name}"
    dest.write_bytes(content)
    return dest


def scan_folder_for_import(
    path_text: str,
    *,
    transcripts_dir: str | Path | None = None,
) -> ScanHandle:
    """Scan a folder and return a versioned handle (closed_ok false on overflow/errors)."""
    scan_id = uuid.uuid4().hex
    scanned_at = datetime.now(timezone.utc).isoformat()
    max_bytes = get_max_import_file_bytes()
    max_candidates = get_max_folder_import_candidates()
    transcripts_root = resolve_transcripts_root(transcripts_dir)

    def _failed(folder: str, error: str) -> ScanHandle:
        return ScanHandle(
            schema_version=SCAN_HANDLE_SCHEMA_VERSION,
            admission_policy_version=ADMISSION_POLICY_VERSION,
            resolved_folder=folder,
            resolved_transcripts_root=str(transcripts_root),
            max_file_bytes=max_bytes,
            max_candidates=max_candidates,
            scan_id=scan_id,
            scanned_at=scanned_at,
            closed_ok=False,
            error=error,
            candidates=(),
        )

    try:
        folder = resolve_absolute_directory(path_text)
        _reject_managed_folder(folder, transcripts_root)
    except AdmissionError as exc:
        return _failed(str(path_text).strip(), str(exc))

    entries: list[tuple[Path, os.stat_result | None, CandidateStatus | None, str]] = []
    try:
        names = sorted(os.listdir(folder))
    except OSError as exc:
        return _failed(str(folder), f"Could not list folder: {exc}")

    supported_count = 0
    for name in names:
        path = folder / name
        try:
            st = os.lstat(path)
        except OSError as exc:
            if extension_is_supported(name):
                supported_count += 1
                entries.append((path, None, CandidateStatus.UNREADABLE, str(exc)))
            continue

        if not extension_is_supported(name):
            continue
        supported_count += 1
        if supported_count > max_candidates:
            return _failed(
                str(folder),
                f"Folder has more than {max_candidates} supported transcript files. "
                "Narrow the folder or raise TRANSCRIPTX_FOLDER_IMPORT_MAX_CANDIDATES.",
            )

        if stat.S_ISLNK(st.st_mode):
            entries.append(
                (path, st, CandidateStatus.SYMLINK, "Symlinks are not imported.")
            )
            continue
        if not stat.S_ISREG(st.st_mode):
            entries.append(
                (
                    path,
                    st,
                    CandidateStatus.SPECIAL_FILE,
                    "Special files are not imported.",
                )
            )
            continue
        try:
            resolved = path.resolve(strict=False)
        except OSError:
            resolved = path
        if is_under_directory(resolved, transcripts_root):
            entries.append(
                (
                    path,
                    st,
                    CandidateStatus.MANAGED_STORAGE,
                    "Resolved path enters managed transcripts storage.",
                )
            )
            continue
        entries.append((path, st, None, ""))

    # Build preliminary candidates, then apply stem conflicts across all members.
    prelim: list[FolderImportCandidate] = []
    for path, st, forced_status, forced_detail in entries:
        try:
            basename = sanitize_upload_basename(path.name)
            target = derive_canonical_target(basename, transcripts_dir=transcripts_root)
        except AdmissionError as exc:
            prelim.append(
                FolderImportCandidate(
                    path=str(path),
                    basename=path.name,
                    display_stem=Path(path.name).stem,
                    conflict_key=normalize_conflict_stem(Path(path.name).stem),
                    status=CandidateStatus.UNREADABLE,
                    secondary_detail=str(exc),
                    audio_hint=same_stem_audio_hint(Path(path.name).stem),
                    st_dev=getattr(st, "st_dev", None) if st else None,
                    st_ino=getattr(st, "st_ino", None) if st else None,
                    size=getattr(st, "st_size", None) if st else None,
                    mtime_ns=getattr(st, "st_mtime_ns", None) if st else None,
                )
            )
            continue

        status = forced_status
        secondary = forced_detail
        size = st.st_size if st is not None else None
        if status is None and size is not None:
            try:
                assert_within_import_size_limit(size, max_bytes=max_bytes)
            except AdmissionError as exc:
                status = CandidateStatus.TOO_LARGE
                secondary = str(exc)

        if status is None:
            inspection = inspect_managed_artifact_state(
                target.target_json, transcripts_dir=transcripts_root
            )
            if inspection.state is ManagedArtifactState.ALREADY_MANAGED:
                status = CandidateStatus.ALREADY_MANAGED
                try:
                    from transcriptx.core.utils.canonicalization import (
                        compute_transcript_identity_hash,
                    )
                    from transcriptx.core.utils.slug_manager import (
                        registration_is_valid,
                    )
                    import json as _json

                    with open(target.target_json, "r", encoding="utf-8") as handle:
                        doc = _json.load(handle)
                    segments = doc.get("segments") if isinstance(doc, dict) else None
                    if isinstance(segments, list) and segments:
                        identity = compute_transcript_identity_hash(segments)
                        if not registration_is_valid(target.target_json, identity):
                            status = CandidateStatus.NEEDS_REGISTRATION
                            secondary = (
                                "Managed artifacts exist but registration is missing."
                            )
                except Exception:
                    # Keep already_managed; admit will re-inspect.
                    pass
            elif inspection.state is ManagedArtifactState.INCOMPLETE_REPAIRABLE:
                status = CandidateStatus.INCOMPLETE_REPAIRABLE
                secondary = inspection.detail
            elif inspection.state is ManagedArtifactState.INCOMPLETE_UNREPAIRABLE:
                status = CandidateStatus.INCOMPLETE_UNREPAIRABLE
                secondary = inspection.detail
            elif inspection.state is ManagedArtifactState.INCONSISTENT:
                status = CandidateStatus.INCONSISTENT
                secondary = inspection.detail
            else:
                status = CandidateStatus.NEW

        mtime_ns = None
        if st is not None:
            mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))
        prelim.append(
            FolderImportCandidate(
                path=str(path),
                basename=basename,
                display_stem=target.display_stem,
                conflict_key=target.conflict_key,
                status=status,
                secondary_detail=secondary,
                audio_hint=same_stem_audio_hint(target.display_stem),
                st_dev=st.st_dev if st is not None else None,
                st_ino=st.st_ino if st is not None else None,
                size=size,
                mtime_ns=mtime_ns,
            )
        )

    by_stem: dict[str, list[int]] = {}
    for idx, cand in enumerate(prelim):
        by_stem.setdefault(cand.conflict_key, []).append(idx)

    final: list[FolderImportCandidate] = list(prelim)
    for key, idxs in by_stem.items():
        if len(idxs) < 2:
            continue
        for idx in idxs:
            old = final[idx]
            secondary = old.secondary_detail
            if old.status not in {
                CandidateStatus.STEM_CONFLICT,
                CandidateStatus.NEW,
                CandidateStatus.ALREADY_MANAGED,
                CandidateStatus.NEEDS_REGISTRATION,
                CandidateStatus.INCOMPLETE_REPAIRABLE,
            }:
                # Preserve secondary failure while promoting primary to stem_conflict.
                if not secondary:
                    secondary = old.status.value
            final[idx] = FolderImportCandidate(
                path=old.path,
                basename=old.basename,
                display_stem=old.display_stem,
                conflict_key=old.conflict_key,
                status=CandidateStatus.STEM_CONFLICT,
                secondary_detail=secondary,
                audio_hint=old.audio_hint,
                st_dev=old.st_dev,
                st_ino=old.st_ino,
                size=old.size,
                mtime_ns=old.mtime_ns,
            )

    return ScanHandle(
        schema_version=SCAN_HANDLE_SCHEMA_VERSION,
        admission_policy_version=ADMISSION_POLICY_VERSION,
        resolved_folder=str(folder),
        resolved_transcripts_root=str(transcripts_root),
        max_file_bytes=max_bytes,
        max_candidates=max_candidates,
        scan_id=scan_id,
        scanned_at=scanned_at,
        closed_ok=True,
        error=None,
        candidates=tuple(final),
    )


def scan_handle_still_valid(
    handle: ScanHandle | None,
    *,
    path_input: str,
    transcripts_dir: str | Path | None = None,
) -> bool:
    if handle is None or not handle.closed_ok:
        return False
    if handle.schema_version != SCAN_HANDLE_SCHEMA_VERSION:
        return False
    if handle.admission_policy_version != ADMISSION_POLICY_VERSION:
        return False
    try:
        folder = resolve_absolute_directory(path_input)
        transcripts_root = resolve_transcripts_root(transcripts_dir)
    except AdmissionError:
        return False
    if str(folder) != handle.resolved_folder:
        return False
    if str(transcripts_root) != handle.resolved_transcripts_root:
        return False
    if handle.max_file_bytes != get_max_import_file_bytes():
        return False
    if handle.max_candidates != get_max_folder_import_candidates():
        return False
    return True


def eligible_candidates(handle: ScanHandle) -> list[FolderImportCandidate]:
    return [c for c in handle.candidates if c.status in ELIGIBLE_STATUSES]


def classify_inbox_file(
    path: Path | str,
    *,
    transcripts_dir: str | Path | None = None,
    expected_dev: int | None = None,
    expected_ino: int | None = None,
    expected_size: int | None = None,
    expected_mtime_ns: int | None = None,
) -> FolderImportCandidate:
    """Classify a single inbox path using the same rules as folder scan."""
    path = Path(path)
    transcripts_root = resolve_transcripts_root(transcripts_dir)
    max_bytes = get_max_import_file_bytes()

    try:
        st = os.lstat(path)
    except OSError as exc:
        return FolderImportCandidate(
            path=str(path),
            basename=path.name,
            display_stem=path.stem,
            conflict_key=normalize_conflict_stem(path.stem),
            status=CandidateStatus.UNREADABLE,
            secondary_detail=str(exc),
        )

    if not extension_is_supported(path.name):
        return FolderImportCandidate(
            path=str(path),
            basename=path.name,
            display_stem=path.stem,
            conflict_key=normalize_conflict_stem(path.stem),
            status=CandidateStatus.UNREADABLE,
            secondary_detail="Unsupported extension for transcript import.",
            st_dev=st.st_dev,
            st_ino=st.st_ino,
            size=st.st_size,
            mtime_ns=getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)),
        )

    if stat.S_ISLNK(st.st_mode):
        return FolderImportCandidate(
            path=str(path),
            basename=path.name,
            display_stem=path.stem,
            conflict_key=normalize_conflict_stem(path.stem),
            status=CandidateStatus.SYMLINK,
            secondary_detail="Symlinks are not imported.",
            st_dev=st.st_dev,
            st_ino=st.st_ino,
            size=st.st_size,
            mtime_ns=getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)),
        )
    if not stat.S_ISREG(st.st_mode):
        return FolderImportCandidate(
            path=str(path),
            basename=path.name,
            display_stem=path.stem,
            conflict_key=normalize_conflict_stem(path.stem),
            status=CandidateStatus.SPECIAL_FILE,
            secondary_detail="Special files are not imported.",
            st_dev=st.st_dev,
            st_ino=st.st_ino,
            size=st.st_size,
            mtime_ns=getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)),
        )

    if expected_dev is not None and st.st_dev != expected_dev:
        return FolderImportCandidate(
            path=str(path),
            basename=path.name,
            display_stem=path.stem,
            conflict_key=normalize_conflict_stem(path.stem),
            status=CandidateStatus.UNREADABLE,
            secondary_detail="File identity changed since detection (device mismatch).",
            st_dev=st.st_dev,
            st_ino=st.st_ino,
            size=st.st_size,
            mtime_ns=getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)),
        )
    if expected_ino is not None and st.st_ino != expected_ino:
        return FolderImportCandidate(
            path=str(path),
            basename=path.name,
            display_stem=path.stem,
            conflict_key=normalize_conflict_stem(path.stem),
            status=CandidateStatus.UNREADABLE,
            secondary_detail="File identity changed since detection (inode mismatch).",
            st_dev=st.st_dev,
            st_ino=st.st_ino,
            size=st.st_size,
            mtime_ns=getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)),
        )
    if expected_size is not None and st.st_size != expected_size:
        return FolderImportCandidate(
            path=str(path),
            basename=path.name,
            display_stem=path.stem,
            conflict_key=normalize_conflict_stem(path.stem),
            status=CandidateStatus.UNREADABLE,
            secondary_detail="File size changed since detection.",
            st_dev=st.st_dev,
            st_ino=st.st_ino,
            size=st.st_size,
            mtime_ns=getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)),
        )
    mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))
    if expected_mtime_ns is not None and mtime_ns != expected_mtime_ns:
        return FolderImportCandidate(
            path=str(path),
            basename=path.name,
            display_stem=path.stem,
            conflict_key=normalize_conflict_stem(path.stem),
            status=CandidateStatus.UNREADABLE,
            secondary_detail="File modification time changed since detection.",
            st_dev=st.st_dev,
            st_ino=st.st_ino,
            size=st.st_size,
            mtime_ns=mtime_ns,
        )

    try:
        resolved = path.resolve(strict=False)
    except OSError:
        resolved = path
    if is_under_directory(resolved, transcripts_root):
        return FolderImportCandidate(
            path=str(path),
            basename=path.name,
            display_stem=path.stem,
            conflict_key=normalize_conflict_stem(path.stem),
            status=CandidateStatus.MANAGED_STORAGE,
            secondary_detail="Resolved path enters managed transcripts storage.",
            st_dev=st.st_dev,
            st_ino=st.st_ino,
            size=st.st_size,
            mtime_ns=mtime_ns,
        )

    try:
        basename = sanitize_upload_basename(path.name)
        target = derive_canonical_target(basename, transcripts_dir=transcripts_root)
    except AdmissionError as exc:
        return FolderImportCandidate(
            path=str(path),
            basename=path.name,
            display_stem=path.stem,
            conflict_key=normalize_conflict_stem(path.stem),
            status=CandidateStatus.UNREADABLE,
            secondary_detail=str(exc),
            st_dev=st.st_dev,
            st_ino=st.st_ino,
            size=st.st_size,
            mtime_ns=mtime_ns,
        )

    status: CandidateStatus | None = None
    secondary = ""
    try:
        assert_within_import_size_limit(st.st_size, max_bytes=max_bytes)
    except AdmissionError as exc:
        status = CandidateStatus.TOO_LARGE
        secondary = str(exc)

    if status is None:
        inspection = inspect_managed_artifact_state(
            target.target_json, transcripts_dir=transcripts_root
        )
        if inspection.state is ManagedArtifactState.ALREADY_MANAGED:
            status = CandidateStatus.ALREADY_MANAGED
            try:
                from transcriptx.core.utils.canonicalization import (
                    compute_transcript_identity_hash,
                )
                from transcriptx.core.utils.slug_manager import registration_is_valid
                import json as _json

                with open(target.target_json, "r", encoding="utf-8") as handle:
                    doc = _json.load(handle)
                segments = doc.get("segments") if isinstance(doc, dict) else None
                if isinstance(segments, list) and segments:
                    identity = compute_transcript_identity_hash(segments)
                    if not registration_is_valid(target.target_json, identity):
                        status = CandidateStatus.NEEDS_REGISTRATION
                        secondary = (
                            "Managed artifacts exist but registration is missing."
                        )
            except Exception:
                pass
        elif inspection.state is ManagedArtifactState.INCOMPLETE_REPAIRABLE:
            status = CandidateStatus.INCOMPLETE_REPAIRABLE
            secondary = inspection.detail
        elif inspection.state is ManagedArtifactState.INCOMPLETE_UNREPAIRABLE:
            status = CandidateStatus.INCOMPLETE_UNREPAIRABLE
            secondary = inspection.detail
        elif inspection.state is ManagedArtifactState.INCONSISTENT:
            status = CandidateStatus.INCONSISTENT
            secondary = inspection.detail
        else:
            status = CandidateStatus.NEW

    return FolderImportCandidate(
        path=str(path),
        basename=basename,
        display_stem=target.display_stem,
        conflict_key=target.conflict_key,
        status=status,
        secondary_detail=secondary,
        st_dev=st.st_dev,
        st_ino=st.st_ino,
        size=st.st_size,
        mtime_ns=mtime_ns,
    )


def admit_inbox_candidate(cand: FolderImportCandidate) -> AdmitOutcome:
    """Admit one classified inbox candidate (copy snapshot → admit_and_register)."""
    if cand.status not in ELIGIBLE_STATUSES:
        return AdmitOutcome(
            kind=AdmitOutcomeKind.UNSUPPORTED_OR_INVALID_INPUT,
            transcript_path=None,
            slug=None,
            artifact_committed=False,
            registration_progressed=False,
            user_safe_detail=f"{cand.basename}: status {cand.status.value} is not eligible.",
        )

    path = Path(cand.path)
    snapshot: Path | None = None
    try:
        _fd, content = _open_nofollow_verify(
            path,
            expected_dev=cand.st_dev,
            expected_ino=cand.st_ino,
            expected_size=cand.size,
            expected_mtime_ns=cand.mtime_ns,
        )
        assert_within_import_size_limit(len(content))
        snapshot = _write_app_snapshot(cand.basename, content)
        outcome = admit_and_register(
            snapshot,
            logical_basename=cand.basename,
            staging_cleanup=StagingCleanupPolicy.APP_IMPORTS_ONLY,
            allow_provenance_backfill=False,
            expected_size=len(content),
        )
        return AdmitOutcome(
            kind=outcome.kind,
            transcript_path=outcome.transcript_path,
            slug=outcome.slug,
            artifact_committed=outcome.artifact_committed,
            registration_progressed=outcome.registration_progressed,
            user_safe_detail=f"{cand.basename}: {outcome.user_safe_detail}",
        )
    except AdmissionError as exc:
        if snapshot is not None:
            try:
                snapshot.unlink(missing_ok=True)
            except OSError:
                pass
        return AdmitOutcome(
            kind=AdmitOutcomeKind.STALE_CANDIDATE,
            transcript_path=None,
            slug=None,
            artifact_committed=False,
            registration_progressed=False,
            user_safe_detail=f"{cand.basename}: {exc}",
        )
    except Exception as exc:
        logger.exception("Inbox admit failed for %s", cand.path)
        if snapshot is not None:
            try:
                snapshot.unlink(missing_ok=True)
            except OSError:
                pass
        return AdmitOutcome(
            kind=AdmitOutcomeKind.UNEXPECTED_FAILURE,
            transcript_path=None,
            slug=None,
            artifact_committed=False,
            registration_progressed=False,
            user_safe_detail=f"{cand.basename}: Unexpected failure: {exc}",
        )


def import_folder_candidates(
    handle: ScanHandle,
    *,
    path_input: str,
    only: Iterable[FolderImportCandidate] | None = None,
) -> list[AdmitOutcome]:
    """Revalidate and admit previewed eligible candidates sequentially."""
    if not scan_handle_still_valid(handle, path_input=path_input):
        return [
            AdmitOutcome(
                kind=AdmitOutcomeKind.STALE_CANDIDATE,
                transcript_path=None,
                slug=None,
                artifact_committed=False,
                registration_progressed=False,
                user_safe_detail="Scan preview is no longer valid. Scan the folder again.",
            )
        ]

    targets = list(only) if only is not None else eligible_candidates(handle)
    # Never admit files absent from the handle.
    handle_paths = {c.path for c in handle.candidates}
    outcomes: list[AdmitOutcome] = []

    for cand in targets:
        if cand.path not in handle_paths:
            outcomes.append(
                AdmitOutcome(
                    kind=AdmitOutcomeKind.STALE_CANDIDATE,
                    transcript_path=None,
                    slug=None,
                    artifact_committed=False,
                    registration_progressed=False,
                    user_safe_detail=f"{cand.basename}: not part of the current scan.",
                )
            )
            continue
        if cand.status not in ELIGIBLE_STATUSES:
            outcomes.append(
                AdmitOutcome(
                    kind=AdmitOutcomeKind.UNSUPPORTED_OR_INVALID_INPUT,
                    transcript_path=None,
                    slug=None,
                    artifact_committed=False,
                    registration_progressed=False,
                    user_safe_detail=f"{cand.basename}: status {cand.status.value} is not eligible.",
                )
            )
            continue

        path = Path(cand.path)
        snapshot: Path | None = None
        try:
            _fd, content = _open_nofollow_verify(
                path,
                expected_dev=cand.st_dev,
                expected_ino=cand.st_ino,
                expected_size=cand.size,
                expected_mtime_ns=cand.mtime_ns,
            )
            assert_within_import_size_limit(
                len(content), max_bytes=handle.max_file_bytes
            )
            snapshot = _write_app_snapshot(cand.basename, content)
            outcome = admit_and_register(
                snapshot,
                logical_basename=cand.basename,
                staging_cleanup=StagingCleanupPolicy.APP_IMPORTS_ONLY,
                allow_provenance_backfill=False,
                expected_size=len(content),
            )
            # Enrich detail with basename for batch UI.
            outcomes.append(
                AdmitOutcome(
                    kind=outcome.kind,
                    transcript_path=outcome.transcript_path,
                    slug=outcome.slug,
                    artifact_committed=outcome.artifact_committed,
                    registration_progressed=outcome.registration_progressed,
                    user_safe_detail=f"{cand.basename}: {outcome.user_safe_detail}",
                )
            )
        except AdmissionError as exc:
            outcomes.append(
                AdmitOutcome(
                    kind=AdmitOutcomeKind.STALE_CANDIDATE,
                    transcript_path=None,
                    slug=None,
                    artifact_committed=False,
                    registration_progressed=False,
                    user_safe_detail=f"{cand.basename}: {exc}",
                )
            )
            if snapshot is not None:
                try:
                    snapshot.unlink(missing_ok=True)
                except OSError:
                    pass
        except Exception as exc:
            logger.exception("Folder import failed for %s", cand.path)
            outcomes.append(
                AdmitOutcome(
                    kind=AdmitOutcomeKind.UNEXPECTED_FAILURE,
                    transcript_path=None,
                    slug=None,
                    artifact_committed=False,
                    registration_progressed=False,
                    user_safe_detail=f"{cand.basename}: Unexpected failure: {exc}",
                )
            )
            if snapshot is not None:
                try:
                    snapshot.unlink(missing_ok=True)
                except OSError:
                    pass
    return outcomes
