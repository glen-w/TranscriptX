"""
Web-facing rename utilities for transcript/audio artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st

from transcriptx.core.utils.file_rename import rename_transcript_files_with_outcome
from transcriptx.core.utils.processing_state import load_processing_state
from transcriptx.web.cache_helpers import clear_transcript_listing_caches
from transcriptx.web.services.recordings_service import RecordingsService

_INVALID_NAME_CHARS = {"/", "\\", ":", "*", "?", '"', "<", ">", "|"}
_KNOWN_EXTENSIONS = {
    ".json",
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
    ".aac",
    ".wma",
}


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
    #: From core rename pipeline: transaction phase (file + state + history) succeeded
    transaction_phase_ok: bool | None = None
    #: From core rename pipeline: finalize phase (output dir / in-tree renames) succeeded
    finalize_phase_ok: bool | None = None


class RenameService:
    """Service wrapper for transcript/audio rename actions in web pages."""

    @staticmethod
    def normalize_base_name(raw_name: str) -> str:
        name = (raw_name or "").strip().rstrip(".")
        suffix = Path(name).suffix.lower()
        if suffix in _KNOWN_EXTENSIONS:
            name = name[: -len(suffix)]
        return name.strip()

    @staticmethod
    def validate_target_name(
        current_base_name: str, raw_target_name: str
    ) -> tuple[bool, str]:
        target = RenameService.normalize_base_name(raw_target_name)
        if not target:
            return False, "Please provide a new file name."
        if any(char in target for char in _INVALID_NAME_CHARS):
            bad = ", ".join(sorted(_INVALID_NAME_CHARS))
            return False, f"File name contains invalid characters: {bad}"
        if target == current_base_name:
            return False, "New file name must be different from the current name."
        return True, ""

    @staticmethod
    def rename_transcript_and_audio(
        transcript_path: str | Path,
        raw_target_name: str,
    ) -> RenameResult:
        transcript = Path(transcript_path)
        if not transcript.exists():
            return RenameResult(ok=False, message="Transcript file not found.")

        old_base = transcript.stem
        valid, error = RenameService.validate_target_name(old_base, raw_target_name)
        if not valid:
            return RenameResult(ok=False, message=error, old_base_name=old_base)

        new_base = RenameService.normalize_base_name(raw_target_name)
        new_transcript = transcript.with_name(f"{new_base}.json")

        old_audio_path = RenameService._find_audio_path_for_transcript(transcript)
        old_audio_suffix = old_audio_path.suffix if old_audio_path else ""
        new_audio = (
            old_audio_path.with_name(f"{new_base}{old_audio_suffix}")
            if old_audio_path and old_audio_suffix
            else None
        )

        outcome = rename_transcript_files_with_outcome(
            old_base, new_base, str(transcript), dry_run=False
        )
        if not outcome.ok:
            partial = outcome.partial_success_after_transaction
            msg = (
                "Transcript and processing state were updated, but moving the output "
                "folder failed. Check output directories; you may need to merge or fix "
                "paths manually."
                if partial
                else "Rename failed. Check for name conflicts or locked files."
            )
            return RenameResult(
                ok=False,
                message=msg,
                old_base_name=old_base,
                new_base_name=new_base,
                old_transcript_path=str(transcript),
                new_transcript_path=str(new_transcript),
                old_audio_path=str(old_audio_path) if old_audio_path else "",
                new_audio_path=str(new_audio) if new_audio else "",
                transaction_phase_ok=outcome.transaction_succeeded,
                finalize_phase_ok=outcome.finalize_succeeded,
            )

        return RenameResult(
            ok=True,
            message="Renamed transcript and linked audio files.",
            old_base_name=old_base,
            new_base_name=new_base,
            old_transcript_path=str(transcript),
            new_transcript_path=str(new_transcript),
            old_audio_path=str(old_audio_path) if old_audio_path else "",
            new_audio_path=str(new_audio) if new_audio else "",
            transaction_phase_ok=outcome.transaction_succeeded,
            finalize_phase_ok=outcome.finalize_succeeded,
        )

    @staticmethod
    def rename_from_audio(
        raw_audio_path: str | Path, raw_target_name: str
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
        return RenameService.rename_transcript_and_audio(transcript, raw_target_name)

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
            for candidate in RenameService._audio_candidates(entry):
                if not candidate:
                    continue
                p = Path(candidate)
                try:
                    if p.exists() and p.resolve() == target:
                        transcript_path = entry.get("transcript_path")
                        if transcript_path:
                            t = Path(transcript_path)
                            if t.exists():
                                return t
                except OSError:
                    continue
        return None

    @staticmethod
    def refresh_after_rename(result: RenameResult) -> None:
        """Clear caches and patch stale selections in session_state."""
        clear_transcript_listing_caches()
        RecordingsService.list_recordings.clear()  # type: ignore[attr-defined]

        old_t = result.old_transcript_path
        new_t = result.new_transcript_path
        old_a = result.old_audio_path
        new_a = result.new_audio_path

        selected_path = st.session_state.get("selected_transcript_path")
        if selected_path == old_t and new_t:
            st.session_state["selected_transcript_path"] = new_t

        subject_id = st.session_state.get("subject_id")
        if subject_id == old_t:
            st.session_state["subject_id"] = new_t or None
            st.session_state["run_id"] = None

        single_audio = st.session_state.get("audio_prep_selected_file")
        if old_a and new_a and single_audio == old_a:
            st.session_state["audio_prep_selected_file"] = new_a

        multi_audio = st.session_state.get("audio_prep_selected_files")
        if isinstance(multi_audio, list) and old_a and new_a:
            st.session_state["audio_prep_selected_files"] = [
                new_a if item == old_a else item for item in multi_audio
            ]

        merge_order = st.session_state.get("audio_merge_ordered_paths")
        if isinstance(merge_order, list) and old_a and new_a:
            st.session_state["audio_merge_ordered_paths"] = [
                new_a if item == old_a else item for item in merge_order
            ]

    @staticmethod
    def _audio_candidates(entry: dict[str, Any]) -> list[str]:
        return [
            entry.get("audio_path", ""),
            entry.get("mp3_path", ""),
            (entry.get("convert") or {}).get("mp3_path", ""),
            ((entry.get("steps") or {}).get("convert") or {}).get("mp3_path", ""),
        ]

    @staticmethod
    def _find_audio_path_for_transcript(transcript_path: Path) -> Path | None:
        try:
            target = transcript_path.resolve()
        except OSError:
            target = transcript_path

        state = load_processing_state(validate=False)
        processed = state.get("processed_files", {}) or {}
        for _, entry in processed.items():
            if not isinstance(entry, dict):
                continue
            raw_transcript = entry.get("transcript_path")
            if not raw_transcript:
                continue
            t_path = Path(raw_transcript)
            try:
                if not t_path.exists() or t_path.resolve() != target:
                    continue
            except OSError:
                continue
            for candidate in RenameService._audio_candidates(entry):
                if candidate:
                    c = Path(candidate)
                    if c.exists():
                        return c
        return None
