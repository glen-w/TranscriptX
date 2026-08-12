"""Managed transcript rename package."""

from __future__ import annotations

from typing import Any

__all__ = [
    "RenameNames",
    "RenamePaths",
    "RenameManagedOutcome",
    "RenameStatus",
    "RenameTranscriptOutcome",
    "RenameContext",
    "RenamePlan",
    "RenamePlanValidation",
    "ROLLBACK_POLICY",
    "normalize_base_name",
    "validate_target_name",
    "build_rename_plan",
    "rename_managed_transcript",
    "repair_managed_rename",
    "discover_incomplete_renames",
    "rename_transcript_files",
    "rename_transcript_files_with_outcome",
    "find_original_audio_file",
    "ordered_audio_candidate_paths_for_state_entry",
    "extract_date_prefix",
    "extract_date_prefix_from_filename",
    "extract_date_prefix_from_transcript",
    "resolve_rename_date_prefix",
    "suggest_rename_base_name",
    "SmartRenameSuggestion",
    "parse_recording_datetime",
    "suggest_smart_rename_base_name",
    "prompt_for_rename",
    "rename_transcript_after_speaker_mapping",
]

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "RenameNames": (".names", "RenameNames"),
    "RenamePaths": (".names", "RenamePaths"),
    "normalize_base_name": (".names", "normalize_base_name"),
    "validate_target_name": (".names", "validate_target_name"),
    "RenameManagedOutcome": (".outcome", "RenameManagedOutcome"),
    "RenameStatus": (".outcome", "RenameStatus"),
    "RenameTranscriptOutcome": (".outcome", "RenameTranscriptOutcome"),
    "RenameContext": (".plan", "RenameContext"),
    "RenamePlan": (".plan", "RenamePlan"),
    "RenamePlanValidation": (".plan", "RenamePlanValidation"),
    "ROLLBACK_POLICY": (".plan", "ROLLBACK_POLICY"),
    "build_rename_plan": (".plan", "build_rename_plan"),
    "rename_managed_transcript": (".pipeline", "rename_managed_transcript"),
    "repair_managed_rename": (".pipeline", "repair_managed_rename"),
    "rename_transcript_files": (".pipeline", "rename_transcript_files"),
    "rename_transcript_files_with_outcome": (
        ".pipeline",
        "rename_transcript_files_with_outcome",
    ),
    "discover_incomplete_renames": (".journal", "discover_incomplete_renames"),
    "find_original_audio_file": (".audio_association", "find_original_audio_file"),
    "ordered_audio_candidate_paths_for_state_entry": (
        ".audio_association",
        "ordered_audio_candidate_paths_for_state_entry",
    ),
    "extract_date_prefix": (".date_prefix", "extract_date_prefix"),
    "extract_date_prefix_from_filename": (
        ".date_prefix",
        "extract_date_prefix_from_filename",
    ),
    "extract_date_prefix_from_transcript": (
        ".date_prefix",
        "extract_date_prefix_from_transcript",
    ),
    "resolve_rename_date_prefix": (".date_prefix", "resolve_rename_date_prefix"),
    "suggest_rename_base_name": (".date_prefix", "suggest_rename_base_name"),
    "SmartRenameSuggestion": (".smart_name", "SmartRenameSuggestion"),
    "parse_recording_datetime": (".smart_name", "parse_recording_datetime"),
    "suggest_smart_rename_base_name": (
        ".smart_name",
        "suggest_smart_rename_base_name",
    ),
    "prompt_for_rename": (".cli", "prompt_for_rename"),
    "rename_transcript_after_speaker_mapping": (
        ".cli",
        "rename_transcript_after_speaker_mapping",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = _LAZY_EXPORTS[name]
    from importlib import import_module

    mod = import_module(module_name, __name__)
    value = getattr(mod, attr)
    globals()[name] = value
    return value
