"""Prompt-free warm for assistive LLM rename / speaker-name suggestion caches."""

from __future__ import annotations

from pathlib import Path

from transcriptx.app.models.requests import WarmSuggestionsRequest
from transcriptx.app.models.results import WarmSuggestionsResult
from typing import Callable, Optional

ProgressCallback = Callable[[int, int, str], None]
from transcriptx.services.llm_suggestions.bulk_warm import (
    BulkLlmSuggestionsService,
    BulkWarmKind,
    BulkWarmTargetStatus,
)


def _kinds_from_request(request: WarmSuggestionsRequest) -> list[BulkWarmKind]:
    if request.warm_all:
        return [BulkWarmKind.SPEAKER_NAMES, BulkWarmKind.RENAME]
    kinds: list[BulkWarmKind] = []
    if request.warm_speaker_names:
        kinds.append(BulkWarmKind.SPEAKER_NAMES)
    if request.warm_rename:
        kinds.append(BulkWarmKind.RENAME)
    return kinds


def run_warm_suggestions(
    request: WarmSuggestionsRequest,
    progress: Optional[ProgressCallback] = None,
) -> WarmSuggestionsResult:
    """Warm suggestion caches. No prompts, no prints."""
    kinds = _kinds_from_request(request)
    if not kinds:
        return WarmSuggestionsResult(
            success=False,
            errors=["Select warm_speaker_names, warm_rename, or warm_all."],
        )

    paths: list[Path] | None = None
    if request.transcript_paths:
        paths = [Path(p).expanduser() for p in request.transcript_paths]

    bulk = BulkLlmSuggestionsService().warm(
        kinds=kinds,
        paths=paths,
        force_refresh=bool(request.force_refresh),
        dry_run=bool(request.dry_run),
        progress_callback=progress,
    )
    errors = [
        f"{target.transcript_label} [{target.kind.value}]: {target.message}"
        for target in bulk.targets
        if target.status is BulkWarmTargetStatus.ERROR
    ]
    log_lines = [
        f"{Path(target.transcript_path).name} [{target.kind.value}]: "
        f"{target.status.value}"
        + (f" — {target.message}" if target.message else "")
        for target in bulk.targets
    ]
    return WarmSuggestionsResult(
        success=bulk.error_count == 0,
        ok_count=bulk.ok_count,
        skipped_fresh_count=bulk.skipped_fresh_count,
        error_count=bulk.error_count,
        errors=errors,
        log_lines=log_lines,
    )
