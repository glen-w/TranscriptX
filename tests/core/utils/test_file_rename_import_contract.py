"""Import-contract tests for file_rename re-export shim."""

from __future__ import annotations

import transcriptx.core.utils.file_rename as fr

REQUIRED_SYMBOLS = [
    "OUTPUTS_DIR",
    "PROCESSING_STATE_FILE",
    "RECORDINGS_DIR",
    "ROLLBACK_POLICY",
    "RenameContext",
    "RenamePlan",
    "RenamePlanValidation",
    "RenameTranscriptOutcome",
    "RenameTransaction",
    "ProcessingStateRenameMutation",
    "append_rename_history",
    "build_rename_plan",
    "extract_date_prefix",
    "extract_date_prefix_from_filename",
    "extract_date_prefix_from_transcript",
    "find_original_audio_file",
    "ordered_audio_candidate_paths_for_state_entry",
    "prompt_for_rename",
    "rename_files_in_directory",
    "rename_managed_transcript",
    "rename_mp3_after_conversion",
    "rename_mp3_file",
    "rename_transcript_after_speaker_mapping",
    "rename_transcript_files",
    "rename_transcript_files_with_outcome",
    "repair_managed_rename",
    "shutil",
    "log_error",
    "resolve_file_path",
    "validate_managed_transcript",
    "update_processing_state",
    "invalidate_path_cache",
    "_audio_lookup_bases",
    "_build_audio_candidates_from_recordings",
    "_compute_processing_state_rename_mutation",
    "_fallback_audio_candidate_paths_no_state",
    "_finalize_output_directory_move",
    "_legacy_rename_hook_noop",
    "_looks_like_uuid",
    "_mutate_metadata_for_rename",
    "_persist_processing_state_mutation",
    "_sibling_path_validation_messages",
]


def test_file_rename_shim_exports_required_symbols() -> None:
    missing = [name for name in REQUIRED_SYMBOLS if not hasattr(fr, name)]
    assert missing == [], f"file_rename shim missing: {missing}"


def test_file_rename_shim_has_no_hidden_pipeline_logic() -> None:
    source = open(fr.__file__, encoding="utf-8").read()
    assert "Compatibility re-export shim" in source
    # Pipeline orchestration must not live in the shim body
    assert "def rename_managed_transcript" not in source
