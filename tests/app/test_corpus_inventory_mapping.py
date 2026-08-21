"""Unit tests for corpus inventory pure mapping."""

from __future__ import annotations

from datetime import datetime, timezone

from transcriptx.app.corpus_inventory.mapping import (
    analysis_state_from_run_results,
    corrections_state_from_session,
    listing_from_document,
    speaker_state_from_map,
)
from transcriptx.app.corpus_inventory.models import (
    AnalysisStatus,
    CorrectionsStatus,
    FieldIntegrity,
    SpeakerIdStatus,
)
from transcriptx.io.speaker_map_resolver import SpeakerMapState


def test_listing_from_metadata_does_not_need_segments() -> None:
    duration, speakers, words, integrity = listing_from_document(
        {
            "metadata": {
                "duration_seconds": 4920,
                "speaker_count": 3,
                "word_count": 10430,
            },
            "segments": [{"text": "ignored"}],
        }
    )
    assert duration == 4920
    assert speakers == 3
    assert words == 10430
    assert integrity is FieldIntegrity.OK


def test_listing_malformed_metadata() -> None:
    _, _, _, integrity = listing_from_document({"metadata": "nope"})
    assert integrity is FieldIntegrity.MALFORMED


def test_speaker_complete_proxy() -> None:
    state = SpeakerMapState(
        has_sidecar=True,
        speaker_map={"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"},
        ignored_speakers=["SPEAKER_02"],
    )
    mapped = speaker_state_from_map(state, speaker_count=3)
    assert mapped.status is SpeakerIdStatus.COMPLETE
    assert mapped.unidentified_count == 0


def test_speaker_partial_proxy() -> None:
    state = SpeakerMapState(
        has_sidecar=True,
        speaker_map={"SPEAKER_00": "Alice"},
        ignored_speakers=[],
    )
    mapped = speaker_state_from_map(state, speaker_count=3)
    assert mapped.status is SpeakerIdStatus.PARTIAL
    assert mapped.unidentified_count == 2


def test_speaker_none_without_sidecar() -> None:
    mapped = speaker_state_from_map(
        SpeakerMapState(has_sidecar=False), speaker_count=2
    )
    assert mapped.status is SpeakerIdStatus.NONE
    assert mapped.integrity is FieldIntegrity.MISSING


def test_analysis_eligible_excludes_policy_skips() -> None:
    run_results = {
        "modules_enabled": ["sentiment", "topics", "voice"],
        "modules_run": ["sentiment", "topics"],
        "modules_failed": [],
        "modules_skipped": [
            {"module": "voice", "execution_status": "skipped", "reason": "no audio"}
        ],
    }
    state = analysis_state_from_run_results(
        run_results,
        run_id="run-1",
        last_analysed_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        run_present=True,
    )
    assert state.status is AnalysisStatus.COMPLETED
    assert state.modules_succeeded == 2
    assert state.modules_eligible == 2
    assert state.last_analysed_at is not None


def test_analysis_incomplete_with_failures() -> None:
    run_results = {
        "modules_enabled": ["a", "b", "c"],
        "modules_run": ["a"],
        "modules_failed": ["b"],
        "modules_skipped": [],
    }
    state = analysis_state_from_run_results(
        run_results, run_id="run-2", last_analysed_at=None, run_present=True
    )
    assert state.status is AnalysisStatus.INCOMPLETE
    assert state.modules_succeeded == 1
    assert state.modules_eligible == 3


def test_analysis_unanalysed_without_run() -> None:
    state = analysis_state_from_run_results(
        None, run_id=None, last_analysed_at=None, run_present=False
    )
    assert state.status is AnalysisStatus.UNANALYSED
    assert state.modules_eligible is None


def test_analysis_unknown_when_results_unreadable() -> None:
    state = analysis_state_from_run_results(
        None,
        run_id="run-x",
        last_analysed_at=None,
        run_present=True,
        results_unreadable=True,
    )
    assert state.status is AnalysisStatus.UNKNOWN
    assert state.modules_eligible is None


def test_corrections_pending_and_complete() -> None:
    pending = corrections_state_from_session(
        {
            "current_generation_id": 1,
            "updated_at": "2026-08-11T10:00:00Z",
            "candidates": [
                {"generation_id": 1, "review_status": "accepted"},
                {"generation_id": 1, "review_status": "pending"},
                {"generation_id": 0, "review_status": "pending"},
            ],
        }
    )
    assert pending.status is CorrectionsStatus.PENDING
    assert pending.accepted_count == 1
    assert pending.pending_count == 1

    done = corrections_state_from_session(
        {
            "current_generation_id": 1,
            "candidates": [{"generation_id": 1, "review_status": "accepted"}],
        }
    )
    assert done.status is CorrectionsStatus.COMPLETE


def test_corrections_missing_and_malformed() -> None:
    missing = corrections_state_from_session(None)
    assert missing.status is CorrectionsStatus.NEVER_STARTED
    assert missing.integrity is FieldIntegrity.MISSING
    bad = corrections_state_from_session(None, unreadable=True)
    assert bad.status is CorrectionsStatus.UNKNOWN
    assert bad.integrity is FieldIntegrity.MALFORMED
