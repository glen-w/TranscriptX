"""Corrections Studio: fuzzy inputs, diagnostics shape, filters, staleness helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.services.corrections_studio.candidate_service import (
    CorrectionsStudioCandidateService,
)
from transcriptx.services.corrections_studio.fuzzy_speaker_inputs import (
    FuzzySpeakerNameResolution,
    compute_fuzzy_skipped_reason,
    compute_speaker_map_fingerprint,
    resolve_fuzzy_speaker_inputs,
)
from transcriptx.services.corrections_studio.generation_manifest import (
    STUDIO_DETECTOR_VERSION,
    evaluate_session_staleness,
    studio_session_rules_fingerprint,
)
from transcriptx.services.corrections_studio.schema import (
    CandidateGenerationDiagnostics,
    DetectorCountsByKind,
    FuzzySkippedReason,
    GenerationManifest,
    StudioGenerationRecord,
    StudioSessionDocument,
)
from transcriptx.services.corrections_studio.service import CorrectionService
from transcriptx.services.corrections_studio.studio_copy import (
    incompatible_transcript_banner_text,
    low_or_zero_candidate_hints,
    stale_generation_banner_lines,
)


def _v1_transcript(segments: list) -> dict:
    return {
        "schema_version": "1.0",
        "source": {
            "type": "manual",
            "original_path": "test.json",
            "imported_at": "2026-01-01T00:00:00Z",
        },
        "segments": segments,
    }


@pytest.mark.unit
def test_compute_fuzzy_skipped_reason_branches() -> None:
    empty = FuzzySpeakerNameResolution(
        display_names_for_fuzzy=[],
        observed_named_speakers=[],
        sidecar_loaded=False,
        map_entries=0,
        load_failed=False,
    )
    assert compute_fuzzy_skipped_reason(False, empty, 0) == FuzzySkippedReason.disabled

    no_map = FuzzySpeakerNameResolution(
        display_names_for_fuzzy=[],
        observed_named_speakers=[],
        sidecar_loaded=False,
        map_entries=0,
        load_failed=True,
    )
    assert (
        compute_fuzzy_skipped_reason(True, no_map, 0)
        == FuzzySkippedReason.no_speaker_map
    )

    zero_ent = FuzzySpeakerNameResolution(
        display_names_for_fuzzy=[],
        observed_named_speakers=[],
        sidecar_loaded=True,
        map_entries=0,
        load_failed=False,
    )
    assert (
        compute_fuzzy_skipped_reason(True, zero_ent, 0)
        == FuzzySkippedReason.zero_map_entries
    )

    zero_named = FuzzySpeakerNameResolution(
        display_names_for_fuzzy=[],
        observed_named_speakers=[],
        sidecar_loaded=True,
        map_entries=2,
        load_failed=False,
    )
    assert (
        compute_fuzzy_skipped_reason(True, zero_named, 0)
        == FuzzySkippedReason.zero_named_speakers
    )

    ok = FuzzySpeakerNameResolution(
        display_names_for_fuzzy=["Alice Smith"],
        observed_named_speakers=[],
        sidecar_loaded=True,
        map_entries=1,
        load_failed=False,
    )
    assert (
        compute_fuzzy_skipped_reason(True, ok, 1) == FuzzySkippedReason.not_applicable
    )


@pytest.mark.unit
def test_speaker_map_fingerprint_stable_for_identical_map() -> None:
    from transcriptx.io.speaker_map_resolver import SpeakerMapState

    m = SpeakerMapState(
        has_sidecar=True,
        speaker_map={"SPEAKER_00": "Alice Smith", "SPEAKER_01": "Bob Jones"},
    )
    assert compute_speaker_map_fingerprint(m) == compute_speaker_map_fingerprint(m)


@pytest.mark.unit
def test_studio_session_rules_fingerprint_order_independent() -> None:
    from transcriptx.services.corrections_studio.schema import StudioRule

    r1 = StudioRule(
        rule_id="b", rule_type="phrase", wrong_variants=["x"], replacement_text="y"
    )
    r2 = StudioRule(
        rule_id="a", rule_type="phrase", wrong_variants=["z"], replacement_text="w"
    )
    fp_ab = studio_session_rules_fingerprint({"b": r1, "a": r2})
    fp_ba = studio_session_rules_fingerprint({"a": r2, "b": r1})
    assert fp_ab == fp_ba


@pytest.mark.unit
def test_evaluate_session_staleness_legacy_manifest_no_crash() -> None:
    old_manifest = GenerationManifest(
        transcript_identity_hash="oldhash",
        detector_version="1",
        corrections_config_fingerprint="",
        memory_rule_fingerprint="",
        speaker_map_fingerprint="",
        studio_session_rules_fingerprint="",
    )
    doc = StudioSessionDocument(
        session_id="s",
        transcript_path="/nonexistent/transcript.json",
        recorded_transcript_identity_hash="oldhash",
        current_generation=StudioGenerationRecord(
            generation_id=1,
            generation_manifest=old_manifest,
            generation_manifest_hash="deadbeef",
            completed_at="2020-01-01T00:00:00Z",
        ),
    )
    status, gen_stale, _ = evaluate_session_staleness(doc)
    assert status.value in ("stale_generation", "incompatible_transcript")
    assert gen_stale is True


@pytest.mark.unit
def test_list_candidates_default_filters_match_unfiltered() -> None:
    svc = CorrectionService()
    session_id = "fake-session-list"
    doc = StudioSessionDocument(
        session_id=session_id,
        transcript_path="/tmp/x.json",
        recorded_transcript_identity_hash="fp",
        candidates=[],
    )
    with patch.object(
        svc._session_svc,
        "load_document",
        return_value=doc,
    ):
        base = svc.list_candidates(session_id)
        explicit = svc.list_candidates(
            session_id,
            status_filter=None,
            kind_filter=[],
            confidence_min=None,
        )
        assert [c.model_dump(mode="json") for c in base] == [
            c.model_dump(mode="json") for c in explicit
        ]


@pytest.mark.unit
def test_low_candidate_hints_only_consistency_line() -> None:
    post = DetectorCountsByKind(consistency=2, memory_hit=0, acronym=0, fuzzy=0)
    diag = CandidateGenerationDiagnostics(
        pre_dedupe=DetectorCountsByKind(
            consistency=2, memory_hit=0, acronym=0, fuzzy=0, ner_variant=0, other=0
        ),
        total_pre_dedupe=2,
        post_dedupe_counts_by_kind=post,
        total_after_dedupe=2,
        fuzzy_enabled=False,
        fuzzy_named_speaker_count=0,
        fuzzy_skipped_reason=FuzzySkippedReason.disabled,
        observed_named_speaker_count=0,
    )
    hints = low_or_zero_candidate_hints(diag)
    assert any("consistency" in h and "All current" in h for h in hints)


@pytest.mark.unit
def test_resolve_fuzzy_from_sidecar(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    sidecar = tmp_path / "t.speaker_map.json"
    transcript.write_text(
        json.dumps(
            _v1_transcript(
                [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "Hello Alicesmith typo",
                        "start": 0.0,
                        "end": 1.0,
                    },
                ]
            )
        ),
        encoding="utf-8",
    )
    sidecar.write_text(
        json.dumps(
            {
                "speaker_map": {"SPEAKER_00": "Alice Smith"},
                "ignored_speakers": [],
            }
        ),
        encoding="utf-8",
    )
    from transcriptx.io import load_segments

    segments = load_segments(str(transcript))
    res = resolve_fuzzy_speaker_inputs(str(transcript), segments)
    assert res.sidecar_loaded is True
    assert "Alice Smith" in res.display_names_for_fuzzy


@pytest.mark.unit
def test_generate_candidates_passes_fuzzy_names(tmp_path: Path) -> None:
    transcript = tmp_path / "t2.json"
    sidecar = tmp_path / "t2.speaker_map.json"
    transcript.write_text(
        json.dumps(
            _v1_transcript(
                [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "Alicia met Alice",
                        "start": 0.0,
                        "end": 1.0,
                    },
                ]
            )
        ),
        encoding="utf-8",
    )
    sidecar.write_text(
        json.dumps(
            {"speaker_map": {"SPEAKER_00": "Alice Smith"}, "ignored_speakers": []}
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
    mock_session_svc = MagicMock()
    mock_session_svc.store.read_event_lines.return_value = ["{}"]
    mock_session_svc.load_document.return_value = doc
    mock_session_svc.last_event_sequence.return_value = 1

    captured: dict = {}

    def persist_batch(tp, d, events, preconditions=None):
        captured["doc"] = d
        return events

    mock_session_svc.persist_event_batch.side_effect = persist_batch
    mock_session_svc.next_event_sequence.return_value = 2

    with patch(
        "transcriptx.services.corrections_studio.candidate_service.get_config"
    ) as mock_cfg:
        corrections = MagicMock()
        corrections.known_acronyms = []
        corrections.known_org_phrases = {}
        corrections.consistency_similarity_threshold = 0.99
        corrections.fuzzy_similarity_threshold = 0.5
        corrections.enable_fuzzy = True
        corrections.llm = MagicMock(enabled=False)
        mock_cfg.return_value.analysis.corrections = corrections
        mock_cfg.return_value.llm = MagicMock(enabled=False)

        with patch(
            "transcriptx.services.corrections_studio.candidate_service.load_memory"
        ) as lm:
            mem = MagicMock()
            mem.rules = {}
            lm.return_value = mem

            svc = CorrectionsStudioCandidateService(mock_session_svc)
            svc.generate_candidates("sid", force=True)

    out = captured["doc"]
    assert out.current_generation is not None
    diag = out.current_generation.generation_diagnostics
    assert diag is not None
    assert diag.fuzzy_enabled is True
    assert diag.fuzzy_named_speaker_count >= 1
    assert (
        out.current_generation.generation_manifest.detector_version
        == STUDIO_DETECTOR_VERSION
    )


@pytest.mark.unit
def test_generation_diagnostics_totals_match_post_counts() -> None:
    post = DetectorCountsByKind(
        memory_hit=1, acronym=2, consistency=3, fuzzy=0, ner_variant=0, other=0
    )
    diag = CandidateGenerationDiagnostics(
        pre_dedupe=DetectorCountsByKind(
            memory_hit=1,
            acronym=2,
            consistency=3,
            fuzzy=0,
            ner_variant=0,
            other=0,
        ),
        total_pre_dedupe=6,
        post_dedupe_counts_by_kind=post,
        total_after_dedupe=6,
        fuzzy_enabled=False,
        fuzzy_named_speaker_count=0,
        fuzzy_skipped_reason=FuzzySkippedReason.disabled,
        observed_named_speaker_count=0,
    )
    assert diag.total_after_dedupe == sum(
        (
            post.memory_hit,
            post.acronym,
            post.consistency,
            post.fuzzy,
            post.ner_variant,
            post.other,
        )
    )


@pytest.mark.unit
def test_stale_generation_banner_lines_include_generation_and_detector() -> None:
    lines = stale_generation_banner_lines(
        generation_id=7,
        completed_at="2026-01-01T00:00:00Z",
        detector_version="2",
    )
    assert any("#7" in ln for ln in lines)
    assert any("detector" in ln.lower() for ln in lines)


@pytest.mark.unit
def test_incompatible_transcript_banner_non_empty() -> None:
    assert len(incompatible_transcript_banner_text()) > 20


@pytest.mark.unit
def test_low_or_zero_hints_fuzzy_no_speaker_map() -> None:
    diag = CandidateGenerationDiagnostics(
        pre_dedupe=DetectorCountsByKind(),
        total_pre_dedupe=0,
        post_dedupe_counts_by_kind=DetectorCountsByKind(),
        total_after_dedupe=0,
        fuzzy_enabled=True,
        fuzzy_named_speaker_count=0,
        fuzzy_skipped_reason=FuzzySkippedReason.no_speaker_map,
        observed_named_speaker_count=0,
    )
    hints = low_or_zero_candidate_hints(diag)
    assert any("speaker map" in h.lower() for h in hints)


@pytest.mark.unit
def test_low_or_zero_hints_fuzzy_zero_named_speakers() -> None:
    diag = CandidateGenerationDiagnostics(
        pre_dedupe=DetectorCountsByKind(),
        total_pre_dedupe=0,
        post_dedupe_counts_by_kind=DetectorCountsByKind(),
        total_after_dedupe=0,
        fuzzy_enabled=True,
        fuzzy_named_speaker_count=0,
        fuzzy_skipped_reason=FuzzySkippedReason.zero_named_speakers,
        observed_named_speaker_count=0,
    )
    hints = low_or_zero_candidate_hints(diag)
    assert any("named" in h.lower() for h in hints)


@pytest.mark.unit
def test_low_or_zero_hints_fuzzy_zero_map_entries() -> None:
    diag = CandidateGenerationDiagnostics(
        pre_dedupe=DetectorCountsByKind(),
        total_pre_dedupe=0,
        post_dedupe_counts_by_kind=DetectorCountsByKind(),
        total_after_dedupe=0,
        fuzzy_enabled=True,
        fuzzy_named_speaker_count=0,
        fuzzy_skipped_reason=FuzzySkippedReason.zero_map_entries,
        observed_named_speaker_count=0,
    )
    hints = low_or_zero_candidate_hints(diag)
    assert any("empty" in h.lower() for h in hints)


@pytest.mark.unit
def test_low_or_zero_hints_fuzzy_named_vocabulary_line() -> None:
    diag = CandidateGenerationDiagnostics(
        pre_dedupe=DetectorCountsByKind(fuzzy=1),
        total_pre_dedupe=1,
        post_dedupe_counts_by_kind=DetectorCountsByKind(fuzzy=1),
        total_after_dedupe=1,
        fuzzy_enabled=True,
        fuzzy_named_speaker_count=3,
        fuzzy_skipped_reason=FuzzySkippedReason.not_applicable,
        observed_named_speaker_count=0,
    )
    hints = low_or_zero_candidate_hints(diag)
    assert any("3" in h and "named speaker" in h for h in hints)


@pytest.mark.unit
def test_load_session_returns_document_with_staleness_fields() -> None:
    svc = CorrectionService()
    session_id = "sess-stale-api"
    doc = StudioSessionDocument(
        session_id=session_id,
        transcript_path="/tmp/missing.json",
        recorded_transcript_identity_hash="abc",
        current_generation=StudioGenerationRecord(
            generation_id=1,
            generation_manifest=GenerationManifest(
                transcript_identity_hash="abc",
                detector_version="0",
                corrections_config_fingerprint="",
                memory_rule_fingerprint="",
            ),
            generation_manifest_hash="x",
            completed_at="2020-01-01T00:00:00Z",
        ),
        candidates=[],
    )
    with patch.object(
        svc.repo, "find_by_session_id", return_value=doc.model_dump(mode="json")
    ):
        out = svc.load_session(session_id)
    assert out is not None
    assert hasattr(out.staleness_status, "value")
    assert isinstance(out.candidates_stale, bool)
    assert isinstance(out.generation_inputs_stale, bool)
