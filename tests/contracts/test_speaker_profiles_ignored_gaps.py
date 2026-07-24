"""Plan-gap deepeners: ignored-link rejection + ignored headline exclusion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from transcriptx.core.speaker_profiles.aggregates import (
    aggregate_profile,
    list_profile_links,
)
from transcriptx.core.speaker_profiles.errors import IgnoredSpeakerLinkError
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.speaker_map_resolver import SpeakerMapState
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)

IMPORT_A = "550e8400-e29b-41d4-a716-446655440000"


class _IgnoredMapResolver:
    def load_mapping(self, transcript_path: str | Path) -> SpeakerMapState:
        return SpeakerMapState(
            has_sidecar=True,
            speaker_map={},
            ignored_speakers=["SPEAKER_00"],
        )


def _patch(monkeypatch: pytest.MonkeyPatch, transcripts: Path) -> None:
    metadata = transcripts / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR", transcripts
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.file_discovery.DIARISED_TRANSCRIPTS_DIR", transcripts
    )


def _managed(transcripts: Path) -> Path:
    originals = transcripts / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    archive_rel = "originals/meeting.srt"
    (transcripts / archive_rel).write_text("x", encoding="utf-8")
    segs: list[dict[str, Any]] = [
        {"speaker": "SPEAKER_00", "text": "Hello world", "start": 0.0, "end": 2.0},
        {"speaker": "SPEAKER_01", "text": "Hi there", "start": 2.0, "end": 4.0},
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
        TranscriptMetadata(duration_seconds=4.0, segment_count=2, speaker_count=2),
    )
    path = transcripts / "meeting.json"
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


def _svc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    ignored: bool = False,
) -> SpeakerProfileService:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch(monkeypatch, transcripts)
    _managed(transcripts)
    profiles = tmp_path / "speaker_profiles"
    state = tmp_path / "state"
    profiles.mkdir()
    state.mkdir()
    resolver = ManagedTranscriptResolver(
        transcripts_dir=transcripts, discovery_root=transcripts
    )
    return SpeakerProfileService(
        root=profiles,
        state_dir=state,
        resolver=resolver,
        speaker_map_resolver=_IgnoredMapResolver() if ignored else None,
    )


@pytest.mark.unit
def test_ignored_speaker_rejects_new_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path, monkeypatch, ignored=True)
    with pytest.raises(IgnoredSpeakerLinkError):
        svc.create_profile_and_link(
            operation_idempotency_key=str(uuid4()),
            display_name="Alice",
            managed_transcript_id=IMPORT_A,
            local_speaker_key="SPEAKER_00",
        )


@pytest.mark.unit
def test_ignored_linked_excluded_from_headline_unless_include_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Link while not ignored, then aggregate with ignored map resolver.
    svc = _svc(tmp_path, monkeypatch, ignored=False)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    # Also link SPEAKER_01 as control (not ignored).
    created2 = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Bob",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_01",
    )
    # Rebuild service with ignored map so SPEAKER_00 appears ignored.
    transcripts = tmp_path / "transcripts"
    resolver = ManagedTranscriptResolver(
        transcripts_dir=transcripts, discovery_root=transcripts
    )
    svc_ignored = SpeakerProfileService(
        root=svc.root,
        state_dir=tmp_path / "state",
        resolver=resolver,
        speaker_map_resolver=_IgnoredMapResolver(),
    )
    # Patch aggregate path's SpeakerMapResolver via monkeypatch on aggregates module
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.aggregates.SpeakerMapResolver",
        lambda: _IgnoredMapResolver(),
    )
    profile = svc_ignored.get_profile(created.profile_id)
    assert profile is not None
    links = list_profile_links(created.profile_id, root=svc.root)
    agg = aggregate_profile(profile, links, resolver=resolver, include_ignored=False)
    assert agg.ignored_linked_count == 1
    assert agg.headline_appearance_count == 0
    assert agg.headline_words == 0
    agg_inc = aggregate_profile(profile, links, resolver=resolver, include_ignored=True)
    assert agg_inc.headline_appearance_count == 1
    assert agg_inc.headline_words > 0
    # Control profile not ignored
    profile2 = svc.get_profile(created2.profile_id)
    links2 = list_profile_links(created2.profile_id, root=svc.root)

    # SPEAKER_01 not in ignored list
    class _Only00Ignored:
        def load_mapping(self, transcript_path: str | Path) -> SpeakerMapState:
            return SpeakerMapState(
                has_sidecar=True,
                speaker_map={},
                ignored_speakers=["SPEAKER_00"],
            )

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.aggregates.SpeakerMapResolver",
        lambda: _Only00Ignored(),
    )
    agg2 = aggregate_profile(profile2, links2, resolver=resolver, include_ignored=False)
    assert agg2.headline_appearance_count == 1
