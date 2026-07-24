"""Unit tests for profile interactions / equity pack aggregation."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from transcriptx.core.speaker_profiles.aggregates import (
    AppearanceRow,
    OccurrenceMetrics,
)
from transcriptx.core.speaker_profiles.interactions_pack import (
    build_profile_interactions_pack,
    find_interactions_speaker_summary_path,
)
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from transcriptx.core.speaker_profiles.snapshot import (
    AggregationSnapshot,
    ProfileRef,
    TranscriptBundle,
)


def _profile(**overrides: Any) -> SpeakerProfileV1:
    base = {
        "profile_id": "p1",
        "display_name": "Alice",
        "aliases": ["Ally"],
        "status": "active",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return SpeakerProfileV1(**base)


def _appearance(**overrides: Any) -> AppearanceRow:
    base = {
        "profile_id": "p1",
        "link_id": "link-1",
        "managed_transcript_id": "550e8400-e29b-41d4-a716-446655440000",
        "local_speaker_key": "SPEAKER_00",
        "link_file_key": "lfk1",
        "observed_transcript_relpath": "meeting.json",
        "current_relpath": "meeting.json",
        "appearance_date": date(2026, 1, 15),
        "flag": "ok",
        "ignored": False,
        "metrics": OccurrenceMetrics(
            words=10,
            turns=2,
            duration_seconds=4.0,
            avg_turn_duration=2.0,
            median_turn_duration=2.0,
            wpm=150.0,
        ),
    }
    base.update(overrides)
    return AppearanceRow(**base)


def _snap(
    *,
    profile: SpeakerProfileV1,
    appearances: tuple[AppearanceRow, ...],
    bundles: dict[str, TranscriptBundle],
) -> AggregationSnapshot:
    pref = ProfileRef(
        profile_id=profile.profile_id,
        display_name=profile.display_name,
        status=profile.status,
        merged_into_profile_id=profile.merged_into_profile_id,
    )
    return AggregationSnapshot(
        root=Path("/tmp"),
        profiles=(profile,),
        profiles_by_id={profile.profile_id: pref},
        links=(),
        links_by_profile={},
        listing=(),
        aggregates_by_profile={
            profile.profile_id: SimpleNamespace(freshness_token="fresh-abc")  # type: ignore[dict-item]
        },
        appearances_by_profile={profile.profile_id: appearances},
        bundles=bundles,
        transcript_denominators={},
        integrity_ok=True,
        incomplete=False,
        corrupt_profile_paths=(),
        corrupt_link_paths=(),
        blocked_profile_ids=frozenset(),
        blocked_link_keys=frozenset(),
        profiles_scanned=1,
        links_scanned=0,
        transcripts_resolved=len(bundles),
    )


def test_interactions_pack_missing_and_merged() -> None:
    from transcriptx.core.speaker_profiles.errors import (
        ProfileAnalyticsMergedError,
        ProfileAnalyticsNotFoundError,
    )

    profile = _profile()
    snap = _snap(profile=profile, appearances=(), bundles={})
    with pytest.raises(ProfileAnalyticsNotFoundError):
        build_profile_interactions_pack(snap, "missing-id")

    merged = _profile(status="merged", merged_into_profile_id="p-target")
    snap_m = _snap(profile=merged, appearances=(), bundles={})
    with pytest.raises(ProfileAnalyticsMergedError):
        build_profile_interactions_pack(snap_m, "p1")


def test_find_interactions_speaker_summary_path(tmp_path: Path) -> None:
    assert find_interactions_speaker_summary_path(tmp_path / "nope") is None

    run = tmp_path / "run1"
    global_dir = run / "interactions" / "data" / "global"
    global_dir.mkdir(parents=True)
    target = global_dir / "sample_speaker_summary.json"
    target.write_text("{}", encoding="utf-8")
    assert find_interactions_speaker_summary_path(run) == target


def test_interactions_pack_extracts_counts_and_equity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    run = outputs / "meeting-slug" / "20260101_120000_abcd1234"
    ix_dir = run / "interactions" / "data" / "global"
    ix_dir.mkdir(parents=True)
    payload = {
        "interruption_initiated": {"Ally": 2, "Bob": 1},
        "interruption_received": {"Ally": 0, "Bob": 2},
        "responses_initiated": {"Ally": 3, "Bob": 1},
        "responses_received": {"Ally": 1, "Bob": 3},
        "net_interruption_balance": {"Ally": 2, "Bob": -1},
        "net_response_balance": {"Ally": 2, "Bob": -2},
        "total_interactions": {"Ally": 6, "Bob": 7},
        "dominance_scores": {"Ally": 0.75, "Bob": 0.25},
        "equity": {
            "floor_share": {"Ally": 0.6, "Bob": 0.4},
            "interruption_asymmetry": {"Ally": 0.1, "Bob": 0.9},
            "response_latency": {"Ally": {"count": 2, "mean": 0.4, "median": 0.3}},
        },
        "semantics_version": 2,
    }
    (ix_dir / "meeting_speaker_summary.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    mid = "550e8400-e29b-41d4-a716-446655440000"
    tx_path = tmp_path / "meeting.json"
    tx_path.write_text("{}", encoding="utf-8")
    resolved = MagicMock()
    resolved.transcript_path = tx_path
    bundle = TranscriptBundle(
        managed_transcript_id=mid,
        resolved=resolved,
        segments=(),
        occurrences=(),
        ignored_keys=frozenset(),
        appearance_date=date(2026, 1, 15),
        transcript_duration_denominator=5.0,
    )
    profile = _profile(aliases=["Ally"])
    appearance = _appearance(managed_transcript_id=mid)
    snap = _snap(profile=profile, appearances=(appearance,), bundles={mid: bundle})

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.interactions_pack.slug_for_transcript_path",
        lambda _path: "meeting-slug",
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.interactions_pack.match_keys_for_appearance",
        lambda **_kwargs: frozenset({"ally", "alice", "speaker_00"}),
    )

    pack = build_profile_interactions_pack(snap, "p1", outputs_dir=outputs)
    assert pack.status == "ok"
    assert len(pack.appearances) == 1
    row = pack.appearances[0]
    assert row.matched_speaker == "Ally"
    assert row.interruptions_initiated == 2
    assert row.interruptions_received == 0
    assert row.responses_initiated == 3
    assert row.dominance_score == 0.75
    assert row.floor_share == 0.6
    assert row.interruption_asymmetry == 0.1
    assert row.response_latency_mean == 0.4
    assert pack.total_interruptions_initiated == 2
    assert pack.mean_floor_share == 0.6
    assert pack.appearances_without_interactions == 0


def test_interactions_pack_empty_when_speaker_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    run = outputs / "meeting-slug" / "runA"
    ix_dir = run / "interactions" / "data" / "global"
    ix_dir.mkdir(parents=True)
    (ix_dir / "meeting_speaker_summary.json").write_text(
        json.dumps(
            {
                "interruption_initiated": {"Bob": 1},
                "responses_initiated": {"Bob": 0},
                "interruption_received": {"Bob": 0},
                "responses_received": {"Bob": 0},
                "total_interactions": {"Bob": 1},
                "dominance_scores": {"Bob": 1.0},
                "equity": {},
            }
        ),
        encoding="utf-8",
    )

    mid = "550e8400-e29b-41d4-a716-446655440000"
    tx_path = tmp_path / "meeting.json"
    tx_path.write_text("{}", encoding="utf-8")
    resolved = MagicMock()
    resolved.transcript_path = tx_path
    bundle = TranscriptBundle(
        managed_transcript_id=mid,
        resolved=resolved,
        segments=(),
        occurrences=(),
        ignored_keys=frozenset(),
        appearance_date=None,
        transcript_duration_denominator=1.0,
    )
    profile = _profile()
    appearance = _appearance(managed_transcript_id=mid)
    snap = _snap(profile=profile, appearances=(appearance,), bundles={mid: bundle})

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.interactions_pack.slug_for_transcript_path",
        lambda _path: "meeting-slug",
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.interactions_pack.match_keys_for_appearance",
        lambda **_kwargs: frozenset({"alice", "speaker_00"}),
    )

    pack = build_profile_interactions_pack(snap, "p1", outputs_dir=outputs)
    assert pack.status == "empty"
    assert pack.appearances == ()
    assert pack.appearances_without_interactions == 1


def _write_ix_summary(outputs: Path, slug: str, run_id: str, payload: dict) -> None:
    ix_dir = outputs / slug / run_id / "interactions" / "data" / "global"
    ix_dir.mkdir(parents=True)
    (ix_dir / f"{slug}_speaker_summary.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_interactions_pack_sums_two_appearances_and_means(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    _write_ix_summary(
        outputs,
        "slug-a",
        "run-a",
        {
            "interruption_initiated": {"Alice": 1},
            "interruption_received": {"Alice": 2},
            "responses_initiated": {"Alice": 4},
            "responses_received": {"Alice": 0},
            "net_interruption_balance": {"Alice": -1},
            "net_response_balance": {"Alice": 4},
            "total_interactions": {"Alice": 7},
            "dominance_scores": {"Alice": 0.2},
            "equity": {"floor_share": {"Alice": 0.4}},
        },
    )
    _write_ix_summary(
        outputs,
        "slug-b",
        "run-b",
        {
            "interruption_initiated": {"Alice": 3},
            "interruption_received": {"Alice": 1},
            "responses_initiated": {"Alice": 1},
            "responses_received": {"Alice": 2},
            "net_interruption_balance": {"Alice": 2},
            "net_response_balance": {"Alice": -1},
            "total_interactions": {"Alice": 7},
            "dominance_scores": {"Alice": 0.8},
            "equity": {"floor_share": {"Alice": 0.6}},
        },
    )

    mid_a = "550e8400-e29b-41d4-a716-446655440000"
    mid_b = "550e8400-e29b-41d4-a716-446655440001"
    bundles: dict[str, TranscriptBundle] = {}
    appearances: list[AppearanceRow] = []
    for mid, slug in ((mid_a, "slug-a"), (mid_b, "slug-b")):
        tx = tmp_path / f"{slug}.json"
        tx.write_text("{}", encoding="utf-8")
        resolved = MagicMock()
        resolved.transcript_path = tx
        bundles[mid] = TranscriptBundle(
            managed_transcript_id=mid,
            resolved=resolved,
            segments=(),
            occurrences=(),
            ignored_keys=frozenset(),
            appearance_date=date(2026, 1, 15),
            transcript_duration_denominator=1.0,
        )
        appearances.append(
            _appearance(
                managed_transcript_id=mid,
                link_id=f"link-{slug}",
                link_file_key=f"lfk-{slug}",
                current_relpath=f"{slug}.json",
                observed_transcript_relpath=f"{slug}.json",
            )
        )

    profile = _profile()
    snap = _snap(profile=profile, appearances=tuple(appearances), bundles=bundles)

    def _slug(path: Path) -> str | None:
        return "slug-a" if path.stem == "slug-a" else "slug-b"

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.interactions_pack.slug_for_transcript_path",
        _slug,
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.interactions_pack.match_keys_for_appearance",
        lambda **_kwargs: frozenset({"alice", "speaker_00"}),
    )

    pack = build_profile_interactions_pack(snap, "p1", outputs_dir=outputs)
    assert pack.status == "ok"
    assert len(pack.appearances) == 2
    assert pack.total_interruptions_initiated == 4  # 1+3
    assert pack.total_interruptions_received == 3  # 2+1
    assert pack.total_responses_initiated == 5  # 4+1
    assert pack.total_responses_received == 2  # 0+2
    assert pack.mean_dominance_score == pytest.approx(0.5)  # (0.2+0.8)/2
    assert pack.mean_floor_share == pytest.approx(0.5)  # (0.4+0.6)/2


def test_interactions_pack_picks_newest_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    slug = "meeting-slug"
    _write_ix_summary(
        outputs,
        slug,
        "run-old",
        {
            "interruption_initiated": {"Alice": 9},
            "interruption_received": {"Alice": 0},
            "responses_initiated": {"Alice": 0},
            "responses_received": {"Alice": 0},
            "total_interactions": {"Alice": 9},
            "dominance_scores": {"Alice": 1.0},
            "equity": {},
        },
    )
    _write_ix_summary(
        outputs,
        slug,
        "run-new",
        {
            "interruption_initiated": {"Alice": 1},
            "interruption_received": {"Alice": 0},
            "responses_initiated": {"Alice": 0},
            "responses_received": {"Alice": 0},
            "total_interactions": {"Alice": 1},
            "dominance_scores": {"Alice": 0.1},
            "equity": {},
        },
    )
    # Ensure mtime order: run-new is newer
    old = outputs / slug / "run-old"
    new = outputs / slug / "run-new"
    import os
    import time

    older = time.time() - 100
    newer = time.time()
    os.utime(old, (older, older))
    os.utime(new, (newer, newer))

    mid = "550e8400-e29b-41d4-a716-446655440000"
    tx_path = tmp_path / "meeting.json"
    tx_path.write_text("{}", encoding="utf-8")
    resolved = MagicMock()
    resolved.transcript_path = tx_path
    bundle = TranscriptBundle(
        managed_transcript_id=mid,
        resolved=resolved,
        segments=(),
        occurrences=(),
        ignored_keys=frozenset(),
        appearance_date=date(2026, 1, 15),
        transcript_duration_denominator=1.0,
    )
    profile = _profile()
    snap = _snap(
        profile=profile,
        appearances=(_appearance(managed_transcript_id=mid),),
        bundles={mid: bundle},
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.interactions_pack.slug_for_transcript_path",
        lambda _path: slug,
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.interactions_pack.match_keys_for_appearance",
        lambda **_kwargs: frozenset({"alice", "speaker_00"}),
    )

    pack = build_profile_interactions_pack(snap, "p1", outputs_dir=outputs)
    assert pack.status == "ok"
    assert pack.appearances[0].run_id == "run-new"
    assert pack.appearances[0].interruptions_initiated == 1


def test_interactions_pack_excludes_needs_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    _write_ix_summary(
        outputs,
        "meeting-slug",
        "runA",
        {
            "interruption_initiated": {"Alice": 5},
            "interruption_received": {"Alice": 0},
            "responses_initiated": {"Alice": 0},
            "responses_received": {"Alice": 0},
            "total_interactions": {"Alice": 5},
            "dominance_scores": {"Alice": 1.0},
            "equity": {},
        },
    )
    mid = "550e8400-e29b-41d4-a716-446655440000"
    tx_path = tmp_path / "meeting.json"
    tx_path.write_text("{}", encoding="utf-8")
    resolved = MagicMock()
    resolved.transcript_path = tx_path
    bundle = TranscriptBundle(
        managed_transcript_id=mid,
        resolved=resolved,
        segments=(),
        occurrences=(),
        ignored_keys=frozenset(),
        appearance_date=date(2026, 1, 15),
        transcript_duration_denominator=1.0,
    )
    profile = _profile()
    appearance = _appearance(managed_transcript_id=mid, flag="needs_review")
    snap = _snap(profile=profile, appearances=(appearance,), bundles={mid: bundle})
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.interactions_pack.slug_for_transcript_path",
        lambda _path: "meeting-slug",
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.interactions_pack.match_keys_for_appearance",
        lambda **_kwargs: frozenset({"alice"}),
    )

    pack = build_profile_interactions_pack(snap, "p1", outputs_dir=outputs)
    assert pack.status == "empty"
    assert pack.appearances_without_interactions == 0
    assert pack.total_interruptions_initiated == 0
