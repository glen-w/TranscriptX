"""Phase 1.6 profile analytics pack contracts."""

from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from transcriptx.core.speaker_profiles.aggregates import (
    AppearanceRow,
    OccurrenceMetrics,
    compute_occurrence_metrics,
    series_eligible,
)
from transcriptx.core.speaker_profiles.analytics_pack import (
    ProfileAnalyticsMergedError,
    ProfileAnalyticsNotFoundError,
    build_profile_analytics_pack,
)
from transcriptx.core.speaker_profiles.longitudinal import (
    compute_period_speaking_share,
    dedupe_to_transcript_contributions,
    period_identity,
)
from transcriptx.core.speaker_profiles.partners import build_conversation_partners
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.snapshot import (
    ProfileRef,
    build_aggregation_snapshot,
)
from transcriptx.core.speaker_profiles.store_io import profile_content_sha256
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)

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


def _svc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SpeakerProfileService:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch(monkeypatch, transcripts)
    _managed(transcripts, name="meeting_a", import_id=IMPORT_A)
    _managed(
        transcripts,
        name="meeting_b",
        import_id=IMPORT_B,
        imported_at="2026-02-20T10:00:00+00:00",
        segments=[
            {"speaker": "SPEAKER_00", "text": "Alpha beta", "start": 0.0, "end": 3.0},
            {"speaker": "SPEAKER_01", "text": "Gamma", "start": 3.0, "end": 5.0},
        ],
    )
    profiles = tmp_path / "speaker_profiles"
    state = tmp_path / "state"
    profiles.mkdir()
    state.mkdir()
    resolver = ManagedTranscriptResolver(
        transcripts_dir=transcripts, discovery_root=transcripts
    )
    return SpeakerProfileService(root=profiles, state_dir=state, resolver=resolver)


def _row(
    *,
    link_id: str,
    managed_transcript_id: str,
    appearance_date: date | None,
    flag: str = "ok",
    ignored: bool = False,
    words: int = 10,
    turns: int = 1,
    duration: float | None = 4.0,
    local_speaker_key: str = "SPEAKER_00",
    profile_id: str = "p1",
) -> AppearanceRow:
    return AppearanceRow(
        profile_id=profile_id,
        link_id=link_id,
        managed_transcript_id=managed_transcript_id,
        local_speaker_key=local_speaker_key,
        link_file_key="k",
        observed_transcript_relpath="a.json",
        current_relpath="a.json",
        appearance_date=appearance_date,
        flag=flag,  # type: ignore[arg-type]
        ignored=ignored,
        metrics=OccurrenceMetrics(
            words=words,
            turns=turns,
            duration_seconds=duration,
            avg_turn_duration=duration,
            median_turn_duration=duration,
            wpm=None,
            timing_valid_turn_count=1 if duration is not None else 0,
        ),
    )


@pytest.mark.unit
def test_timing_valid_turn_count_includes_zero_duration() -> None:
    metrics = compute_occurrence_metrics(
        [
            {"text": "Hello world", "start": 0.0, "end": 2.0},
            {"text": "x", "start": 2.0, "end": 2.0},
            {"text": "bad", "start": "x", "end": 1},
        ]
    )
    assert metrics.timing_valid_turn_count == 2
    assert metrics.duration_seconds == 2.0
    assert metrics.wpm is not None


@pytest.mark.unit
def test_wpm_unavailable_when_only_zero_duration() -> None:
    metrics = compute_occurrence_metrics(
        [{"text": "hi", "start": 1.0, "end": 1.0}]
    )
    assert metrics.timing_valid_turn_count == 1
    assert metrics.duration_seconds == 0.0
    assert metrics.wpm is None


@pytest.mark.unit
def test_series_eligible_flag_matrix() -> None:
    day = date(2026, 1, 1)
    for flag in ("needs_review", "missing_source", "collision", "repair_required"):
        row = _row(link_id=flag, managed_transcript_id="t", appearance_date=day, flag=flag)
        assert series_eligible(row, include_ignored=True) is False
        assert series_eligible(row, include_ignored=False) is False
    ignored = _row(
        link_id="ig", managed_transcript_id="t", appearance_date=day, flag="ignored", ignored=True
    )
    assert series_eligible(ignored, include_ignored=False) is False
    assert series_eligible(ignored, include_ignored=True) is True
    combo = _row(
        link_id="c",
        managed_transcript_id="t",
        appearance_date=day,
        flag="needs_review",
        ignored=True,
    )
    assert series_eligible(combo, include_ignored=True) is False


@pytest.mark.unit
def test_period_identity_unknown_last() -> None:
    sk, pid, label = period_identity(None, "month")
    assert pid == "unknown"
    assert label == "Unknown date"
    assert sk == date.max
    msk, mpid, _ = period_identity(date(2026, 2, 20), "month")
    assert mpid == "2026-02"
    assert msk == date(2026, 2, 1)
    _, qpid, _ = period_identity(date(2026, 2, 20), "quarter")
    assert qpid == "2026-Q1"


@pytest.mark.unit
def test_numerator_dedupe_same_link_and_key() -> None:
    day = date(2026, 1, 15)
    rows = (
        _row(link_id="a", managed_transcript_id="t1", appearance_date=day, words=10, duration=2.0),
        _row(link_id="a", managed_transcript_id="t1", appearance_date=day, words=10, duration=2.0),
        _row(
            link_id="b",
            managed_transcript_id="t1",
            appearance_date=day,
            words=5,
            duration=1.0,
            local_speaker_key="SPEAKER_00",
        ),
    )
    contribs = dedupe_to_transcript_contributions(rows)
    assert len(contribs) == 1
    # duplicate link_id dropped; duplicate (tid,key) keeps smallest link_id only
    assert contribs[0].words == 10
    assert contribs[0].source_appearance_ids == ("a",)


@pytest.mark.unit
def test_speaking_share_helper_partial_and_unavailable() -> None:
    contribs = dedupe_to_transcript_contributions(
        (
            _row(link_id="a", managed_transcript_id="t1", appearance_date=date(2026, 1, 1), duration=2.0),
            _row(link_id="b", managed_transcript_id="t2", appearance_date=date(2026, 1, 1), duration=None),
        )
    )
    dens = {"t1": 10.0, "t2": 10.0}
    share = compute_period_speaking_share(contribs, dens)
    assert share.value == pytest.approx(0.1)
    assert share.availability == "partial"
    assert share.evidence_note and share.evidence_note.startswith("missing_timing:")

    empty = compute_period_speaking_share(
        dedupe_to_transcript_contributions(
            (_row(link_id="x", managed_transcript_id="t1", appearance_date=None, duration=None),)
        ),
        {"t1": 5.0},
    )
    assert empty.value is None
    assert empty.availability == "unavailable"


@pytest.mark.unit
def test_pack_empty_not_found_merged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path, monkeypatch)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    # Create a second profile then unlink its only appearance → empty pack
    other = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Solo",
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
    )
    svc.unlink(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
    )
    snap = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    empty_pack = build_profile_analytics_pack(snap, other.profile_id)
    assert empty_pack.status == "empty"
    assert empty_pack.headline.words == ()
    assert empty_pack.partners == ()

    with pytest.raises(ProfileAnalyticsNotFoundError):
        build_profile_analytics_pack(snap, "missing-profile-id")

    bob = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Bob",
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_01",
    )
    sha = profile_content_sha256(created.profile_id, root=svc.root)
    svc.merge_profiles(
        operation_idempotency_key=str(uuid4()),
        source_profile_id=created.profile_id,
        target_profile_id=bob.profile_id,
        expected_source_sha256=sha,
    )
    snap2 = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    with pytest.raises(ProfileAnalyticsMergedError):
        build_profile_analytics_pack(snap2, created.profile_id)


@pytest.mark.unit
def test_pack_trends_and_partners(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path, monkeypatch)
    alice = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    svc.link_existing_profile(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
        profile_id=alice.profile_id,
    )
    bob = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Bob",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_01",
    )
    svc.link_existing_profile(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_01",
        profile_id=bob.profile_id,
    )
    snap = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    assert alice.profile_id in snap.profiles_by_id

    pack = build_profile_analytics_pack(
        snap, alice.profile_id, grain="appearance_date", include_all_series=True
    )
    assert pack.freshness_token == snap.aggregates_by_profile[alice.profile_id].freshness_token
    assert pack.all_appearances is not None
    assert len(pack.headline.speaking_minutes) >= 1
    assert all(p.value is None or p.value >= 0 for p in pack.headline.speaking_minutes)

    # Month grain reconciles unknown isolation
    month_pack = build_profile_analytics_pack(snap, alice.profile_id, grain="month")
    assert all(p.period_id != "unknown" or p.display_label == "Unknown date" for p in month_pack.headline.words)

    assert len(pack.partners) == 1
    assert pack.partners[0].partner_id == bob.profile_id
    assert pack.partners[0].shared_transcript_count == 2
    assert pack.partners[0].partner_id != alice.profile_id

    # Additive headline words match aggregate
    agg = snap.aggregates_by_profile[alice.profile_id]
    words_sum = sum(int(p.value or 0) for p in pack.headline.words)
    assert words_sum == agg.headline_words


@pytest.mark.unit
def test_pack_no_filesystem_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path, monkeypatch)
    alice = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    snap = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)

    def _boom(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("filesystem/resolver call not allowed")

    monkeypatch.setattr(Path, "read_text", _boom)
    monkeypatch.setattr(Path, "read_bytes", _boom)
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.resolver.ManagedTranscriptResolver.resolve",
        _boom,
    )
    pack = build_profile_analytics_pack(snap, alice.profile_id)
    assert pack.profile_id == alice.profile_id


@pytest.mark.unit
def test_partners_exclude_self_and_merged_owner() -> None:
    day = date(2026, 1, 1)
    from transcriptx.core.speaker_profiles.models import SpeakerProfileLinkV1
    from transcriptx.core.speaker_profiles.versioning import LINK_SCHEMA_ID

    def _link(pid: str, tid: str, key: str, lid: str) -> SpeakerProfileLinkV1:
        return SpeakerProfileLinkV1(
            schema_id=LINK_SCHEMA_ID,
            link_id=lid,
            profile_id=pid,
            managed_transcript_id=tid,
            local_speaker_key=key,
            occurrence_fingerprint="occurrence_fingerprint.v1:" + ("a" * 64),
            observed_transcript_relpath="x.json",
            observed_label="x",
            status="confirmed",
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        )

    TID = "550e8400-e29b-41d4-a716-446655440099"
    links = (
        _link("alice", TID, "SPEAKER_00", "l0"),
        _link("bob", TID, "SPEAKER_01", "l1"),
        _link("merged_guy", TID, "SPEAKER_02", "l2"),
        _link("ghost", TID, "SPEAKER_03", "l3"),
    )
    profiles = {
        "alice": ProfileRef("alice", "Alice", "active", None),
        "bob": ProfileRef("bob", "Bob", "active", None),
        "merged_guy": ProfileRef("merged_guy", "M", "merged", "bob"),
    }
    subject_rows = (
        _row(
            link_id="s1",
            managed_transcript_id=TID,
            appearance_date=day,
            profile_id="alice",
        ),
    )
    result = build_conversation_partners(
        subject_profile_id="alice",
        subject_appearances=subject_rows,
        links=links,
        profiles_by_id=profiles,
    )
    ids = {p.partner_id for p in result.partners}
    assert ids == {"bob"}
    assert any(w.startswith("merged_owner_link:") for w in result.integrity_warnings)
    assert any(w.startswith("dangling_partner_profile:") for w in result.integrity_warnings)


@pytest.mark.unit
def test_mutation_changes_freshness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path, monkeypatch)
    alice = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    snap1 = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    token1 = snap1.aggregates_by_profile[alice.profile_id].freshness_token
    svc.link_existing_profile(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
        profile_id=alice.profile_id,
    )
    snap2 = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    token2 = snap2.aggregates_by_profile[alice.profile_id].freshness_token
    assert token1 != token2
    pack1 = build_profile_analytics_pack(snap1, alice.profile_id)
    pack2 = build_profile_analytics_pack(snap2, alice.profile_id)
    assert pack1.freshness_token == token1
    assert pack2.freshness_token == token2


@pytest.mark.unit
def test_speakers_page_has_trends_not_gallery() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "transcriptx"
        / "web"
        / "page_modules"
        / "speakers.py"
    )
    src = path.read_text(encoding="utf-8")
    assert 'st.expander("Trends"' in src
    assert 'st.expander("Conversation partners"' in src
    assert 'st.expander("Interactions & equity"' in src
    assert 'st.expander("Sentiment"' in src
    assert "@st.fragment" in src
    assert "def _render_detail_charts" in src
    assert "def _render_interactions_equity" in src
    assert "def _render_sentiment_trends" in src
    assert "_speakers_browser_fragment" in src
    assert "scope=\"fragment\"" in src or "scope='fragment'" in src
    assert "build_profile_analytics_pack" in src
    assert "build_profile_interactions_pack" in src
    assert "build_profile_sentiment_pack" in src
    assert "chart_definitions" not in src
    assert "_evidence_caption" in src
    tree = ast.parse(src)
    assert tree is not None


@pytest.mark.unit
def test_grain_additive_reconcile_and_all_contains_headline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path, monkeypatch)
    alice = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    svc.link_existing_profile(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
        profile_id=alice.profile_id,
    )
    snap = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    date_pack = build_profile_analytics_pack(
        snap, alice.profile_id, grain="appearance_date", include_all_series=True
    )
    month_pack = build_profile_analytics_pack(snap, alice.profile_id, grain="month")
    quarter_pack = build_profile_analytics_pack(snap, alice.profile_id, grain="quarter")

    date_words = sum(int(p.value or 0) for p in date_pack.headline.words)
    assert date_words == sum(int(p.value or 0) for p in month_pack.headline.words)
    assert date_words == sum(int(p.value or 0) for p in quarter_pack.headline.words)
    assert date_words == snap.aggregates_by_profile[alice.profile_id].headline_words

    assert date_pack.all_appearances is not None
    by_period_all = {
        p.period_id: set(p.source_appearance_ids) for p in date_pack.all_appearances.words
    }
    for hp in date_pack.headline.words:
        assert set(hp.source_appearance_ids) <= by_period_all.get(hp.period_id, set())

    appearance_ids = {r.link_id for r in snap.appearances_by_profile[alice.profile_id]}
    for p in date_pack.headline.words:
        assert set(p.source_appearance_ids) <= appearance_ids


@pytest.mark.unit
def test_median_only_uses_subject_segments() -> None:
    from transcriptx.core.speaker_profiles.longitudinal import (
        TranscriptContribution,
        _collect_turn_durations,
    )
    from transcriptx.core.speaker_profiles.snapshot import TranscriptBundle

    subject = TranscriptContribution(
        managed_transcript_id="t1",
        words=3,
        turns=2,
        duration_seconds=3.0,
        timing_valid_turn_count=2,
        source_appearance_ids=("a",),
        local_speaker_keys=("SPEAKER_00",),
        untimed=False,
    )
    bundle = TranscriptBundle(
        managed_transcript_id="t1",
        resolved=None,
        segments=(
            {"speaker": "SPEAKER_00", "text": "a", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_00", "text": "b", "start": 1.0, "end": 3.0},
            {"speaker": "SPEAKER_01", "text": "other", "start": 0.0, "end": 99.0},
        ),
        occurrences=(),
        ignored_keys=frozenset(),
        appearance_date=date(2026, 1, 1),
        transcript_duration_denominator=102.0,
    )
    other = TranscriptBundle(
        managed_transcript_id="t2",
        resolved=None,
        segments=(
            {"speaker": "SPEAKER_00", "text": "noise", "start": 0.0, "end": 50.0},
        ),
        occurrences=(),
        ignored_keys=frozenset(),
        appearance_date=date(2026, 1, 1),
        transcript_duration_denominator=50.0,
    )
    durs, warns = _collect_turn_durations(
        (subject,), {"t1": bundle, "t2": other}
    )
    assert sorted(durs) == [1.0, 2.0]
    assert warns == []


@pytest.mark.unit
def test_flag_matrix_headline_vs_all_series() -> None:
    from transcriptx.core.speaker_profiles.longitudinal import build_trend_bundle

    day = date(2026, 1, 15)
    rows = (
        _row(link_id="ok", managed_transcript_id="t1", appearance_date=day, flag="ok", words=10),
        _row(
            link_id="nr",
            managed_transcript_id="t2",
            appearance_date=day,
            flag="needs_review",
            words=20,
        ),
        _row(
            link_id="ig",
            managed_transcript_id="t3",
            appearance_date=day,
            flag="ignored",
            ignored=True,
            words=30,
        ),
    )
    dens = {"t1": 10.0, "t2": 10.0, "t3": 10.0}
    headline = build_trend_bundle(
        rows,
        grain="appearance_date",
        inclusion="headline",
        include_ignored=False,
        transcript_denominators=dens,
        bundles={},
    )
    all_series = build_trend_bundle(
        rows,
        grain="appearance_date",
        inclusion="all",
        include_ignored=False,
        transcript_denominators=dens,
        bundles={},
    )
    assert sum(int(p.value or 0) for p in headline.words) == 10
    assert sum(int(p.value or 0) for p in all_series.words) == 60
    assert "ok" in headline.words[0].source_appearance_ids
    assert "nr" not in headline.words[0].source_appearance_ids


@pytest.mark.unit
def test_mutations_unlink_archive_change_freshness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path, monkeypatch)
    alice = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    svc.link_existing_profile(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
        profile_id=alice.profile_id,
    )
    snap1 = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    token1 = snap1.aggregates_by_profile[alice.profile_id].freshness_token
    words1 = sum(
        int(p.value or 0)
        for p in build_profile_analytics_pack(snap1, alice.profile_id).headline.words
    )

    svc.unlink(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_B,
        local_speaker_key="SPEAKER_00",
    )
    snap2 = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    token2 = snap2.aggregates_by_profile[alice.profile_id].freshness_token
    words2 = sum(
        int(p.value or 0)
        for p in build_profile_analytics_pack(snap2, alice.profile_id).headline.words
    )
    assert token1 != token2
    assert words2 < words1

    sha = profile_content_sha256(alice.profile_id, root=svc.root)
    svc.archive_profile(
        operation_idempotency_key=str(uuid4()),
        profile_id=alice.profile_id,
        expected_content_sha256=sha,
    )
    snap3 = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    assert snap3.profiles_by_id[alice.profile_id].status == "archived"
    token3 = snap3.aggregates_by_profile[alice.profile_id].freshness_token
    assert token3 != token2


@pytest.mark.unit
def test_period_wpm_is_weighted_not_mean_of_wpms() -> None:
    from transcriptx.core.speaker_profiles.longitudinal import build_trend_bundle

    day = date(2026, 1, 15)
    # Session A: 60 words in 60s → 60 WPM; Session B: 120 words in 60s → 120 WPM
    # Mean of WPMs = 90; weighted = 180 words / 2 minutes = 90 coincidentally —
    # use uneven durations so they diverge: 60w/60s + 120w/120s → mean 90, weighted 60.
    rows = (
        _row(
            link_id="a",
            managed_transcript_id="t1",
            appearance_date=day,
            words=60,
            turns=1,
            duration=60.0,
        ),
        _row(
            link_id="b",
            managed_transcript_id="t2",
            appearance_date=day,
            words=120,
            turns=1,
            duration=120.0,
        ),
    )
    dens = {"t1": 60.0, "t2": 120.0}
    bundle = build_trend_bundle(
        rows,
        grain="appearance_date",
        inclusion="headline",
        include_ignored=False,
        transcript_denominators=dens,
        bundles={},
    )
    assert len(bundle.speaking_rate_wpm) == 1
    pt = bundle.speaking_rate_wpm[0]
    assert pt.value == pytest.approx(60.0)  # 180 words / 3 minutes
    assert pt.value != pytest.approx(90.0)  # not mean of 60 and 120


@pytest.mark.unit
def test_speaking_minutes_partial_and_no_fabrication() -> None:
    from transcriptx.core.speaker_profiles.longitudinal import build_trend_bundle

    day = date(2026, 3, 1)
    rows = (
        _row(
            link_id="timed",
            managed_transcript_id="t1",
            appearance_date=day,
            duration=120.0,
            words=10,
        ),
        _row(
            link_id="untimed",
            managed_transcript_id="t2",
            appearance_date=day,
            duration=None,
            words=10,
        ),
    )
    bundle = build_trend_bundle(
        rows,
        grain="appearance_date",
        inclusion="headline",
        include_ignored=False,
        transcript_denominators={"t1": 120.0, "t2": 0.0},
        bundles={},
    )
    assert len(bundle.speaking_minutes) == 1
    pt = bundle.speaking_minutes[0]
    assert pt.value == pytest.approx(2.0)
    assert pt.availability == "partial"
    assert pt.evidence_note == "missing_timing:1/2"
    # Untimed session still in provenance
    assert "untimed" in pt.source_appearance_ids


@pytest.mark.unit
def test_speaking_share_stable_across_grains_same_bucket() -> None:
    day = date(2026, 2, 10)
    rows = (
        _row(link_id="a", managed_transcript_id="t1", appearance_date=day, duration=2.0),
        _row(link_id="b", managed_transcript_id="t2", appearance_date=day, duration=3.0),
    )
    dens = {"t1": 10.0, "t2": 10.0}
    contribs = dedupe_to_transcript_contributions(rows)
    direct = compute_period_speaking_share(contribs, dens)
    from transcriptx.core.speaker_profiles.longitudinal import build_trend_bundle

    for grain in ("appearance_date", "month", "quarter"):
        bundle = build_trend_bundle(
            rows,
            grain=grain,  # type: ignore[arg-type]
            inclusion="headline",
            include_ignored=False,
            transcript_denominators=dens,
            bundles={},
        )
        assert len(bundle.speaking_share) == 1
        assert bundle.speaking_share[0].value == pytest.approx(direct.value)
        assert bundle.speaking_share[0].availability == direct.availability


@pytest.mark.unit
def test_turn_length_avg_weighted_across_period() -> None:
    from transcriptx.core.speaker_profiles.longitudinal import build_trend_bundle
    from transcriptx.core.speaker_profiles.snapshot import TranscriptBundle

    day = date(2026, 1, 15)
    rows = (
        _row(
            link_id="a",
            managed_transcript_id="t1",
            appearance_date=day,
            duration=2.0,
            turns=2,
            words=4,
            local_speaker_key="SPEAKER_00",
        ),
        _row(
            link_id="b",
            managed_transcript_id="t2",
            appearance_date=day,
            duration=6.0,
            turns=1,
            words=2,
            local_speaker_key="SPEAKER_00",
        ),
    )
    bundles = {
        "t1": TranscriptBundle(
            managed_transcript_id="t1",
            resolved=None,
            segments=(
                {"speaker": "SPEAKER_00", "text": "a", "start": 0.0, "end": 1.0},
                {"speaker": "SPEAKER_00", "text": "b", "start": 1.0, "end": 2.0},
            ),
            occurrences=(),
            ignored_keys=frozenset(),
            appearance_date=day,
            transcript_duration_denominator=2.0,
        ),
        "t2": TranscriptBundle(
            managed_transcript_id="t2",
            resolved=None,
            segments=(
                {"speaker": "SPEAKER_00", "text": "c", "start": 0.0, "end": 6.0},
            ),
            occurrences=(),
            ignored_keys=frozenset(),
            appearance_date=day,
            transcript_duration_denominator=6.0,
        ),
    }
    bundle = build_trend_bundle(
        rows,
        grain="appearance_date",
        inclusion="headline",
        include_ignored=False,
        transcript_denominators={"t1": 2.0, "t2": 6.0},
        bundles=bundles,
    )
    # Durations 1, 1, 6 → avg 8/3, median 1
    assert bundle.turn_length_avg[0].value == pytest.approx(8.0 / 3.0)
    assert bundle.turn_length_median[0].value == pytest.approx(1.0)
    assert bundle.turn_length_avg[0].n_valid_turns == 3


@pytest.mark.unit
def test_partner_ranking_ties_and_top_n() -> None:
    from transcriptx.core.speaker_profiles.models import SpeakerProfileLinkV1
    from transcriptx.core.speaker_profiles.versioning import LINK_SCHEMA_ID

    def _link(pid: str, tid: str, key: str, lid: str) -> SpeakerProfileLinkV1:
        return SpeakerProfileLinkV1(
            schema_id=LINK_SCHEMA_ID,
            link_id=lid,
            profile_id=pid,
            managed_transcript_id=tid,
            local_speaker_key=key,
            occurrence_fingerprint="occurrence_fingerprint.v1:" + ("a" * 64),
            observed_transcript_relpath="x.json",
            observed_label="x",
            status="confirmed",
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        )

    tid_a = "550e8400-e29b-41d4-a716-4466554400aa"
    tid_b = "550e8400-e29b-41d4-a716-4466554400ab"
    day = date(2026, 1, 1)
    subject = (
        _row(link_id="s1", managed_transcript_id=tid_a, appearance_date=day, profile_id="alice", duration=60.0),
        _row(link_id="s2", managed_transcript_id=tid_b, appearance_date=day, profile_id="alice", duration=120.0),
    )
    # Two partners each share 1 transcript — tie on count; minutes differ; name tie-break unused
    links = (
        _link("alice", tid_a, "SPEAKER_00", "l0"),
        _link("alice", tid_b, "SPEAKER_00", "l1"),
        _link("cara", tid_a, "SPEAKER_01", "l2"),
        _link("bora", tid_b, "SPEAKER_01", "l3"),
    )
    profiles = {
        "alice": ProfileRef("alice", "Alice", "active", None),
        "cara": ProfileRef("cara", "Cara", "active", None),
        "bora": ProfileRef("bora", "Bora", "active", None),
    }
    result = build_conversation_partners(
        subject_profile_id="alice",
        subject_appearances=subject,
        links=links,
        profiles_by_id=profiles,
        top_n=1,
    )
    assert len(result.partners) == 1
    assert result.remainder_count == 1
    # bora has 120s subject minutes on shared session vs cara's 60s
    assert result.partners[0].partner_id == "bora"
    assert result.partners[0].shared_speaking_minutes == pytest.approx(2.0)


@pytest.mark.unit
def test_unknown_date_bucket_isolated_from_month() -> None:
    from transcriptx.core.speaker_profiles.longitudinal import build_trend_bundle

    rows = (
        _row(
            link_id="known",
            managed_transcript_id="t1",
            appearance_date=date(2026, 4, 15),
            words=5,
            duration=5.0,
        ),
        _row(
            link_id="unk",
            managed_transcript_id="t2",
            appearance_date=None,
            words=7,
            duration=7.0,
        ),
    )
    bundle = build_trend_bundle(
        rows,
        grain="month",
        inclusion="headline",
        include_ignored=False,
        transcript_denominators={"t1": 5.0, "t2": 7.0},
        bundles={},
    )
    labels = [p.display_label for p in bundle.words]
    assert "2026-04" in labels
    assert "Unknown date" in labels
    assert labels[-1] == "Unknown date"
    by_label = {p.display_label: int(p.value or 0) for p in bundle.words}
    assert by_label["2026-04"] == 5
    assert by_label["Unknown date"] == 7


@pytest.mark.unit
def test_time_series_share_matches_longitudinal_helper() -> None:
    from transcriptx.core.speaker_profiles.time_series import build_time_series

    day = date(2026, 1, 15)
    rows = (
        _row(link_id="a", managed_transcript_id="t1", appearance_date=day, duration=4.0),
        _row(link_id="b", managed_transcript_id="t2", appearance_date=day, duration=None),
    )
    dens = {"t1": 8.0, "t2": 8.0}
    series = build_time_series(
        rows, metric="speaking_share", kind="headline", transcript_denominators=dens
    )
    share = compute_period_speaking_share(
        dedupe_to_transcript_contributions(rows), dens
    )
    assert series.points[0].value == pytest.approx(share.value)
    assert share.availability == "partial"
