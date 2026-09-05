"""Tests for LibraryFilter matching and Continue working ranking."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from transcriptx.app.corpus_inventory.models import (
    AnalysisState,
    AnalysisStatus,
    ContinueAction,
    CorrectionsState,
    CorrectionsStatus,
    FieldIntegrity,
    FileStamp,
    InventoryFingerprint,
    InventoryRow,
    LibraryFilter,
    LibraryWorkflowPreset,
    SpeakerIdState,
    SpeakerIdStatus,
)
from transcriptx.app.corpus_inventory.query import (
    apply_library_filter,
    continue_working_action,
    needs_attention_counts,
    select_continue_working,
)


def _fp() -> InventoryFingerprint:
    return InventoryFingerprint(stamps=(FileStamp("/x", 0, -1),))


def _row(
    name: str,
    *,
    speaker: SpeakerIdStatus = SpeakerIdStatus.COMPLETE,
    corrections: CorrectionsStatus = CorrectionsStatus.NEVER_STARTED,
    analysis: AnalysisStatus = AnalysisStatus.UNANALYSED,
    speaker_count: int | None = 2,
    last_activity: datetime | None = None,
    pending: int | None = None,
) -> InventoryRow:
    return InventoryRow(
        transcript_path=Path(f"/tmp/{name}.json"),
        transcript_key=name,
        slug=name,
        title=name,
        imported_at=None,
        duration_seconds=60.0,
        speaker_count=speaker_count,
        word_count=100,
        source_id="whisperx",
        listing_integrity=FieldIntegrity.OK,
        speaker=SpeakerIdState(status=speaker, integrity=FieldIntegrity.OK),
        corrections=CorrectionsState(
            status=corrections,
            integrity=FieldIntegrity.OK,
            pending_count=pending,
            accepted_count=0,
        ),
        analysis=AnalysisState(
            status=analysis,
            integrity=FieldIntegrity.OK,
            modules_succeeded=1 if analysis is AnalysisStatus.COMPLETED else None,
            modules_eligible=1 if analysis is AnalysisStatus.COMPLETED else None,
        ),
        last_activity_at=last_activity,
        fingerprint=_fp(),
    )


def test_preset_matching_ignores_unknown_as_complete() -> None:
    analysed = _row("a", analysis=AnalysisStatus.COMPLETED)
    unknown = _row("u", analysis=AnalysisStatus.UNKNOWN)
    filtered = apply_library_filter(
        [analysed, unknown],
        LibraryFilter(preset=LibraryWorkflowPreset.ANALYSED),
    )
    assert [row.title for row in filtered] == ["a"]


def test_needs_speaker_id_preset() -> None:
    rows = [
        _row("named", speaker=SpeakerIdStatus.COMPLETE),
        _row("partial", speaker=SpeakerIdStatus.PARTIAL),
        _row("none", speaker=SpeakerIdStatus.NONE),
        _row("unknown", speaker=SpeakerIdStatus.UNKNOWN),
    ]
    filtered = apply_library_filter(
        rows, LibraryFilter(preset=LibraryWorkflowPreset.NEEDS_SPEAKER_ID)
    )
    assert {row.title for row in filtered} == {"partial", "none"}


def test_query_matches_title_not_body() -> None:
    rows = [_row("Interview Alice"), _row("Standup")]
    filtered = apply_library_filter(rows, LibraryFilter(query="alice"))
    assert [row.title for row in filtered] == ["Interview Alice"]


def test_query_matches_tags() -> None:
    tagged = replace(_row("standup"), tags=("meeting",))
    other = _row("notes")
    rows = [tagged, other]
    filtered = apply_library_filter(rows, LibraryFilter(query="meeting"))
    assert [row.title for row in filtered] == ["standup"]
    filtered_tag = apply_library_filter(rows, LibraryFilter(tag="meeting"))
    assert [row.title for row in filtered_tag] == ["standup"]


def test_continue_working_prefers_resumable_over_recency() -> None:
    recent = datetime(2026, 8, 21, tzinfo=timezone.utc)
    older = datetime(2026, 8, 1, tzinfo=timezone.utc)
    idle = _row("idle-recent", last_activity=recent)
    corrections = _row(
        "old-corrections",
        corrections=CorrectionsStatus.PENDING,
        pending=2,
        last_activity=older,
    )
    chosen = select_continue_working([idle, corrections], limit=1)
    assert chosen[0].title == "old-corrections"
    assert continue_working_action(corrections) is ContinueAction.CORRECTIONS


def test_needs_attention_counts() -> None:
    rows = [
        _row("a", speaker=SpeakerIdStatus.NONE),
        _row("b", analysis=AnalysisStatus.INCOMPLETE),
        _row("c", corrections=CorrectionsStatus.PENDING, pending=1),
        _row("d", analysis=AnalysisStatus.COMPLETED, speaker=SpeakerIdStatus.COMPLETE),
    ]
    counts = needs_attention_counts(rows)
    assert counts["speaker_id"] == 1
    assert counts["analysis"] == 1
    assert counts["corrections"] == 1
