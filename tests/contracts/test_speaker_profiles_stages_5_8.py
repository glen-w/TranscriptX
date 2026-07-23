"""Stages 5–8: aggregates, lifecycle, integrity, Speakers UI contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from transcriptx.core.speaker_profiles.aggregates import (
    aggregate_profile,
    compute_occurrence_metrics,
    list_profile_links,
    list_profiles,
    resolve_profile_redirect,
)
from transcriptx.core.speaker_profiles.fingerprint import compute_occurrence_fingerprint
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.integrity import (
    rebuild_freshness_token,
    reverse_lookup_link,
    run_integrity_scan,
    scan_bound_for_listing,
)
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.store_io import profile_content_sha256
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)
from transcriptx.web.page_modules import speakers as speakers_mod

IMPORT_A = "550e8400-e29b-41d4-a716-446655440000"
IMPORT_B = "660e8400-e29b-41d4-a716-446655440001"


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


def _managed(
    transcripts: Path,
    *,
    name: str,
    import_id: str,
    segments: list[dict[str, Any]] | None = None,
) -> Path:
    originals = transcripts / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    archive_rel = f"originals/{name}.srt"
    (transcripts / archive_rel).write_text("x", encoding="utf-8")
    segs = segments or [
        {"speaker": "SPEAKER_00", "text": "Hello world", "start": 0.0, "end": 2.0},
        {"speaker": "SPEAKER_01", "text": "Hi", "start": 2.0, "end": 3.0},
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
        TranscriptMetadata(
            duration_seconds=3.0, segment_count=len(segs), speaker_count=2
        ),
    )
    path = transcripts / f"{name}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    write_initial_sidecar(
        path,
        import_id=import_id,
        imported_at="2026-01-15T10:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename=f"{name}.srt",
        archived_original_relpath=archive_rel,
    )
    return path


def _svc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SpeakerProfileService:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch(monkeypatch, transcripts)
    _managed(transcripts, name="meeting", import_id=IMPORT_A)
    profiles = tmp_path / "speaker_profiles"
    state = tmp_path / "state"
    profiles.mkdir()
    state.mkdir()
    resolver = ManagedTranscriptResolver(
        transcripts_dir=transcripts, discovery_root=transcripts
    )
    return SpeakerProfileService(root=profiles, state_dir=state, resolver=resolver)


@pytest.mark.unit
def test_occurrence_metrics_words_turns_duration() -> None:
    metrics = compute_occurrence_metrics(
        [
            {"text": "Hello world", "start": 0.0, "end": 2.0},
            {"text": "x", "start": 2.0, "end": 2.0},
            {"text": "bad", "start": "x", "end": 1},
        ]
    )
    assert metrics.words == 4
    assert metrics.turns == 3
    assert metrics.duration_seconds == 2.0  # zero-duration counts; invalid timing excluded


@pytest.mark.unit
def test_headline_excludes_needs_review_and_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path, monkeypatch)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    profile = svc.get_profile(created.profile_id)
    assert profile is not None
    links = list_profile_links(created.profile_id, root=svc.root)
    # Force needs_review by mutating fingerprint on disk via supersession inverse:
    # write a bogus fingerprint through supersede then change segments — instead,
    # call aggregate after manually patching link fingerprint via supersede noop:
    from transcriptx.core.speaker_profiles.layout import link_path
    from transcriptx.core.speaker_profiles.store_io import parse_model, write_bytes_under_root, dumps_model
    from transcriptx.core.speaker_profiles.models import SpeakerProfileLinkV1

    key = link_file_key(IMPORT_A, "SPEAKER_00")
    path = link_path(key, root=svc.root)
    link = parse_model(SpeakerProfileLinkV1, path)
    bad = link.model_copy(
        update={"occurrence_fingerprint": "occurrence_fingerprint.v1:" + ("0" * 64)}
    )
    write_bytes_under_root(path, dumps_model(bad), root=svc.root)
    links = list_profile_links(created.profile_id, root=svc.root)
    agg = aggregate_profile(profile, links, resolver=svc.resolver)
    assert agg.pending_review_count == 1
    assert agg.headline_appearance_count == 0
    assert agg.headline_words == 0
    assert agg.speaking_share_basis == "unavailable"


@pytest.mark.unit
def test_speaking_share_unavailable_when_no_valid_duration() -> None:
    metrics = compute_occurrence_metrics(
        [
            {"text": "Hello", "start": None, "end": None},
            {"text": "World", "start": 5, "end": 3},  # end < start → None
        ]
    )
    assert metrics.turns == 2
    assert metrics.words == 2
    assert metrics.duration_seconds is None
    # Profile-level basis follows duration-only denominator > 0 rule.
    total_duration = 0.0
    if metrics.duration_seconds is not None:
        total_duration += metrics.duration_seconds
    basis = "duration" if total_duration > 0 else "unavailable"
    assert basis == "unavailable"


@pytest.mark.unit
def test_archive_and_merged_redirect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path, monkeypatch)
    a = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    b = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Bob",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_01",
    )
    sha = profile_content_sha256(a.profile_id, root=svc.root)
    svc.merge_profiles(
        operation_idempotency_key=str(uuid4()),
        source_profile_id=a.profile_id,
        target_profile_id=b.profile_id,
        expected_source_sha256=sha,
    )
    resolved = resolve_profile_redirect(a.profile_id, root=svc.root)
    assert resolved.profile_id == b.profile_id
    assert resolved.display_name == "Bob"

    sha_b = profile_content_sha256(b.profile_id, root=svc.root)
    svc.archive_profile(
        operation_idempotency_key=str(uuid4()),
        profile_id=b.profile_id,
        expected_content_sha256=sha_b,
    )
    items = {i.profile_id: i for i in list_profiles(root=svc.root)}
    assert items[b.profile_id].status == "archived"
    assert items[a.profile_id].status == "merged"


@pytest.mark.unit
def test_migrate_keeps_observed_relpath(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path, monkeypatch)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    key = link_file_key(IMPORT_A, "SPEAKER_00")
    before = svc.get_live_link(key)
    assert before is not None
    observed = before.observed_transcript_relpath
    svc.migrate_link_observed_relpath(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    after = svc.get_live_link(key)
    assert after is not None
    assert after.observed_transcript_relpath == observed
    assert after.provenance.get("resolver_relpath_at_migration")


@pytest.mark.unit
def test_supersede_fingerprint_clears_needs_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path, monkeypatch)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    from transcriptx.core.speaker_profiles.layout import link_path
    from transcriptx.core.speaker_profiles.store_io import (
        dumps_model,
        parse_model,
        write_bytes_under_root,
    )
    from transcriptx.core.speaker_profiles.models import SpeakerProfileLinkV1

    key = link_file_key(IMPORT_A, "SPEAKER_00")
    path = link_path(key, root=svc.root)
    link = parse_model(SpeakerProfileLinkV1, path)
    write_bytes_under_root(
        path,
        dumps_model(
            link.model_copy(
                update={
                    "occurrence_fingerprint": "occurrence_fingerprint.v1:" + ("ab" * 32)
                }
            )
        ),
        root=svc.root,
    )
    profile = svc.get_profile(created.profile_id)
    agg_before = aggregate_profile(
        profile, list_profile_links(created.profile_id, root=svc.root), resolver=svc.resolver
    )
    assert agg_before.pending_review_count == 1
    svc.supersede_link_fingerprint(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    agg_after = aggregate_profile(
        profile, list_profile_links(created.profile_id, root=svc.root), resolver=svc.resolver
    )
    assert agg_after.pending_review_count == 0
    assert agg_after.headline_appearance_count == 1


@pytest.mark.unit
def test_integrity_and_reverse_lookup_o1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path, monkeypatch)
    for i, speaker in enumerate(("SPEAKER_00", "SPEAKER_01")):
        svc.create_profile_and_link(
            operation_idempotency_key=str(uuid4()),
            display_name=f"P{i}",
            managed_transcript_id=IMPORT_A,
            local_speaker_key=speaker,
        )
    report = run_integrity_scan(svc.root)
    assert report.profiles_scanned == 2
    assert report.links_scanned == 2
    assert report.ok is True
    scanned, parsed = scan_bound_for_listing(svc.root)
    assert scanned == 2
    assert parsed == 2
    t1 = rebuild_freshness_token(svc.root)
    t2 = rebuild_freshness_token(svc.root)
    assert t1 == t2
    stats = reverse_lookup_link(
        root=svc.root,
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    assert stats.examined_paths == 1
    assert stats.found is True


@pytest.mark.unit
def test_fingerprint_stable_across_metadata_only_segment_fields() -> None:
    base = [{"speaker": "SPEAKER_00", "text": "hi", "start": 1.0, "end": 2.0}]
    with_extra = [
        {
            "speaker": "SPEAKER_00",
            "text": "hi",
            "start": 1.0,
            "end": 2.0,
            "confidence": 0.9,
            "foo": "bar",
        }
    ]
    assert compute_occurrence_fingerprint(base) == compute_occurrence_fingerprint(
        with_extra
    )


@pytest.mark.unit
def test_speakers_page_callable_and_nav_wired() -> None:
    assert callable(speakers_mod.render_speakers_page)
    from transcriptx.web.navigation import PAGE_SPECS
    from transcriptx.web.router import build_page_renderers

    assert any(s.key == "Speakers" for s in PAGE_SPECS)
    renderers = build_page_renderers(
        corrections_studio_available=False, render_corrections_studio=None
    )
    assert "Speakers" in renderers
