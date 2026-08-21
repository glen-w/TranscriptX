"""Pure mapping from cheap payloads to typed inventory subsystem state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from transcriptx.app.corpus_inventory.models import (
    AnalysisState,
    AnalysisStatus,
    CorrectionsState,
    CorrectionsStatus,
    FieldIntegrity,
    SpeakerIdState,
    SpeakerIdStatus,
)
from transcriptx.core.pipeline.run_outcome_truth import project_canonical_outcomes
from transcriptx.io.speaker_map_resolver import SpeakerMapState

_ELIGIBLE_OUTCOMES = frozenset(
    {"succeeded", "failed", "blocked", "enabled", "requested"}
)


def parse_iso_datetime(value: Any) -> datetime | None:
    """Parse ISO-8601 timestamps; return None when missing or malformed."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def datetime_from_mtime(mtime: float | None) -> datetime | None:
    if mtime is None or mtime <= 0:
        return None
    try:
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def listing_from_document(
    doc: Any,
) -> tuple[
    float | None,
    int | None,
    int | None,
    FieldIntegrity,
]:
    """Extract duration/speakers/words; caller must drop segments."""
    if not isinstance(doc, dict):
        return None, None, None, FieldIntegrity.MALFORMED
    metadata = doc.get("metadata")
    if metadata is None:
        return None, None, None, FieldIntegrity.MISSING
    if not isinstance(metadata, dict):
        return None, None, None, FieldIntegrity.MALFORMED

    duration: float | None = None
    for key in ("duration_seconds", "duration"):
        raw = metadata.get(key)
        if raw is None:
            continue
        try:
            duration = float(raw)
            break
        except (TypeError, ValueError):
            return None, None, None, FieldIntegrity.MALFORMED

    speaker_count: int | None = None
    for key in ("speaker_count", "num_speakers"):
        raw = metadata.get(key)
        if raw is None:
            continue
        try:
            speaker_count = int(raw)
            break
        except (TypeError, ValueError):
            return None, None, None, FieldIntegrity.MALFORMED

    word_count: int | None = None
    for key in ("word_count", "words"):
        raw = metadata.get(key)
        if raw is None:
            continue
        try:
            word_count = int(raw)
            break
        except (TypeError, ValueError):
            return None, None, None, FieldIntegrity.MALFORMED

    return duration, speaker_count, word_count, FieldIntegrity.OK


def speaker_state_from_map(
    state: SpeakerMapState | None,
    *,
    speaker_count: int | None,
    malformed: bool = False,
) -> SpeakerIdState:
    if malformed:
        return SpeakerIdState(status=SpeakerIdStatus.UNKNOWN, integrity=FieldIntegrity.MALFORMED)
    if state is None or not state.has_sidecar:
        return SpeakerIdState(
            status=SpeakerIdStatus.NONE,
            integrity=FieldIntegrity.MISSING,
            named_count=0,
            ignored_count=0,
            unidentified_count=speaker_count,
        )
    named = int(state.named_speaker_count)
    ignored = int(state.ignored_speaker_count)
    if speaker_count is None:
        if named == 0 and ignored == 0:
            status = SpeakerIdStatus.NONE
            unidentified = None
        else:
            status = SpeakerIdStatus.PARTIAL
            unidentified = None
    else:
        unidentified = max(int(speaker_count) - named - ignored, 0)
        if named == 0 and ignored == 0:
            status = SpeakerIdStatus.NONE
        elif unidentified == 0:
            status = SpeakerIdStatus.COMPLETE
        else:
            status = SpeakerIdStatus.PARTIAL
    return SpeakerIdState(
        status=status,
        integrity=FieldIntegrity.OK,
        named_count=named,
        ignored_count=ignored,
        unidentified_count=unidentified,
    )


def analysis_state_from_run_results(
    run_results: dict[str, Any] | None,
    *,
    run_id: str | None,
    last_analysed_at: datetime | None,
    run_present: bool,
    results_unreadable: bool = False,
) -> AnalysisState:
    if not run_present:
        return AnalysisState(
            status=AnalysisStatus.UNANALYSED,
            integrity=FieldIntegrity.MISSING,
        )
    if results_unreadable or run_results is None:
        return AnalysisState(
            status=AnalysisStatus.UNKNOWN,
            integrity=FieldIntegrity.MALFORMED if results_unreadable else FieldIntegrity.MISSING,
            latest_run_id=run_id,
            last_analysed_at=last_analysed_at,
        )
    try:
        rows = project_canonical_outcomes(run_results)
    except Exception:
        return AnalysisState(
            status=AnalysisStatus.UNKNOWN,
            integrity=FieldIntegrity.MALFORMED,
            latest_run_id=run_id,
            last_analysed_at=last_analysed_at,
        )
    eligible = [row for row in rows if row.status in _ELIGIBLE_OUTCOMES]
    succeeded = [row for row in eligible if row.status == "succeeded"]
    failed = [row for row in eligible if row.status == "failed"]
    blocked_or_open = [
        row for row in eligible if row.status in {"blocked", "enabled", "requested"}
    ]
    modules_succeeded = len(succeeded)
    modules_eligible = len(eligible)
    if modules_eligible == 0:
        status = AnalysisStatus.COMPLETED
        run_status = "completed"
    elif failed and not succeeded and not blocked_or_open:
        status = AnalysisStatus.FAILED
        run_status = "failed"
    elif failed or blocked_or_open:
        status = AnalysisStatus.INCOMPLETE
        run_status = "partial"
    else:
        status = AnalysisStatus.COMPLETED
        run_status = "completed"
    return AnalysisState(
        status=status,
        integrity=FieldIntegrity.OK,
        modules_succeeded=modules_succeeded,
        modules_eligible=modules_eligible,
        latest_run_id=run_id,
        run_status=run_status,
        last_analysed_at=last_analysed_at,
    )


def corrections_state_from_session(
    payload: dict[str, Any] | None,
    *,
    unreadable: bool = False,
) -> CorrectionsState:
    if unreadable:
        return CorrectionsState(
            status=CorrectionsStatus.UNKNOWN,
            integrity=FieldIntegrity.MALFORMED,
        )
    if not payload:
        return CorrectionsState(
            status=CorrectionsStatus.NEVER_STARTED,
            integrity=FieldIntegrity.MISSING,
        )
    if not isinstance(payload, dict):
        return CorrectionsState(
            status=CorrectionsStatus.UNKNOWN,
            integrity=FieldIntegrity.MALFORMED,
        )
    gen = payload.get("current_generation_id")
    candidates = payload.get("candidates")
    if candidates is None:
        candidates = []
    if not isinstance(candidates, list):
        return CorrectionsState(
            status=CorrectionsStatus.UNKNOWN,
            integrity=FieldIntegrity.MALFORMED,
            updated_at=parse_iso_datetime(payload.get("updated_at")),
        )
    pending = accepted = 0
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if gen is not None and candidate.get("generation_id") != gen:
            continue
        status = str(candidate.get("review_status") or "pending")
        if status == "accepted":
            accepted += 1
        elif status in {"rejected", "skipped"}:
            continue
        else:
            pending += 1
    updated_at = parse_iso_datetime(payload.get("updated_at"))
    if pending > 0:
        corr_status = CorrectionsStatus.PENDING
    elif accepted > 0:
        corr_status = CorrectionsStatus.COMPLETE
    else:
        corr_status = CorrectionsStatus.NEVER_STARTED
    return CorrectionsState(
        status=corr_status,
        integrity=FieldIntegrity.OK,
        accepted_count=accepted,
        pending_count=pending,
        updated_at=updated_at,
    )


def max_datetime(*values: datetime | None) -> datetime | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return max(present)
