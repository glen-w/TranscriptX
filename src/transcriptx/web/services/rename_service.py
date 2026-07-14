"""
Web-facing rename utilities for transcript/audio artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import streamlit as st

from transcriptx.core.utils.rename.audio_association import find_original_audio_file
from transcriptx.core.utils.rename.names import (
    normalize_base_name,
    validate_target_name,
)
from transcriptx.core.utils.rename.outcome import RenameStatus
from transcriptx.core.utils.rename.pipeline import rename_managed_transcript
from transcriptx.core.utils.processing_state import load_processing_state
from transcriptx.web.cache_helpers import clear_rename_related_caches
from transcriptx.web.services.recordings_service import RecordingsService
from transcriptx.web.state import IMPORT_LAST_TRANSCRIPT_PATH


@dataclass(frozen=True)
class RenameResultError:
    code: str
    message: str
    phase: str = ""


@dataclass(frozen=True)
class RenameResult:
    """Normalized result for UI callers."""

    ok: bool
    message: str
    old_base_name: str = ""
    new_base_name: str = ""
    old_transcript_path: str = ""
    new_transcript_path: str = ""
    old_audio_path: str = ""
    new_audio_path: str = ""
    transaction_phase_ok: bool | None = None
    finalize_phase_ok: bool | None = None
    transaction_committed: bool = False
    operation_id: str | None = None
    status: str = ""
    audio_kind: str = ""
    audio_renamed: bool = False
    old_slug: str | None = None
    new_slug: str | None = None
    errors: tuple[RenameResultError, ...] = ()


class RenameService:
    """Service wrapper for transcript/audio rename actions in web pages."""

    @staticmethod
    def normalize_base_name(raw_name: str) -> str:
        return normalize_base_name(raw_name)

    @staticmethod
    def validate_target_name(
        current_base_name: str, raw_target_name: str
    ) -> tuple[bool, str]:
        return validate_target_name(current_base_name, raw_target_name)

    @staticmethod
    def rename(
        *,
        transcript_path: str | Path | None = None,
        audio_path: str | Path | None = None,
        new_base_name: str,
        dry_run: bool = False,
    ) -> RenameResult:
        if transcript_path is not None:
            return RenameService._rename_transcript_path(
                Path(transcript_path), new_base_name, dry_run=dry_run
            )
        if audio_path is not None:
            return RenameService.rename_from_audio(
                audio_path, new_base_name, dry_run=dry_run
            )
        return RenameResult(ok=False, message="No transcript or audio path provided.")

    @staticmethod
    def rename_transcript_and_audio(
        transcript_path: str | Path,
        raw_target_name: str,
    ) -> RenameResult:
        return RenameService._rename_transcript_path(
            Path(transcript_path), raw_target_name, dry_run=False
        )

    @staticmethod
    def _rename_transcript_path(
        transcript: Path, raw_target_name: str, *, dry_run: bool
    ) -> RenameResult:
        if not transcript.exists():
            return RenameResult(ok=False, message="Transcript file not found.")

        old_base = transcript.stem
        valid, error = RenameService.validate_target_name(old_base, raw_target_name)
        if not valid:
            return RenameResult(ok=False, message=error, old_base_name=old_base)

        new_base = RenameService.normalize_base_name(raw_target_name)
        outcome = rename_managed_transcript(transcript, new_base, dry_run=dry_run)

        # Slug is already reconciled inside the pipeline when committed
        committed = outcome.transaction_committed
        complete = outcome.status == RenameStatus.committed_complete
        partial = outcome.status == RenameStatus.committed_partial
        dry = outcome.status == RenameStatus.dry_run

        msg = outcome.message
        if partial:
            msg = (
                "Transcript rename committed, but some follow-up work is incomplete "
                "and can be repaired. "
                f"Repair id: {outcome.operation_id}"
            )
            if outcome.errors:
                detail = "; ".join(f"{e.phase}:{e.code}" for e in outcome.errors[:5])
                msg = f"{msg} ({detail})"
        elif outcome.status == RenameStatus.blocked:
            msg = outcome.message
        elif outcome.status == RenameStatus.failed_rolled_back:
            msg = "Rename failed and was rolled back. " f"{outcome.message}"
        elif outcome.status == RenameStatus.failed_rollback_incomplete:
            msg = (
                "Rename failed and rollback did not fully complete. "
                "Manual repair may be required. "
                f"{outcome.message}"
            )

        audio_msg = RenameService._audio_outcome_phrase(
            outcome.audio_kind, outcome.audio_renamed
        )
        if complete or dry:
            msg = f"{msg} ({audio_msg})" if audio_msg else msg

        return RenameResult(
            ok=complete or dry,
            message=msg,
            old_base_name=old_base,
            new_base_name=new_base,
            old_transcript_path=outcome.old_transcript_path or str(transcript),
            new_transcript_path=outcome.new_transcript_path,
            old_audio_path=outcome.old_audio_path,
            new_audio_path=outcome.new_audio_path,
            transaction_phase_ok=outcome.transaction_succeeded,
            finalize_phase_ok=outcome.finalize_succeeded,
            transaction_committed=committed,
            operation_id=outcome.operation_id,
            status=outcome.status.value,
            audio_kind=outcome.audio_kind,
            audio_renamed=outcome.audio_renamed,
            old_slug=outcome.old_slug,
            new_slug=outcome.new_slug,
            errors=tuple(
                RenameResultError(code=e.code, message=e.message, phase=e.phase)
                for e in outcome.errors
            ),
        )

    @staticmethod
    def _audio_outcome_phrase(kind: str, renamed: bool) -> str:
        if renamed:
            return "linked working-copy audio renamed"
        if kind == "archival_original":
            return "preserved archival/external association"
        if kind == "external_or_unknown":
            return "preserved archival/external association"
        if kind in {"missing", "none", ""}:
            return "no linked working-copy audio"
        return "audio association unchanged"

    @staticmethod
    def rename_from_audio(
        raw_audio_path: str | Path,
        raw_target_name: str,
        *,
        dry_run: bool = False,
    ) -> RenameResult:
        audio_path = Path(raw_audio_path)
        transcript = RenameService.find_linked_transcript_for_audio(audio_path)
        if transcript is None:
            return RenameResult(
                ok=False,
                message=(
                    "This recording is not linked to a transcript in processing state, "
                    "so synchronized rename is unavailable."
                ),
            )
        return RenameService._rename_transcript_path(
            transcript, raw_target_name, dry_run=dry_run
        )

    @staticmethod
    def find_linked_transcript_for_audio(audio_path: str | Path) -> Path | None:
        audio = Path(audio_path)
        try:
            target = audio.resolve()
        except OSError:
            target = audio

        state = load_processing_state(validate=False)
        processed = state.get("processed_files", {}) or {}
        for _, entry in processed.items():
            if not isinstance(entry, dict):
                continue
            raw_transcript = entry.get("transcript_path")
            if not raw_transcript:
                continue
            transcript = Path(raw_transcript)
            if not transcript.exists():
                continue
            found_audio = find_original_audio_file(str(transcript))
            if found_audio is None:
                continue
            try:
                if found_audio.resolve() == target:
                    return transcript
            except OSError:
                if found_audio == target:
                    return transcript
        return None

    @staticmethod
    def after_rename(
        result: RenameResult,
        *,
        library_transcripts: list | None = None,
        extra_session_patch: Callable[[RenameResult], None] | None = None,
    ) -> None:
        RenameService.refresh_after_rename(
            result,
            library_transcripts=library_transcripts,
            extra_session_patch=extra_session_patch,
        )

    @staticmethod
    def refresh_after_rename(
        result: RenameResult,
        *,
        library_transcripts: list | None = None,
        extra_session_patch: Callable[[RenameResult], None] | None = None,
    ) -> None:
        clear_rename_related_caches()
        RecordingsService.list_recordings.clear()  # type: ignore[attr-defined]

        old_t = result.old_transcript_path
        new_t = result.new_transcript_path
        old_a = result.old_audio_path
        new_a = result.new_audio_path
        old_slug = result.old_slug
        new_slug = result.new_slug

        subject_id = st.session_state.get("subject_id")
        if subject_id is not None:
            if RenameService._paths_equal(str(subject_id), old_t):
                st.session_state["subject_id"] = new_slug or new_t or None
                st.session_state["run_id"] = None
            elif old_slug and subject_id == old_slug and new_slug:
                st.session_state["subject_id"] = new_slug
                st.session_state["run_id"] = None

        import_path = st.session_state.get(IMPORT_LAST_TRANSCRIPT_PATH)
        if RenameService._paths_equal(import_path, old_t) and new_t:
            st.session_state[IMPORT_LAST_TRANSCRIPT_PATH] = new_t

        single_audio = st.session_state.get("audio_prep_selected_file")
        if old_a and new_a and RenameService._paths_equal(single_audio, old_a):
            st.session_state["audio_prep_selected_file"] = new_a

        multi_audio = st.session_state.get("audio_prep_selected_files")
        if isinstance(multi_audio, list) and old_a and new_a:
            st.session_state["audio_prep_selected_files"] = [
                new_a if RenameService._paths_equal(item, old_a) else item
                for item in multi_audio
            ]

        merge_order = st.session_state.get("audio_merge_ordered_paths")
        if isinstance(merge_order, list) and old_a and new_a:
            st.session_state["audio_merge_ordered_paths"] = [
                new_a if RenameService._paths_equal(item, old_a) else item
                for item in merge_order
            ]

        if library_transcripts and new_t:
            from transcriptx.web.navigation import library_transcript_index

            idx = library_transcript_index(library_transcripts, new_t)
            if idx > 0:
                st.session_state["library_transcript_select"] = idx

        if extra_session_patch is not None:
            extra_session_patch(result)

    @staticmethod
    def _paths_equal(a: Any, b: Any) -> bool:
        if a is None or b is None:
            return False
        sa, sb = str(a), str(b)
        if sa == sb:
            return True
        try:
            return Path(sa).expanduser().resolve() == Path(sb).expanduser().resolve()
        except OSError:
            return False

    @staticmethod
    def _find_audio_path_for_transcript(transcript_path: Path) -> Path | None:
        return find_original_audio_file(str(transcript_path))
