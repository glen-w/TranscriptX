"""Delete extra duplicate library files after fingerprint re-check."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.app.corpus_inventory.service import import_sidecar_candidates
from transcriptx.app.duplicate_cleanup.models import (
    DuplicateAuthorization,
    DuplicatePreview,
    DuplicateResult,
    FileFingerprint,
    MemberRole,
    authorization_is_valid,
)
from transcriptx.app.duplicate_cleanup.scan import fingerprint_file, resolve_path
from transcriptx.core.audio.linked_transcripts import (
    companion_files_for_transcript,
    drop_processing_state_for_transcripts,
)
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.slug_manager import unregister_source_path

logger = get_logger()


def _path_key(path: Path) -> str:
    return str(resolve_path(path))


def fingerprint_matches(expected: FileFingerprint) -> bool:
    current = fingerprint_file(expected.path)
    if current is None:
        return False
    return (
        current.size == expected.size
        and current.mtime_ns == expected.mtime_ns
        and current.sha256 == expected.sha256
    )


def import_id_for_transcript(transcript: Path) -> str | None:
    for candidate in import_sidecar_candidates(transcript):
        if not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        value = payload.get("import_id")
        if value:
            return str(value)
    return None


def archived_original_path(transcript: Path) -> Path | None:
    from transcriptx.core.utils.paths import PATHS

    for candidate in import_sidecar_candidates(transcript):
        if not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        rel = payload.get("archived_original_relpath")
        if not rel:
            continue
        path = Path(str(rel))
        if not path.is_absolute():
            path = PATHS.transcripts_dir / path
        if path.is_file():
            return resolve_path(path)
    return None


def _delete_corrections(transcript: Path, warnings: list[str]) -> int:
    deleted = 0
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
            deleted += 1
        except OSError as exc:
            warnings.append(f"Could not delete corrections session {session}: {exc}")
    return deleted


def _unlink(path: Path, warnings: list[str]) -> bool:
    try:
        path.unlink()
        logger.info("Deleted duplicate library file: %s", path)
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        warnings.append(f"Could not delete {path.name}: {exc}")
        return False


def count_speaker_links_for_import_ids(import_ids: set[str]) -> int:
    if not import_ids:
        return 0
    try:
        from transcriptx.core.speaker_profiles.identity import (
            canonicalize_managed_transcript_id,
        )
        from transcriptx.core.speaker_profiles.layout import links_dir
    except Exception:
        return 0
    canonical: set[str] = set()
    for value in import_ids:
        try:
            canonical.add(canonicalize_managed_transcript_id(value))
        except Exception:
            canonical.add(value)
    try:
        root = links_dir()
    except Exception:
        return 0
    if not root.is_dir():
        return 0
    count = 0
    for path in root.glob("*.speaker_link.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        mid = payload.get("managed_transcript_id")
        if mid in canonical or mid in import_ids:
            count += 1
    return count


def _member_matches_deleted(member: str, deleted: set[str]) -> bool:
    raw = str(member)
    if raw in deleted:
        return True
    try:
        resolved = str(Path(raw).expanduser().resolve())
    except OSError:
        resolved = raw
    if resolved in deleted:
        return True
    for item in deleted:
        try:
            if Path(item).resolve() == Path(raw).expanduser().resolve():
                return True
        except OSError:
            continue
    return False


def tidy_group_membership(deleted_transcripts: set[str]) -> tuple[tuple[str, ...], list[str]]:
    emptied: list[str] = []
    warnings: list[str] = []
    if not deleted_transcripts:
        return (), []
    try:
        from transcriptx.core.store.group_manifest_store import GroupManifestStore
    except Exception as exc:
        warnings.append(f"Could not load groups: {exc}")
        return (), warnings
    try:
        groups, errors = GroupManifestStore().list_groups_best_effort()
    except Exception as exc:
        warnings.append(f"Could not list groups: {exc}")
        return (), warnings
    warnings.extend(errors or [])
    store = GroupManifestStore()
    for group in groups:
        remaining: list[str] = []
        removed_any = False
        for member in group.members:
            if _member_matches_deleted(str(member), deleted_transcripts):
                removed_any = True
                continue
            remaining.append(str(member))
        if not removed_any:
            continue
        if not remaining:
            emptied.append(group.name or group.group_id)
            continue
        try:
            store.update_group(group, members=remaining)
        except Exception as exc:
            warnings.append(
                f"Could not update group {group.name or group.group_id}: {exc}"
            )
    return tuple(emptied), warnings


def execute_preview(
    preview: DuplicatePreview,
    auth: DuplicateAuthorization,
) -> DuplicateResult:
    if not authorization_is_valid(auth, expected_plan_id=preview.plan_id):
        return DuplicateResult(
            ok=False,
            plan_id=preview.plan_id,
            errors=("Authorization failed; type DELETE DUPLICATES after acknowledging.",),
        )
    if not preview.can_execute:
        return DuplicateResult(
            ok=False,
            plan_id=preview.plan_id,
            errors=preview.blocking_errors or ("Plan cannot be executed.",),
        )

    skipped: list[str] = []
    warnings: list[str] = []
    audio_deleted = 0
    transcripts_deleted = 0
    companions_deleted = 0
    deleted_transcript_paths: list[str] = []
    deleted_audio_paths: list[str] = []
    import_ids: set[str] = set()
    dropped_transcripts: list[Path] = []

    for group in preview.groups:
        keeper_path = group.keeper.fingerprint.path
        for extra in group.extras:
            if not fingerprint_matches(extra.fingerprint):
                skipped.append(
                    f"{extra.fingerprint.path.name}: changed since preview; skipped"
                )
                continue
            path = extra.fingerprint.path
            if extra.role is MemberRole.AUDIO:
                if _unlink(path, warnings):
                    audio_deleted += 1
                    deleted_audio_paths.append(_path_key(path))
                continue

            import_id = import_id_for_transcript(path)
            if import_id:
                import_ids.add(import_id)
            companions = companion_files_for_transcript(path)
            json_deleted = False
            for companion in companions:
                if _unlink(companion, warnings):
                    companions_deleted += 1
                    if resolve_path(companion) == resolve_path(path):
                        json_deleted = True
            companions_deleted += _delete_corrections(path, warnings)
            if json_deleted or not path.exists():
                transcripts_deleted += 1
                deleted_transcript_paths.append(_path_key(path))
                dropped_transcripts.append(path)
                try:
                    unregister_source_path(path, retarget_to=keeper_path)
                except Exception as exc:
                    warnings.append(
                        f"Could not unregister {path.name} from slug index: {exc}"
                    )

    if dropped_transcripts:
        try:
            drop_processing_state_for_transcripts(dropped_transcripts)
        except Exception as exc:
            warnings.append(f"Could not update processing state: {exc}")

    emptied, group_warnings = tidy_group_membership(set(deleted_transcript_paths))
    warnings.extend(group_warnings)
    dangling = count_speaker_links_for_import_ids(import_ids)

    ok = not skipped or (audio_deleted + transcripts_deleted) > 0
    if skipped and not (audio_deleted or transcripts_deleted):
        ok = False
    return DuplicateResult(
        ok=ok,
        plan_id=preview.plan_id,
        audio_deleted=audio_deleted,
        transcripts_deleted=transcripts_deleted,
        companions_deleted=companions_deleted,
        skipped=tuple(skipped),
        warnings=tuple(warnings),
        dangling_speaker_links=dangling,
        emptied_groups=emptied,
        deleted_transcript_paths=tuple(deleted_transcript_paths),
        deleted_audio_paths=tuple(deleted_audio_paths),
    )
