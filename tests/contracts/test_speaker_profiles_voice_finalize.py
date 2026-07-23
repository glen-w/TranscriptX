"""Finalize / residual coverage for voice Stage 8 exit."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.layout import iter_paths_for_ordinary_backup
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.errors import StaleConfirmationError
from transcriptx.core.speaker_profiles.voice.acceptance import (
    AcceptSuggestionRequest,
    VoiceAcceptanceOwner,
)
from transcriptx.core.speaker_profiles.voice.match_service import SpeakerMatchService
from transcriptx.core.speaker_profiles.voice.runtime import (
    EmbeddingBatchResult,
    EmbeddingRuntimeMeta,
)
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


def test_accept_same_owner_supersede_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same owner + fingerprint drift uses supersede in one journalled accept."""
    svc, profiles = _svc(tmp_path, monkeypatch)
    alice = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    link = svc.get_live_link(link_file_key(IMPORT_A, "SPEAKER_00"))
    assert link is not None
    # Force stored fingerprint behind live occurrence by rewriting via supersede noop path:
    # accept with matching expected_fingerprint but candidate same owner → supersede branch.
    owner = VoiceAcceptanceOwner(
        root=profiles, state_dir=tmp_path / "state", profile_service=svc
    )
    result = owner.accept_suggestion(
        AcceptSuggestionRequest(
            operation_idempotency_key=str(uuid4()),
            managed_transcript_id=IMPORT_A,
            local_speaker_key="SPEAKER_00",
            candidate_profile_id=alice.profile_id,
            suggestion_id="s1",
            suggestion_digest="d1",
            confidence_category="strong",
            model_generation_id="g",
            occurrence_fingerprint=link.occurrence_fingerprint,
            expected_link_id=link.link_id,
            expected_owner_profile_id=alice.profile_id,
            expected_fingerprint=link.occurrence_fingerprint,
        ),
        require_activation=False,
    )
    assert result.decision_id is not None
    decision = profiles / "voice" / "decisions" / f"{result.decision_id}.voice_decision.json"
    assert decision.is_file()
    updated = svc.get_live_link(link_file_key(IMPORT_A, "SPEAKER_00"))
    assert updated is not None
    assert updated.profile_id == alice.profile_id


def test_project_lock_helper_shared_sentinel(tmp_path: Path) -> None:
    from transcriptx.core.speaker_profiles.layout import (
        speaker_profiles_lock_path,
        speaker_profiles_project_lock,
    )

    state = tmp_path / "state"
    state.mkdir()
    lock_a = speaker_profiles_project_lock(state)
    lock_b = speaker_profiles_project_lock(state)
    assert lock_a.file_path == lock_b.file_path
    assert lock_a.file_path == speaker_profiles_lock_path(state).with_suffix(
        ".lock.target"
    )


def test_layout_backup_inventory_excludes_voice(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    (root / "profiles").mkdir(parents=True)
    (root / "voice" / "samples").mkdir(parents=True)
    (root / "profiles" / "a.speaker_profile.json").write_text("{}", encoding="utf-8")
    (root / "voice" / "samples" / "x.voice_sample.json").write_text(
        "{}", encoding="utf-8"
    )
    (root / ".cache" / "voice" / "q.npy").parent.mkdir(parents=True)
    (root / ".cache" / "voice" / "q.npy").write_bytes(b"x")
    paths = iter_paths_for_ordinary_backup(root)
    rels = [p.relative_to(root).as_posix() for p in paths]
    assert "profiles/a.speaker_profile.json" in rels
    assert not any(r.startswith("voice/") for r in rels)
    assert not any(r.startswith(".cache/voice/") for r in rels)


def test_accept_relink_other_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, profiles = _svc(tmp_path, monkeypatch)
    alice = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    bob = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Bob",
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
    )
    link = svc.get_live_link(link_file_key(IMPORT_A, "SPEAKER_00"))
    assert link is not None
    owner = VoiceAcceptanceOwner(
        root=profiles, state_dir=tmp_path / "state", profile_service=svc
    )
    result = owner.accept_suggestion(
        AcceptSuggestionRequest(
            operation_idempotency_key=str(uuid4()),
            managed_transcript_id=IMPORT_A,
            local_speaker_key="SPEAKER_00",
            candidate_profile_id=bob.profile_id,
            suggestion_id="s1",
            suggestion_digest="d1",
            confidence_category="possible",
            model_generation_id="g",
            occurrence_fingerprint=link.occurrence_fingerprint,
            expected_link_id=link.link_id,
            expected_owner_profile_id=alice.profile_id,
            expected_fingerprint=link.occurrence_fingerprint,
        ),
        require_activation=False,
    )
    assert result.decision_id is not None
    updated = svc.get_live_link(link_file_key(IMPORT_A, "SPEAKER_00"))
    assert updated is not None
    assert updated.profile_id == bob.profile_id


def test_accept_stale_audio_precondition(
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
        root=profiles, state_dir=tmp_path / "state", profile_service=svc
    )
    with pytest.raises(StaleConfirmationError, match="audio"):
        owner.accept_suggestion(
            AcceptSuggestionRequest(
                operation_idempotency_key=str(uuid4()),
                managed_transcript_id=IMPORT_A,
                local_speaker_key="SPEAKER_01",
                candidate_profile_id=alice.profile_id,
                suggestion_id="s1",
                suggestion_digest="d1",
                confidence_category="possible",
                model_generation_id="g",
                occurrence_fingerprint="fp",
                expected_audio_stat_fingerprint="fastsha256:missing:0",
                expected_audio_content_sha256="sha256:missing",
            ),
            require_activation=False,
        )


class _SlowRuntime:
    def embed_wav_paths(self, wav_paths):  # noqa: ANN001
        time.sleep(0.15)
        vec = np.ones(192, dtype=np.float32)
        vec = vec / np.linalg.norm(vec)
        meta = EmbeddingRuntimeMeta(
            device_class="cpu",
            embedding_schema_version="1",
            preprocessing_policy_id="p",
            speechbrain_version=None,
            torch_version=None,
        )
        return EmbeddingBatchResult(vectors=(vec,), meta=meta)


def test_lock_released_during_embed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Project lock must be free while embedding runs (mock delayed runtime)."""
    _, profiles = _svc(tmp_path, monkeypatch)
    state = tmp_path / "state"
    from transcriptx.core.speaker_profiles.voice.privacy_service import VoicePrivacyService

    VoicePrivacyService(root=profiles, state_dir=state).enable(
        operation_idempotency_key=str(uuid4()),
        require_feature_gate=False,
    )
    held_during_embed = {"value": False}

    match = SpeakerMatchService(
        root=profiles, state_dir=state, runtime=_SlowRuntime()  # type: ignore[arg-type]
    )

    # Probe: while embed sleeps, another thread can acquire the *same* project lock.
    from transcriptx.core.speaker_profiles.layout import speaker_profiles_project_lock

    def try_lock() -> None:
        time.sleep(0.02)
        with speaker_profiles_project_lock(state):
            held_during_embed["value"] = True

    from transcriptx.core.speaker_profiles.voice import match_service as ms

    class FakeSelection:
        outcome = "ok"
        one_excerpt_fallback = False
        excerpts = [
            type(
                "P",
                (),
                {
                    "start_us": 0,
                    "end_us": 1_500_000,
                    "start": 0.0,
                    "end": 1.5,
                },
            )()
        ]

    monkeypatch.setattr(ms, "select_excerpts_v1", lambda *a, **k: FakeSelection())

    class FakeAudio:
        audio_path = tmp_path / "a.wav"
        audio_stat_fingerprint = "fastsha256:1:1"
        audio_content_sha256 = "sha256:abc"

    FakeAudio.audio_path.write_bytes(b"RIFF")

    monkeypatch.setattr(
        ms,
        "resolve_managed_transcript_audio",
        lambda *a, **k: FakeAudio(),
    )
    monkeypatch.setattr(ms, "verify_audio_unchanged", lambda *a, **k: None)

    class FakeExcerptStore:
        def get_or_extract(self, **kwargs):  # noqa: ANN003
            p = tmp_path / "clip.wav"
            p.write_bytes(b"RIFF")
            return p

    match.excerpts = FakeExcerptStore()  # type: ignore[assignment]

    # Pre-warm generation under lock so snapshot is short
    from transcriptx.core.speaker_profiles.voice.generations import VoiceGenerationRegistry

    VoiceGenerationRegistry(profiles).ensure_default_generation_and_activate(
        operation_idempotency_key=str(uuid4())
    )

    t = threading.Thread(target=try_lock)
    t.start()
    match.analyse_occurrence(
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
        transcript_path=tmp_path / "transcripts" / "meeting.json",
        segments=[
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 10.0, "text": "x"}
        ],
        occurrence_fingerprint="fp",
        require_activation=True,
    )
    t.join(timeout=2.0)
    assert held_during_embed["value"] is True
