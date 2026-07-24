"""LLM-off generate_candidates golden — fixed fixture, exact diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.services.corrections_studio.candidate_service import (
    CorrectionsStudioCandidateService,
    GenerateCandidatesResult,
)
from transcriptx.services.corrections_studio.generation_manifest import (
    STUDIO_DETECTOR_VERSION,
)
from transcriptx.services.corrections_studio.schema import StudioSessionDocument


def _v1_transcript(segments: list) -> dict:
    return {
        "schema_version": 1,
        "source": {
            "type": "manual",
            "original_path": "test.json",
            "imported_at": "2026-01-01T00:00:00Z",
        },
        "segments": segments,
    }


@pytest.mark.unit
def test_generate_candidates_llm_off_golden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "golden.json"
    # Fixed bait: spaced letters match acronym detector; fuzzy off; no memory rules.
    transcript.write_text(
        json.dumps(
            _v1_transcript(
                [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "The N A S A team landed",
                        "start": 0.0,
                        "end": 1.0,
                    },
                    {
                        "speaker": "SPEAKER_00",
                        "text": "Mission control confirmed",
                        "start": 1.0,
                        "end": 2.0,
                    },
                ]
            )
        ),
        encoding="utf-8",
    )

    doc = StudioSessionDocument(
        session_id="sid",
        transcript_path=str(transcript),
        recorded_transcript_identity_hash="x",
        candidates=[],
        current_generation_id=None,
    )
    mock_session = MagicMock()
    mock_session.store.read_event_lines.return_value = ["{}"]
    mock_session.load_document.return_value = doc
    mock_session.last_event_sequence.return_value = 1
    mock_session.next_event_sequence.return_value = 2
    captured: dict = {}

    def persist_batch(_tp, d, events, preconditions=None):
        captured["doc"] = d
        captured["events"] = events
        return list(d.candidates)

    mock_session.persist_event_batch.side_effect = persist_batch

    from transcriptx.services.corrections_studio.llm import discovery as disc

    built = {"n": 0}

    def _boom(**_kwargs):
        built["n"] += 1
        raise AssertionError("client should not be built when LLM is off")

    monkeypatch.setattr(disc, "build_ollama_analysis_client", _boom)

    with (
        patch(
            "transcriptx.services.corrections_studio.candidate_service.get_config"
        ) as mock_cfg,
        patch(
            "transcriptx.services.corrections_studio.candidate_service.load_memory"
        ) as lm,
    ):
        corrections = MagicMock()
        corrections.known_acronyms = ["NASA"]
        corrections.known_org_phrases = {}
        corrections.consistency_similarity_threshold = 0.99
        corrections.fuzzy_similarity_threshold = 0.85
        corrections.enable_fuzzy = False
        corrections.llm = MagicMock(enabled=False)
        mock_cfg.return_value.analysis.corrections = corrections
        mock_cfg.return_value.llm = MagicMock(enabled=False)
        mem = MagicMock()
        mem.rules = {}
        lm.return_value = mem

        svc = CorrectionsStudioCandidateService(mock_session)
        out = svc.generate_candidates("sid", force=True)

    assert isinstance(out, GenerateCandidatesResult)
    assert out.commit_aborted is False
    assert built["n"] == 0

    gen = captured["doc"].current_generation
    assert gen is not None
    diag = gen.generation_diagnostics
    man = gen.generation_manifest

    assert diag.total_after_dedupe == len(out.candidates)
    # Fixed fixture expectations (detectors with fuzzy off, known acronym NASA, "teh")
    counts = diag.post_dedupe_counts_by_kind
    assert counts.memory_hit == 0
    assert counts.fuzzy == 0
    assert counts.acronym >= 1
    assert counts.consistency >= 0
    assert diag.total_after_dedupe == (
        counts.memory_hit
        + counts.acronym
        + counts.consistency
        + counts.fuzzy
        + counts.ner_variant
        + counts.other
    )

    assert gen.generation_manifest_hash
    assert len(gen.generation_manifest_hash) >= 16
    assert man.detector_version == STUDIO_DETECTOR_VERSION
    assert man.llm_fingerprint == ""
    assert man.llm_prompt_version == ""
    assert man.llm_schema_version == ""
    assert man.context_pack_version == ""

    assert diag.llm is not None
    assert diag.llm.enabled is False
    assert diag.llm.attempted is False
    assert diag.llm.available is False
    assert diag.llm.outcome == "skipped"
    assert diag.llm.candidates_raw == 0
    assert diag.llm.chunks_total == 0

    # Re-run with same fixture must keep stable manifest hash for same inputs
    hash1 = gen.generation_manifest_hash
    mock_session.load_document.return_value = StudioSessionDocument(
        session_id="sid",
        transcript_path=str(transcript),
        recorded_transcript_identity_hash="x",
        candidates=[],
        current_generation_id=None,
    )
    with (
        patch(
            "transcriptx.services.corrections_studio.candidate_service.get_config"
        ) as mock_cfg,
        patch(
            "transcriptx.services.corrections_studio.candidate_service.load_memory"
        ) as lm,
    ):
        corrections = MagicMock()
        corrections.known_acronyms = ["NASA"]
        corrections.known_org_phrases = {}
        corrections.consistency_similarity_threshold = 0.99
        corrections.fuzzy_similarity_threshold = 0.85
        corrections.enable_fuzzy = False
        corrections.llm = MagicMock(enabled=False)
        mock_cfg.return_value.analysis.corrections = corrections
        mock_cfg.return_value.llm = MagicMock(enabled=False)
        mem = MagicMock()
        mem.rules = {}
        lm.return_value = mem
        out2 = CorrectionsStudioCandidateService(mock_session).generate_candidates(
            "sid", force=True
        )
    hash2 = captured["doc"].current_generation.generation_manifest_hash
    assert hash1 == hash2
    assert len(out2.candidates) == len(out.candidates)
