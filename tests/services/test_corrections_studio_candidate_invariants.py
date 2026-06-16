"""Invariant tests for Corrections Studio candidate generation pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.corrections.detect import resolve_segment_id
from transcriptx.core.corrections.models import Candidate as EngineCandidate
from transcriptx.services.corrections_studio.candidate_service import (
    CorrectionsStudioCandidateService,
    _detector_counts_from_candidates,
    _detector_counts_sum,
    _enrich_occurrences,
)
from transcriptx.services.corrections_studio.occurrence_keys import (
    stable_occurrence_key,
)


def _segment(text: str, speaker: str = "Alice", start: float = 0.0, end: float = 1.0):
    return {"text": text, "speaker": speaker, "start": start, "end": end}


@pytest.mark.unit
def test_enrich_occurrences_with_span_uses_stable_key_without_index_suffix() -> None:
    segments = [_segment("hello world")]
    tk = "transcript-key"
    sid = resolve_segment_id(segments[0], tk, segment_index=0)
    wrong = "hello"
    occs = [{"segment_id": sid, "span": [0, 5], "snippet": "hello"}]
    out = _enrich_occurrences(occs, segments, tk, wrong)
    assert len(out) == 1
    assert out[0]["stable_occurrence_key"] == stable_occurrence_key(sid, 0, 5, wrong)


@pytest.mark.unit
def test_enrich_occurrences_without_span_uses_base_key_with_index_suffix() -> None:
    segments = [_segment("hello world")]
    tk = "transcript-key"
    sid = resolve_segment_id(segments[0], tk, segment_index=0)
    wrong = "hello"
    occs = [{"segment_id": sid, "snippet": "hello"}]
    out = _enrich_occurrences(occs, segments, tk, wrong)
    base = stable_occurrence_key(sid, -1, -1, wrong)
    assert out[0]["stable_occurrence_key"] == f"{base}_0"


@pytest.mark.unit
def test_detector_counts_sum_equals_len_for_mixed_kinds() -> None:
    cands = [
        EngineCandidate(
            proposed_wrong="a",
            proposed_right="b",
            kind="memory_hit",
            confidence=0.5,
        ),
        EngineCandidate(
            proposed_wrong="c",
            proposed_right="d",
            kind="acronym",
            confidence=0.6,
        ),
        EngineCandidate(
            proposed_wrong="e",
            proposed_right="f",
            kind="ner_variant",
            confidence=0.7,
        ),
    ]
    post = _detector_counts_from_candidates(cands)
    assert _detector_counts_sum(post) == len(cands)


@pytest.mark.unit
def test_generate_candidates_len_matches_post_dedupe_after_dedupe() -> None:
    """Studio list length must match dedupe output and per-kind totals (mocked pipeline)."""
    from transcriptx.services.corrections_studio.schema import (
        GenerationManifest,
        StudioSessionDocument,
    )

    deduped = [
        EngineCandidate(
            proposed_wrong="w1",
            proposed_right="r1",
            kind="acronym",
            confidence=0.9,
        ),
        EngineCandidate(
            proposed_wrong="w2",
            proposed_right="r2",
            kind="consistency",
            confidence=0.8,
        ),
    ]
    mock_session = MagicMock()
    mock_session.store.read_event_lines.return_value = ["{}"]
    mock_session.next_event_sequence.return_value = 2
    doc = StudioSessionDocument(
        session_id="sid",
        transcript_path="/tmp/x.json",
        recorded_transcript_identity_hash="abc12345",
    )
    mock_session.load_document.return_value = doc

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
            return_value=MagicMock(analysis=MagicMock(corrections=None)),
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
            "transcriptx.services.corrections_studio.candidate_service.dedupe_candidates",
            return_value=deduped,
        ),
        patch(
            "transcriptx.services.corrections_studio.candidate_service.build_generation_manifest",
        ) as mock_manifest,
        patch(
            "transcriptx.services.corrections_studio.candidate_service.compute_generation_manifest_hash",
            return_value="hashhashhash",
        ),
        patch(
            "transcriptx.services.corrections_studio.candidate_service.logger",
        ),
    ):
        mock_mem.return_value = MagicMock(rules={})
        mock_fuzz.return_value = MagicMock(
            display_names_for_fuzzy=[],
            observed_named_speakers=[],
        )
        mock_sms.return_value = MagicMock(has_sidecar=False)
        mock_manifest.return_value = GenerationManifest(
            transcript_identity_hash="tk",
            detector_version="v1",
        )

        svc = CorrectionsStudioCandidateService(mock_session)
        out = svc.generate_candidates("sid", force=True)

    assert len(out) == len(deduped)
    post = _detector_counts_from_candidates(deduped)
    assert _detector_counts_sum(post) == len(out)
