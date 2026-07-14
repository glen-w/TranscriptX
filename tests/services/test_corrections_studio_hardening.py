"""Hardening regressions: abort-on-conflict, export provenance, live LLM staleness."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.store import corrections_session_store as cs
from transcriptx.core.store.corrections_session_store import GenerationCommitConflict
from transcriptx.services.corrections_studio.candidate_service import (
    CorrectionsStudioCandidateService,
    GenerateCandidatesResult,
)
from transcriptx.services.corrections_studio.export_service import (
    CorrectionsStudioExportService,
)
from transcriptx.services.corrections_studio.generation_manifest import (
    compute_llm_fingerprint,
    evaluate_session_staleness,
)
from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    CandidateSource,
    GenerationManifest,
    ReviewAction,
    ReviewStatus,
    StudioCandidate,
    StudioGenerationRecord,
    StudioOccurrence,
    StudioReviewRecord,
    StudioSessionDocument,
    StalenessStatus,
)
from transcriptx.services.corrections_studio.semantic_identity import (
    compute_semantic_identity_key,
)


@pytest.fixture
def iso_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "corrections"
    monkeypatch.setattr(cs, "_CORRECTIONS_ROOT", root)
    return root


@pytest.mark.unit
def test_generate_aborts_when_commit_conflicts() -> None:
    mock_session = MagicMock()
    mock_session.store.read_event_lines.return_value = ["{}"]
    mock_session.next_event_sequence.return_value = 2
    mock_session.last_event_sequence.return_value = 1
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
    mock_session.load_document.return_value = doc
    mock_session.persist_event_batch.side_effect = GenerationCommitConflict(
        "seq conflict", reason="event_sequence_conflict"
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
    assert result.candidates[0].candidate_id == "old"


@pytest.mark.unit
def test_export_provenance_lists_llm_influenced_accepted_only() -> None:
    sem_llm = compute_semantic_identity_key("foo", "bar")
    sem_det = compute_semantic_identity_key("baz", "qux")
    cand_llm = StudioCandidate(
        candidate_id="llm1",
        generation_id=1,
        kind="ner_variant",
        wrong_text="foo",
        right_text="bar",
        sources=[CandidateSource.llm_discovery],
        occurrences=[
            StudioOccurrence(
                segment_id="s0", stable_occurrence_key="k1", span=(0, 3), snippet="foo"
            )
        ],
        semantic_identity_key=sem_llm,
        review_status=ReviewStatus.accepted,
    )
    cand_pending_llm = StudioCandidate(
        candidate_id="llm2",
        generation_id=1,
        kind="ner_variant",
        wrong_text="aaa",
        right_text="bbb",
        sources=[CandidateSource.llm_discovery],
        occurrences=[],
        semantic_identity_key=compute_semantic_identity_key("aaa", "bbb"),
        review_status=ReviewStatus.pending,
    )
    cand_det = StudioCandidate(
        candidate_id="det1",
        generation_id=1,
        kind="consistency",
        wrong_text="baz",
        right_text="qux",
        sources=[CandidateSource.detector_consistency],
        occurrences=[
            StudioOccurrence(
                segment_id="s0", stable_occurrence_key="k2", span=(4, 7), snippet="baz"
            )
        ],
        semantic_identity_key=sem_det,
        review_status=ReviewStatus.accepted,
    )
    # Accept then reject should not count as applied (latest wins).
    reviews = [
        StudioReviewRecord(
            session_id="s",
            generation_id=1,
            candidate_id="llm1",
            review_action=ReviewAction.accept,
            apply_scope=ApplyScope.all,
            recorded_at="t1",
            event_sequence=1,
        ),
        StudioReviewRecord(
            session_id="s",
            generation_id=1,
            candidate_id="llm1",
            review_action=ReviewAction.reject,
            recorded_at="t2",
            event_sequence=2,
        ),
        StudioReviewRecord(
            session_id="s",
            generation_id=1,
            candidate_id="det1",
            review_action=ReviewAction.accept,
            apply_scope=ApplyScope.all,
            recorded_at="t3",
            event_sequence=3,
        ),
    ]
    manifest = GenerationManifest(
        transcript_identity_hash="h",
        detector_version="3",
        llm_fingerprint="fp123",
    )
    doc = StudioSessionDocument(
        session_id="s",
        transcript_path="/t.json",
        recorded_transcript_identity_hash="h",
        current_generation_id=1,
        current_generation=StudioGenerationRecord(
            generation_id=1,
            generation_manifest=manifest,
            generation_manifest_hash="mh",
            completed_at="t",
        ),
        candidates=[cand_llm, cand_pending_llm, cand_det],
        review_records=reviews,
    )

    session = MagicMock()
    session.load_document.return_value = doc
    session.next_event_sequence.return_value = 4
    session.persist = MagicMock()
    preview = MagicMock()
    preview_result = MagicMock()
    preview_result.updated_segments = [{"id": "s0", "text": "bar qux"}]
    preview_result.stats = MagicMock(applied_count=1)
    preview.compute_preview.return_value = preview_result
    export_svc = CorrectionsStudioExportService(session, preview)

    with (
        patch("transcriptx.services.corrections_studio.export_service.save_json"),
        patch(
            "transcriptx.services.corrections_studio.export_service.write_export_provenance"
        ) as write_prov,
        patch("transcriptx.services.corrections_studio.export_service.os.replace"),
    ):
        captured: Dict[str, Any] = {}

        def _capture(path, prov):
            captured["prov"] = prov

        write_prov.side_effect = _capture
        export_svc.apply_and_export("s", export_path="/tmp/out.json")

    prov = captured["prov"]
    assert "llm1" not in prov.applied_candidate_ids  # rejected latest
    assert "det1" in prov.applied_candidate_ids
    assert "llm2" not in prov.applied_candidate_ids
    assert prov.llm_influenced_candidate_ids == []
    assert prov.llm_fingerprint_at_export == "fp123"


@pytest.mark.unit
def test_live_manifest_includes_llm_fingerprint_when_gate_on(monkeypatch) -> None:
    from transcriptx.services.corrections_studio import generation_manifest as gm

    corrections_llm = MagicMock(
        enabled=True,
        effort="low",
        chunk_max_segments=40,
        chunk_overlap_segments=4,
        max_candidates_per_chunk=10,
        max_candidates_per_transcript=80,
        max_chunks=25,
        assess_deterministic=False,
    )
    corrections = MagicMock(llm=corrections_llm)
    llm_cfg = MagicMock(enabled=True, provider="ollama", model="mymodel")
    config = MagicMock(analysis=MagicMock(corrections=corrections), llm=llm_cfg)

    expected_fp = compute_llm_fingerprint(
        model="mymodel",
        effort="low",
        chunk_max_segments=40,
        chunk_overlap_segments=4,
        max_candidates_per_chunk=10,
        max_candidates_per_transcript=80,
        max_chunks=25,
        prompt_version=gm.LLM_PROMPT_VERSION,
        schema_version=gm.LLM_SCHEMA_VERSION,
        context_pack_version=gm.CONTEXT_PACK_VERSION,
        assess_deterministic=False,
    )
    manifest = GenerationManifest(
        transcript_identity_hash="tk",
        detector_version=gm.STUDIO_DETECTOR_VERSION,
        llm_fingerprint=expected_fp,
        llm_prompt_version=gm.LLM_PROMPT_VERSION,
        llm_schema_version=gm.LLM_SCHEMA_VERSION,
        context_pack_version=gm.CONTEXT_PACK_VERSION,
    )
    from transcriptx.services.corrections_studio.identity import (
        compute_generation_manifest_hash,
    )

    mh = compute_generation_manifest_hash(manifest)
    doc = StudioSessionDocument(
        session_id="s",
        transcript_path="/t.json",
        recorded_transcript_identity_hash="tk",
        current_generation_id=1,
        current_generation=StudioGenerationRecord(
            generation_id=1,
            generation_manifest=manifest,
            generation_manifest_hash=mh,
            completed_at="t",
        ),
    )

    monkeypatch.setattr(gm, "get_config", lambda: config)
    monkeypatch.setattr(gm, "load_segments", lambda p: [{"id": "s0", "text": "x"}])
    monkeypatch.setattr(gm, "compute_transcript_identity_hash", lambda s: "tk")
    monkeypatch.setattr(gm, "load_memory", lambda **kw: MagicMock(rules={}))
    monkeypatch.setattr(
        gm, "load_speaker_map_state", lambda p: MagicMock(has_sidecar=False)
    )
    monkeypatch.setattr(gm, "corrections_config_fingerprint", lambda c: "")
    monkeypatch.setattr(gm, "memory_rule_fingerprint", lambda m: "")
    monkeypatch.setattr(gm, "studio_session_rules_fingerprint", lambda r: "")

    status, stale, _ = evaluate_session_staleness(doc)
    assert status == StalenessStatus.ok
    assert stale is False
