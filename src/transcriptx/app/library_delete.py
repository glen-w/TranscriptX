"""Delete one managed library transcript and its companions.

User-initiated (Library inspector). Never auto-runs. Linked recordings and
analysis run folders are left in place — same companion set as duplicate
cleanup extras, without touching the recordings library.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from transcriptx.app.duplicate_cleanup.execute import (
    count_speaker_links_for_import_ids,
    import_id_for_transcript,
    tidy_group_membership,
)
from transcriptx.core.audio.linked_transcripts import (
    companion_files_for_transcript,
    drop_processing_state_for_transcripts,
)
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR
from transcriptx.core.utils.slug_manager import unregister_source_path
from transcriptx.io.import_admission import is_under_directory

logger = get_logger()

_DERIVED_REL_ROOTS = frozenset({"metadata", "originals", "readable", "imports"})
_SIDECAR_NAME_SUFFIXES = (
    ".speaker_map.json",
    ".import_meta.json",
    "_speaker_map.json",
    "_summary.json",
    "_manifest.json",
)


@dataclass(frozen=True)
class LibraryDeleteResult:
    ok: bool
    transcript_deleted: bool = False
    companions_deleted: int = 0
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    emptied_groups: tuple[str, ...] = ()
    dangling_speaker_links: int = 0


def is_managed_library_transcript(path: Path) -> bool:
    """True when *path* is a library transcript JSON, not a sidecar or derived copy."""
    try:
        candidate = path.expanduser()
        if candidate.suffix.lower() != ".json":
            return False
        if not candidate.is_file():
            return False
        resolved = candidate.resolve()
        root = Path(DIARISED_TRANSCRIPTS_DIR).expanduser().resolve()
    except OSError:
        return False
    if not is_under_directory(resolved, root) or resolved == root:
        return False
    try:
        rel = resolved.relative_to(root)
    except ValueError:
        return False
    if not rel.parts or rel.parts[0] in _DERIVED_REL_ROOTS:
        return False
    name = resolved.name
    return not any(name.endswith(suffix) for suffix in _SIDECAR_NAME_SUFFIXES)


def delete_managed_library_transcript(path: Path) -> LibraryDeleteResult:
    """Delete one managed transcript JSON plus companions; keep recordings and runs."""
    transcript = Path(path)
    if not is_managed_library_transcript(transcript):
        return LibraryDeleteResult(
            ok=False,
            errors=(
                "This file is not a managed library transcript and cannot be deleted here.",
            ),
        )

    warnings: list[str] = []
    companions_deleted = 0
    json_deleted = False
    try:
        resolved = transcript.expanduser().resolve()
    except OSError:
        resolved = transcript

    import_id = import_id_for_transcript(resolved)
    companions = companion_files_for_transcript(resolved)
    for companion in companions:
        if _unlink(companion, warnings):
            companions_deleted += 1
            try:
                if companion.resolve() == resolved:
                    json_deleted = True
            except OSError:
                if companion == resolved:
                    json_deleted = True
    companions_deleted += _delete_corrections(resolved, warnings)

    if not json_deleted and resolved.exists():
        return LibraryDeleteResult(
            ok=False,
            companions_deleted=companions_deleted,
            errors=(f"Could not delete {resolved.name}.",),
            warnings=tuple(warnings),
        )

    try:
        unregister_source_path(resolved)
    except Exception as exc:
        warnings.append(f"Could not unregister {resolved.name} from slug index: {exc}")

    try:
        drop_processing_state_for_transcripts([resolved])
    except Exception as exc:
        warnings.append(f"Could not update processing state: {exc}")

    try:
        deleted_key = str(resolved)
        emptied, group_warnings = tidy_group_membership({deleted_key})
        warnings.extend(group_warnings)
    except Exception as exc:
        emptied = ()
        warnings.append(f"Could not update groups: {exc}")

    dangling = 0
    if import_id:
        try:
            dangling = count_speaker_links_for_import_ids({import_id})
        except Exception as exc:
            warnings.append(f"Could not check speaker-profile links: {exc}")

    logger.info("Deleted managed library transcript: %s", resolved)
    return LibraryDeleteResult(
        ok=True,
        transcript_deleted=True,
        companions_deleted=companions_deleted,
        warnings=tuple(warnings),
        emptied_groups=tuple(emptied),
        dangling_speaker_links=dangling,
    )


def _unlink(path: Path, warnings: list[str]) -> bool:
    try:
        path.unlink()
        logger.info("Deleted library transcript artifact: %s", path)
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        warnings.append(f"Could not delete {path.name}: {exc}")
        return False


def _delete_corrections(transcript: Path, warnings: list[str]) -> int:
    try:
        from transcriptx.core.store.corrections_session_store import (
            session_path_for_transcript,
        )
    except Exception:
        return 0
    try:
        session = session_path_for_transcript(transcript)
    except Exception:
        return 0
    if session.is_file():
        try:
            session.unlink()
            return 1
        except OSError as exc:
            warnings.append(f"Could not delete corrections session {session}: {exc}")
    return 0
