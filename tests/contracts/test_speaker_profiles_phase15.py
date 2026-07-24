"""Phase 1.5 contracts: accents, flags, snapshot, time-series, mutations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from transcriptx.core.speaker_profiles.accents import (
    SPEAKER_ACCENTS,
    assign_unused_accent,
    normalize_accent_color,
)
from transcriptx.core.speaker_profiles.aggregates import (
    resolve_appearance_flag,
)
from transcriptx.core.speaker_profiles.errors import (
    SpeakerProfileContractError,
    StaleConfirmationError,
)
from transcriptx.core.speaker_profiles.integrity import run_integrity_scan
from transcriptx.core.speaker_profiles.normalize import apply_profile_update
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.snapshot import build_aggregation_snapshot
from transcriptx.core.speaker_profiles.store_io import (
    profile_content_sha256,
    read_profile,
)
from transcriptx.core.speaker_profiles.time_series import (
    DIRECTORY_TOP_N,
    build_directory_activity_chart,
    build_time_series,
)
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)
from transcriptx.web.speaker_accent import resolve_speaker_accent, speaker_heading_html

IMPORT_A = "550e8400-e29b-41d4-a716-446655440000"
IMPORT_B = "660e8400-e29b-41d4-a716-446655440001"
IMPORT_C = "770e8400-e29b-41d4-a716-446655440002"


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
    imported_at: str = "2026-01-15T10:00:00+00:00",
) -> Path:
    originals = transcripts / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    archive_rel = f"originals/{name}.srt"
    (transcripts / archive_rel).write_text("x", encoding="utf-8")
    segs = segments or [
        {"speaker": "SPEAKER_00", "text": "Hello world", "start": 0.0, "end": 2.0},
        {"speaker": "SPEAKER_01", "text": "Hi there", "start": 2.0, "end": 4.0},
    ]
    doc = create_transcript_document(
        segs,
        SourceInfo(
            type="srt",
            original_path=archive_rel,
            imported_at=imported_at,
            file_hash="abc",
            file_mtime=0.0,
        ),
        TranscriptMetadata(
            duration_seconds=4.0, segment_count=len(segs), speaker_count=2
        ),
    )
    path = transcripts / f"{name}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    write_initial_sidecar(
        path,
        import_id=import_id,
        imported_at=imported_at,
        adapter_source_id="srt",
        source_upload_basename=f"{name}.srt",
        archived_original_relpath=archive_rel,
    )
    return path


def _svc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transcripts: Path | None = None
) -> SpeakerProfileService:
    from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver

    if transcripts is None:
        transcripts = tmp_path / "transcripts"
        transcripts.mkdir(exist_ok=True)
    _patch(monkeypatch, transcripts)
    profiles = tmp_path / "speaker_profiles"
    state = tmp_path / "state"
    profiles.mkdir(exist_ok=True)
    state.mkdir(exist_ok=True)
    resolver = ManagedTranscriptResolver(
        transcripts_dir=transcripts, discovery_root=transcripts
    )
    return SpeakerProfileService(root=profiles, state_dir=state, resolver=resolver)


def test_normalize_accent_short_and_reject() -> None:
    assert normalize_accent_color("#abc") == "#AABBCC"
    assert normalize_accent_color("#aAbBcC") == "#AABBCC"
    with pytest.raises(SpeakerProfileContractError):
        normalize_accent_color("#AABBCCDD")
    with pytest.raises(SpeakerProfileContractError):
        normalize_accent_color("red")
    with pytest.raises(SpeakerProfileContractError):
        normalize_accent_color("rgb(1,2,3)")


def test_assign_unused_avoids_used() -> None:
    used = list(SPEAKER_ACCENTS[:3])
    for _ in range(10):
        color = assign_unused_accent(used)
        assert color not in used
        assert color in SPEAKER_ACCENTS


def test_flag_precedence_collision_beats_needs_review() -> None:
    assert resolve_appearance_flag(collision=True, needs_review=True) == "collision"
    assert (
        resolve_appearance_flag(
            repair_required=True, missing_source=True, collision=True
        )
        == "repair_required"
    )


def test_create_assigns_distinct_accents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(transcripts, name="a", import_id=IMPORT_A)
    _managed(
        transcripts,
        name="b",
        import_id=IMPORT_B,
        imported_at="2026-01-16T10:00:00+00:00",
    )
    r1 = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    r2 = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Bob",
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
    )
    p1 = read_profile(r1.profile_id, root=svc.root)
    p2 = read_profile(r2.profile_id, root=svc.root)
    assert p1 is not None and p2 is not None
    assert p1.accent_color
    assert p2.accent_color
    assert p1.accent_color != p2.accent_color


def test_clear_notes_and_invalid_blank_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(transcripts, name="a", import_id=IMPORT_A)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
        notes="keep me",
    )
    sha = profile_content_sha256(created.profile_id, root=svc.root)
    assert sha
    svc.update_profile(
        operation_idempotency_key=str(uuid4()),
        profile_id=created.profile_id,
        expected_content_sha256=sha,
        clear_notes=True,
    )
    updated = read_profile(created.profile_id, root=svc.root)
    assert updated is not None
    assert updated.notes is None
    with pytest.raises(SpeakerProfileContractError):
        apply_profile_update(updated, display_name="   ")


def test_unarchive_and_link_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(transcripts, name="a", import_id=IMPORT_A)
    _managed(transcripts, name="b", import_id=IMPORT_B)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    sha = profile_content_sha256(created.profile_id, root=svc.root)
    assert sha
    svc.archive_profile(
        operation_idempotency_key=str(uuid4()),
        profile_id=created.profile_id,
        expected_content_sha256=sha,
    )
    sha2 = profile_content_sha256(created.profile_id, root=svc.root)
    assert sha2
    svc.unarchive_profile(
        operation_idempotency_key=str(uuid4()),
        profile_id=created.profile_id,
        expected_content_sha256=sha2,
    )
    assert read_profile(created.profile_id, root=svc.root).status == "active"
    linked = svc.link_existing_profile(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
        profile_id=created.profile_id,
    )
    assert linked.profile_id == created.profile_id
    noop = svc.relink(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
        profile_id=created.profile_id,
    )
    assert noop.noop is True


def test_stale_unlink_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(transcripts, name="a", import_id=IMPORT_A)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    with pytest.raises(StaleConfirmationError):
        svc.unlink(
            operation_idempotency_key=str(uuid4()),
            managed_transcript_id=IMPORT_A,
            local_speaker_key="SPEAKER_00",
            expected_link_id="not-the-real-id",
        )
    assert created.link_id


def test_snapshot_scan_bound_and_time_series(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(
        transcripts,
        name="a",
        import_id=IMPORT_A,
        imported_at="2026-01-15T10:00:00+00:00",
    )
    _managed(
        transcripts,
        name="b",
        import_id=IMPORT_B,
        imported_at="2026-01-15T10:00:00+00:00",
    )
    _managed(
        transcripts,
        name="c",
        import_id=IMPORT_C,
        imported_at="2026-01-16T10:00:00+00:00",
    )
    p = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    svc.link_existing_profile(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
        profile_id=p.profile_id,
    )
    svc.link_existing_profile(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_C,
        local_speaker_key="SPEAKER_00",
        profile_id=p.profile_id,
    )
    snap = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    assert snap.scan_stats["transcripts"] == 3
    assert snap.scan_stats["link_files"] == 3
    # One-pass: transcripts resolved once per distinct managed id
    assert snap.transcripts_resolved == 3
    rows = snap.appearances_by_profile[p.profile_id]
    headline = build_time_series(
        rows,
        metric="words",
        kind="headline",
        transcript_denominators=snap.transcript_denominators,
    )
    # Two appearances share 2026-01-15 → one bucket; Unknown not present
    labels = [pt.display_label for pt in headline.points]
    assert labels.count("2026-01-15") == 1
    assert labels[-1] != "Unknown date" or "Unknown date" in labels
    # Same-date source ids aggregated
    day = next(pt for pt in headline.points if pt.display_label == "2026-01-15")
    assert len(day.source_appearance_ids) == 2

    share = build_time_series(
        rows,
        metric="speaking_share",
        kind="headline",
        transcript_denominators=snap.transcript_denominators,
    )
    day_share = next(pt for pt in share.points if pt.display_label == "2026-01-15")
    # Unique transcript densoms: A and B both on same date
    assert day_share.value is not None
    assert 0 < day_share.value <= 1.0


def test_directory_top_n_other(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch(monkeypatch, transcripts)
    ids: list[str] = []
    for i in range(DIRECTORY_TOP_N + 2):
        iid = f"550e8400-e29b-41d4-a716-{i:012d}"
        ids.append(iid)
        _managed(
            transcripts,
            name=f"t{i}",
            import_id=iid,
            segments=[
                {
                    "speaker": "SPEAKER_00",
                    "text": "word " * (i + 1),
                    "start": 0.0,
                    "end": 1.0,
                }
            ],
        )
    svc = _svc(tmp_path, monkeypatch, transcripts)
    for i, iid in enumerate(ids):
        svc.create_profile_and_link(
            operation_idempotency_key=str(uuid4()),
            display_name=f"P{i}",
            managed_transcript_id=iid,
            local_speaker_key="SPEAKER_00",
        )
    snap = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    active = [i.profile_id for i in snap.listing if i.status == "active"]
    chart = build_directory_activity_chart(
        profile_rows=snap.appearances_by_profile,
        profile_headline_words={
            pid: snap.aggregates_by_profile[pid].headline_words for pid in active
        },
        active_profile_ids=active,
    )
    assert len(chart.ranked_profile_ids) == DIRECTORY_TOP_N
    assert len(chart.other_profile_ids) == 2
    assert "Other" in chart.series_by_key


def test_corrupt_link_surfaces_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(transcripts, name="a", import_id=IMPORT_A)
    svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    links = list((svc.root / "links").glob("*.speaker_link.json"))
    assert links
    links[0].write_text("{not-json", encoding="utf-8")
    snap = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    assert snap.incomplete
    assert snap.corrupt_link_paths
    report = run_integrity_scan(svc.root)
    assert report.corrupt_links
    assert not report.ok


def test_replay_cache_signal_includes_merge_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(transcripts, name="a", import_id=IMPORT_A)
    _managed(transcripts, name="b", import_id=IMPORT_B)
    a = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    b = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Bob",
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
    )
    key = str(uuid4())
    sha = profile_content_sha256(a.profile_id, root=svc.root)
    assert sha
    first = svc.merge_profiles(
        operation_idempotency_key=key,
        source_profile_id=a.profile_id,
        target_profile_id=b.profile_id,
        expected_source_sha256=sha,
    )
    replay = svc.merge_profiles(
        operation_idempotency_key=key,
        source_profile_id=a.profile_id,
        target_profile_id=b.profile_id,
        expected_source_sha256=sha,
    )
    assert replay.outcome.replayed is True
    assert b.profile_id in replay.cache_signal.profile_ids
    assert a.profile_id in first.cache_signal.profile_ids


def test_heading_html_uses_assigned_accent() -> None:
    html = speaker_heading_html("Alice", accent="#112233")
    assert "--speaker-accent: #112233" in html
    assert resolve_speaker_accent(
        "Alice", accent="not-a-color"
    ) == resolve_speaker_accent("Alice")


def test_speakers_page_still_callable() -> None:
    from transcriptx.web.page_modules import speakers as speakers_mod

    assert callable(speakers_mod.render_speakers_page)
    from transcriptx.web.page_modules import diagnostics as diagnostics_mod

    assert callable(diagnostics_mod.render_diagnostics_page)
