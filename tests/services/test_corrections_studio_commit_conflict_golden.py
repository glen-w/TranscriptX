"""Commit-conflict golden — no successful persist; prior candidates returned."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.store.corrections_session_store import GenerationCommitConflict
from transcriptx.services.corrections_studio.candidate_service import (
    CorrectionsStudioCandidateService,
    GenerateCandidatesResult,
)
from transcriptx.services.corrections_studio.schema import (
    GenerationManifest,
    ReviewStatus,
    StudioCandidate,
    StudioSessionDocument,
)
from transcriptx.services.corrections_studio.semantic_identity import (
    compute_semantic_identity_key,
)


@pytest.mark.unit
def test_generate_candidates_commit_conflict_golden() -> None:
    prior = StudioCandidate(
        candidate_id="old",
        generation_id=1,
        kind="consistency",
        wrong_text="a",
        right_text="b",
        occurrences=[],
        review_status=ReviewStatus.pending,
        semantic_identity_key=compute_semantic_identity_key("a", "b"),
    )
    doc = StudioSessionDocument(
        session_id="sid",
        transcript_path="/tmp/x.json",
        recorded_transcript_identity_hash="abc12345",
        current_generation_id=1,
        candidates=[prior],
        review_records=[],
        rules={},
    )
    mock_session = MagicMock()
    mock_session.store.read_event_lines.return_value = ["{}"]
    mock_session.next_event_sequence.return_value = 2
    mock_session.last_event_sequence.return_value = 1
    mock_session.load_document.return_value = doc
    mock_session.persist_event_batch.side_effect = GenerationCommitConflict(
        "seq conflict", reason="event_sequence_conflict"
    )
    # Ensure document persist path is never used as a bypass
    mock_session.persist = MagicMock(
        side_effect=AssertionError("persist must not be called on conflict path")
    )

    with (
        patch(
            "transcriptx.services.corrections_studio.candidate_service.load_segments",
            return_value=[{"id": "s0", "text": "hello"}],
        ),
        patch(
            "transcriptx.services.corrections_studio.candidate_service.compute_transcript_identity_hash",
            return_value="tk",
        ),
        patch(
            "transcriptx.services.corrections_studio.candidate_service.get_config",
            return_value=MagicMock(
                analysis=MagicMock(corrections=None), llm=MagicMock(enabled=False)
            ),
        ),
        patch(
            "transcriptx.services.corrections_studio.candidate_service.load_memory",
        ) as mock_mem,
        patch(
            "transcriptx.services.corrections_studio.candidate_service.resolve_fuzzy_speaker_inputs",
        ) as mock_fuzz,
        patch(
            "transcriptx.services.corrections_studio.candidate_service.load_speaker_map_state",
        ) as mock_sms,
        patch(
            "transcriptx.services.corrections_studio.candidate_service.detect_memory_hits",
            return_value=[],
        ),
        patch(
            "transcriptx.services.corrections_studio.candidate_service.build_generation_manifest",
        ) as mock_manifest,
        patch(
            "transcriptx.services.corrections_studio.candidate_service.compute_generation_manifest_hash",
            return_value="hashhashhash",
        ),
        patch(
            "transcriptx.services.corrections_studio.generation_manifest.studio_session_rules_fingerprint",
            return_value="rulesfp",
        ),
    ):
        mock_mem.return_value = MagicMock(rules={})
        mock_fuzz.return_value = MagicMock(
            display_names_for_fuzzy=[], observed_named_speakers=[]
        )
        mock_sms.return_value = MagicMock(has_sidecar=False)
        mock_manifest.return_value = GenerationManifest(
            transcript_identity_hash="tk", detector_version="3"
        )
        svc = CorrectionsStudioCandidateService(mock_session)
        result = svc.generate_candidates("sid", force=True)

    assert isinstance(result, GenerateCandidatesResult)
    assert result.commit_aborted is True
    assert result.abort_reason == "event_sequence_conflict"
    assert len(result.candidates) == 1
    assert result.candidates[0].candidate_id == "old"
    assert result.candidates[0].model_dump() == prior.model_dump()

    # Batch was attempted once but did not succeed — no document mutation
    assert mock_session.persist_event_batch.call_count == 1
    mock_session.persist.assert_not_called()
    # load_document still returns the prior doc (unchanged generation)
    assert mock_session.load_document.return_value.current_generation_id == 1
    assert mock_session.load_document.return_value.candidates[0].candidate_id == "old"
