"""Fault-injection and atomic-accept tests for voice Stage 8."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.integrity import run_integrity_scan
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.voice.acceptance import (
    AcceptSuggestionRequest,
    VoiceAcceptanceOwner,
)
from transcriptx.core.speaker_profiles.voice.evidence import (
    EnrolExcerptInput,
    VoiceEvidenceService,
)
from transcriptx.core.speaker_profiles.voice.privacy_service import VoicePrivacyService
from transcriptx.core.speaker_profiles.voice.wipe import VoiceWipeService
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)

IMPORT_A = "550e8400-e29b-41d4-a716-446655440000"
IMPORT_B = "660e8400-e29b-41d4-a716-446655440001"


def _patch_roots(monkeypatch: pytest.MonkeyPatch, transcripts_root: Path) -> None:
    metadata_dir = transcripts_root / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR",
        transcripts_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR",
        metadata_dir,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.file_discovery.DIARISED_TRANSCRIPTS_DIR",
        transcripts_root,
    )


def _write_managed(transcripts_root: Path, *, name: str, import_id: str) -> None:
    originals = transcripts_root / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    archive_rel = f"originals/{name}.srt"
    (transcripts_root / archive_rel).write_text("x", encoding="utf-8")
    segs = [
        {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
        {"speaker": "SPEAKER_01", "text": "World", "start": 1.0, "end": 2.0},
    ]
    doc = create_transcript_document(
        segs,
        SourceInfo(
            type="srt",
            original_path=archive_rel,
            imported_at="2026-01-15T10:00:00+00:00",
            file_hash="abc",
            file_mtime=0.0,
        ),
        TranscriptMetadata(duration_seconds=2.0, segment_count=2, speaker_count=2),
    )
    path = transcripts_root / f"{name}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    write_initial_sidecar(
        path,
        import_id=import_id,
        imported_at="2026-01-15T10:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename=f"{name}.srt",
        archived_original_relpath=archive_rel,
    )


def _svc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[SpeakerProfileService, Path]:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    _write_managed(transcripts, name="meeting", import_id=IMPORT_A)
    _write_managed(transcripts, name="other", import_id=IMPORT_B)
    profiles = tmp_path / "speaker_profiles"
    state = tmp_path / "state"
    profiles.mkdir()
    state.mkdir()
    resolver = ManagedTranscriptResolver(
        transcripts_dir=transcripts, discovery_root=transcripts
    )
    return (
        SpeakerProfileService(root=profiles, state_dir=state, resolver=resolver),
        profiles,
    )


def test_accept_is_single_journalled_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    alice = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    owner = VoiceAcceptanceOwner(
        root=profiles,
        state_dir=tmp_path / "state",
        profile_service=svc,
    )
    op_key = str(uuid4())
    result = owner.accept_suggestion(
        AcceptSuggestionRequest(
            operation_idempotency_key=op_key,
            managed_transcript_id=IMPORT_B,
            local_speaker_key="SPEAKER_00",
            candidate_profile_id=alice.profile_id,
            suggestion_id="s1",
            suggestion_digest="d1",
            confidence_category="possible",
            model_generation_id="g",
            occurrence_fingerprint="fp",
        ),
        require_activation=False,
    )
    assert result.decision_id is not None
    assert result.mutation is not None
    decision_path = (
        profiles / "voice" / "decisions" / f"{result.decision_id}.voice_decision.json"
    )
    assert decision_path.is_file()
    link = svc.get_live_link(link_file_key(IMPORT_B, "SPEAKER_00"))
    assert link is not None
    assert link.profile_id == alice.profile_id
    # Single op key — no :link / :decision siblings
    ops = list((profiles / "operations").glob("*.op.json"))
    matching = []
    for path in ops:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("operation_idempotency_key") == op_key:
            matching.append(payload)
    assert len(matching) == 1
    # Idempotent replay
    again = owner.accept_suggestion(
        AcceptSuggestionRequest(
            operation_idempotency_key=op_key,
            managed_transcript_id=IMPORT_B,
            local_speaker_key="SPEAKER_00",
            candidate_profile_id=alice.profile_id,
            suggestion_id="s1",
            suggestion_digest="d1",
            confidence_category="possible",
            model_generation_id="g",
            occurrence_fingerprint="fp",
        ),
        require_activation=False,
    )
    assert again.decision_id == result.decision_id


def test_leave_unlinked_writes_no_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, profiles = _svc(tmp_path, monkeypatch)
    owner = VoiceAcceptanceOwner(root=profiles, state_dir=tmp_path / "state")
    result = owner.leave_unlinked()
    assert result.decision_id is None
    decisions = profiles / "voice" / "decisions"
    if decisions.is_dir():
        assert not list(decisions.glob("*.json"))


def test_wipe_clears_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    evidence = VoiceEvidenceService(root=profiles, state_dir=tmp_path / "state")
    evidence.enrol_trusted_excerpts_from_link(
        operation_idempotency_key=str(uuid4()),
        link_file_key_value=link_file_key(IMPORT_A, "SPEAKER_00"),
        excerpts=[
            EnrolExcerptInput(
                clip_start_us=0,
                clip_end_us=1_500_000,
                audio_stat_fingerprint="fastsha256:1:2",
                audio_content_sha256="sha256:y",
                vector=np.ones(192, dtype=np.float32),
                runtime_metadata={},
                model_id="m",
                model_revision="r",
                model_generation_id="g",
            )
        ],
        require_activation=False,
    )
    wipe = VoiceWipeService(root=profiles, state_dir=tmp_path / "state")
    progress = wipe.wipe_until_complete(base_idempotency_key=str(uuid4()))
    assert progress.complete is True
    assert not (profiles / "voice" / "wipe_receipt.json").exists()
    report = run_integrity_scan(profiles)
    assert "wipe_incomplete" not in " ".join(report.voice_issues)
    assert "wipe_receipt_stale" not in " ".join(report.voice_issues)


def test_revoke_chains_wipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    evidence = VoiceEvidenceService(root=profiles, state_dir=tmp_path / "state")
    evidence.enrol_trusted_excerpts_from_link(
        operation_idempotency_key=str(uuid4()),
        link_file_key_value=link_file_key(IMPORT_A, "SPEAKER_00"),
        excerpts=[
            EnrolExcerptInput(
                clip_start_us=0,
                clip_end_us=1_500_000,
                audio_stat_fingerprint="fastsha256:1:2",
                audio_content_sha256="sha256:y",
                vector=np.ones(192, dtype=np.float32),
                runtime_metadata={},
                model_id="m",
                model_revision="r",
                model_generation_id="g",
            )
        ],
        require_activation=False,
    )
    privacy = VoicePrivacyService(root=profiles, state_dir=tmp_path / "state")
    privacy.enable(
        operation_idempotency_key=str(uuid4()),
        require_feature_gate=False,
    )
    settings, _ = privacy.revoke(operation_idempotency_key=str(uuid4()))
    assert settings.enabled is False
    assert settings.wipe_required is False
    assert not list((profiles / "voice" / "samples").glob("*.json"))
    # Profile link preserved
    assert svc.get_live_link(link_file_key(IMPORT_A, "SPEAKER_00")) is not None


def test_integrity_flags_incomplete_wipe(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    (root / "voice").mkdir(parents=True)
    (root / "voice" / "wipe_receipt.json").write_text(
        json.dumps({"pending_paths": ["voice/samples/a.voice_sample.json"]}),
        encoding="utf-8",
    )
    report = run_integrity_scan(root)
    assert any(i.startswith("wipe_incomplete:") for i in report.voice_issues)
    assert report.ok is False
