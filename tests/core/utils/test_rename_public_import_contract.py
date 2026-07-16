"""Public import contract for transcriptx.core.utils.rename package."""

from __future__ import annotations

import transcriptx.core.utils.rename as rename_pkg

REQUIRED = [
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
]


def test_rename_package_exports_required_symbols() -> None:
    missing = [name for name in REQUIRED if not hasattr(rename_pkg, name)]
    assert missing == [], f"rename package missing: {missing}"


def test_rename_package_all_matches_lazy_map() -> None:
    for name in rename_pkg.__all__:
        assert hasattr(rename_pkg, name), name
