"""Stage 4: managed-only profile actions + cache signal (no Streamlit in core)."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from transcriptx.core.speaker_profiles.errors import NotManagedTranscriptError
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.signals import CacheInvalidationSignal
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)
from transcriptx.services.speaker_profiles.create_and_name import (
    create_profile_link_and_name,
)

IMPORT_A = "550e8400-e29b-41d4-a716-446655440000"
CORE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "transcriptx"
    / "core"
    / "speaker_profiles"
)


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


def _write_managed(transcripts_root: Path) -> Path:
    originals = transcripts_root / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    archive_rel = "originals/meeting.srt"
    (transcripts_root / archive_rel).write_text("x", encoding="utf-8")
    segs: list[dict[str, Any]] = [
        {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
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
        TranscriptMetadata(duration_seconds=1.0, segment_count=1, speaker_count=1),
    )
    path = transcripts_root / "meeting.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    write_initial_sidecar(
        path,
        import_id=IMPORT_A,
        imported_at="2026-01-15T10:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="meeting.srt",
        archived_original_relpath=archive_rel,
    )
    return path


class _FakeController:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, str, str]] = []

    def apply_mapping_mutation(
        self, transcript_path: str, speaker_id: str, name: str, method: str = "web"
    ):
        self.calls.append((transcript_path, speaker_id, name))
        if self.fail:
            raise RuntimeError("sidecar write failed")
        return type("S", (), {"speaker_map": {speaker_id: name}, "ignored_speakers": []})()


@pytest.mark.unit
def test_core_speaker_profiles_do_not_import_streamlit() -> None:
    for path in CORE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] != "streamlit", path
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] != "streamlit", path


@pytest.mark.unit
def test_ad_hoc_path_rejected_for_profile_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    _write_managed(transcripts)
    ad_hoc = tmp_path / "run" / "adhoc.json"
    ad_hoc.parent.mkdir()
    ad_hoc.write_text("{}", encoding="utf-8")

    profiles = tmp_path / "speaker_profiles"
    profiles.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    resolver = ManagedTranscriptResolver(
        transcripts_dir=transcripts, discovery_root=transcripts
    )
    svc = SpeakerProfileService(root=profiles, state_dir=state, resolver=resolver)

    with pytest.raises(NotManagedTranscriptError):
        create_profile_link_and_name(
            transcript_path=ad_hoc,
            raw_speaker="SPEAKER_00",
            display_name="Alice",
            service=svc,
            resolver=resolver,
            controller=_FakeController(),
            create_profile=True,
            apply_sidecar_name=False,
        )


@pytest.mark.unit
def test_partial_success_when_naming_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    path = _write_managed(transcripts)
    profiles = tmp_path / "speaker_profiles"
    profiles.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    resolver = ManagedTranscriptResolver(
        transcripts_dir=transcripts, discovery_root=transcripts
    )
    svc = SpeakerProfileService(root=profiles, state_dir=state, resolver=resolver)
    fake = _FakeController(fail=True)

    partial = create_profile_link_and_name(
        transcript_path=path,
        raw_speaker="SPEAKER_00",
        display_name="Alice",
        service=svc,
        resolver=resolver,
        controller=fake,
        operation_idempotency_key=str(uuid4()),
        create_profile=True,
        apply_sidecar_name=True,
    )
    assert partial.mutation is not None
    assert partial.is_partial is True
    assert partial.naming_ok is False
    assert svc.get_profile(partial.mutation.profile_id) is not None
    signal = partial.effective_signal
    assert isinstance(signal, CacheInvalidationSignal)
    assert "speaker_profiles" in signal.scopes


@pytest.mark.unit
def test_consume_signal_clears_listing_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cleared: list[str] = []

    def _clear() -> None:
        cleared.append("listing")

    monkeypatch.setattr(
        "transcriptx.web.cache_helpers.clear_transcript_listing_caches",
        _clear,
    )
    from transcriptx.web.speaker_profile_signals import consume_cache_invalidation_signal

    consume_cache_invalidation_signal(
        CacheInvalidationSignal(scopes=("speaker_profiles", "speaker_links"))
    )
    assert cleared == ["listing"]
