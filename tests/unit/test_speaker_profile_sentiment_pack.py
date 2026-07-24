"""Unit tests for profile sentiment pack aggregation."""

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
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from transcriptx.core.speaker_profiles.sentiment_pack import (
    build_profile_sentiment_pack,
    find_sentiment_rows_path,
    find_sentiment_summary_path,
)
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


def test_sentiment_pack_missing_and_merged() -> None:
    from transcriptx.core.speaker_profiles.errors import (
        ProfileAnalyticsMergedError,
        ProfileAnalyticsNotFoundError,
    )

    profile = _profile()
    snap = _snap(profile=profile, appearances=(), bundles={})
    with pytest.raises(ProfileAnalyticsNotFoundError):
        build_profile_sentiment_pack(snap, "missing-id")

    merged = _profile(status="merged", merged_into_profile_id="p-target")
    snap_m = _snap(profile=merged, appearances=(), bundles={})
    with pytest.raises(ProfileAnalyticsMergedError):
        build_profile_sentiment_pack(snap_m, "p1")


def test_find_sentiment_paths_prefer_rows_not_with_sentiment(tmp_path: Path) -> None:
    run = tmp_path / "run1"
    global_dir = run / "sentiment" / "data" / "global"
    global_dir.mkdir(parents=True)
    (global_dir / "sample_with_sentiment.json").write_text("[]", encoding="utf-8")
    rows = global_dir / "sample_sentiment.json"
    rows.write_text("[]", encoding="utf-8")
    summary = global_dir / "sample_sentiment_summary.json"
    summary.write_text("{}", encoding="utf-8")

    assert find_sentiment_rows_path(run) == rows
    assert find_sentiment_summary_path(run) == summary


def test_sentiment_pack_from_segment_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    run = outputs / "meeting-slug" / "20260101_120000_abcd1234"
    sent_dir = run / "sentiment" / "data" / "global"
    sent_dir.mkdir(parents=True)
    rows = [
        {
            "speaker": "Alice",
            "start": 0.0,
            "text": "Great news",
            "compound": 0.5,
            "pos": 0.4,
            "neu": 0.6,
            "neg": 0.0,
        },
        {
            "speaker": "Alice",
            "start": 1.0,
            "text": "Bad day",
            "compound": -0.4,
            "pos": 0.0,
            "neu": 0.5,
            "neg": 0.5,
        },
        {
            "speaker": "Bob",
            "start": 2.0,
            "text": "ok",
            "compound": 0.0,
            "pos": 0.0,
            "neu": 1.0,
            "neg": 0.0,
        },
    ]
    (sent_dir / "meeting_sentiment.json").write_text(json.dumps(rows), encoding="utf-8")

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
    profile = _profile()
    appearance = _appearance(managed_transcript_id=mid)
    snap = _snap(profile=profile, appearances=(appearance,), bundles={mid: bundle})

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.sentiment_pack.slug_for_transcript_path",
        lambda _path: "meeting-slug",
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.sentiment_pack.match_keys_for_appearance",
        lambda **_kwargs: frozenset({"alice", "speaker_00"}),
    )

    pack = build_profile_sentiment_pack(snap, "p1", outputs_dir=outputs)
    assert pack.status == "ok"
    assert len(pack.appearances) == 1
    row = pack.appearances[0]
    assert row.segment_count == 2
    assert row.compound_mean == pytest.approx(0.05)
    assert row.pos_mean == pytest.approx(0.2)
    assert row.neg_mean == pytest.approx(0.25)
    assert row.positive_count == 1
    assert row.negative_count == 1
    assert pack.compound_mean == pytest.approx(0.05)
    assert pack.positive_share == pytest.approx(0.5)
    assert pack.negative_share == pytest.approx(0.5)


def test_sentiment_pack_summary_fallback_stubs_pos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    run = outputs / "meeting-slug" / "runA"
    sent_dir = run / "sentiment" / "data" / "global"
    sent_dir.mkdir(parents=True)
    (sent_dir / "meeting_sentiment_summary.json").write_text(
        json.dumps(
            {
                "global_results": {"compound_mean": 0.1},
                "speaker_results": {
                    "Alice": {
                        "count": 4,
                        "compound_mean": 0.12,
                        "pos_mean": 0,
                        "neu_mean": 0,
                        "neg_mean": 0,
                    }
                },
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
        appearance_date=date(2026, 1, 15),
        transcript_duration_denominator=1.0,
    )
    profile = _profile()
    appearance = _appearance(managed_transcript_id=mid)
    snap = _snap(profile=profile, appearances=(appearance,), bundles={mid: bundle})

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.sentiment_pack.slug_for_transcript_path",
        lambda _path: "meeting-slug",
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.sentiment_pack.match_keys_for_appearance",
        lambda **_kwargs: frozenset({"alice", "speaker_00"}),
    )

    pack = build_profile_sentiment_pack(snap, "p1", outputs_dir=outputs)
    assert pack.status == "ok"
    row = pack.appearances[0]
    assert row.compound_mean == pytest.approx(0.12)
    assert row.pos_mean is None
    assert row.neu_mean is None
    assert row.neg_mean is None
    assert row.segment_count == 4


def test_sentiment_pack_weighted_mean_by_segment_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Headline compound must weight by segment_count, not mean-of-means."""
    outputs = tmp_path / "outputs"
    for slug, compounds in (
        ("slug-a", [0.0, 0.0]),  # mean 0.0, n=2
        ("slug-b", [1.0]),  # mean 1.0, n=1 → weighted = (0+0+1)/3 = 1/3
    ):
        run = outputs / slug / f"run-{slug}"
        sent = run / "sentiment" / "data" / "global"
        sent.mkdir(parents=True)
        rows = [
            {
                "speaker": "Alice",
                "start": float(i),
                "text": "x",
                "compound": c,
                "pos": max(0.0, c),
                "neu": 1.0 - abs(c),
                "neg": max(0.0, -c),
            }
            for i, c in enumerate(compounds)
        ]
        (sent / f"{slug}_sentiment.json").write_text(json.dumps(rows), encoding="utf-8")

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
        "transcriptx.core.speaker_profiles.sentiment_pack.slug_for_transcript_path",
        _slug,
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.sentiment_pack.match_keys_for_appearance",
        lambda **_kwargs: frozenset({"alice", "speaker_00"}),
    )

    pack = build_profile_sentiment_pack(snap, "p1", outputs_dir=outputs)
    assert pack.status == "ok"
    assert pack.segment_count == 3
    # Weighted: (0.0*2 + 1.0*1) / 3 — not mean-of-means (0.5)
    assert pack.compound_mean == pytest.approx(1.0 / 3.0)
    assert pack.compound_mean != pytest.approx(0.5)


def test_sentiment_pack_prefers_rows_over_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    run = outputs / "meeting-slug" / "runA"
    sent = run / "sentiment" / "data" / "global"
    sent.mkdir(parents=True)
    (sent / "meeting_sentiment.json").write_text(
        json.dumps(
            [
                {
                    "speaker": "Alice",
                    "start": 0.0,
                    "text": "ok",
                    "compound": 0.2,
                    "pos": 0.1,
                    "neu": 0.9,
                    "neg": 0.0,
                }
            ]
        ),
        encoding="utf-8",
    )
    (sent / "meeting_sentiment_summary.json").write_text(
        json.dumps(
            {
                "speaker_results": {
                    "Alice": {
                        "count": 99,
                        "compound_mean": 0.99,
                        "pos_mean": 0,
                        "neu_mean": 0,
                        "neg_mean": 0,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (sent / "meeting_with_sentiment.json").write_text("[]", encoding="utf-8")

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
        "transcriptx.core.speaker_profiles.sentiment_pack.slug_for_transcript_path",
        lambda _path: "meeting-slug",
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.sentiment_pack.match_keys_for_appearance",
        lambda **_kwargs: frozenset({"alice"}),
    )

    pack = build_profile_sentiment_pack(snap, "p1", outputs_dir=outputs)
    assert pack.appearances[0].compound_mean == pytest.approx(0.2)
    assert pack.appearances[0].segment_count == 1
    assert pack.appearances[0].pos_mean == pytest.approx(0.1)


def test_sentiment_pack_excludes_ignored_unless_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    run = outputs / "meeting-slug" / "runA"
    sent = run / "sentiment" / "data" / "global"
    sent.mkdir(parents=True)
    (sent / "meeting_sentiment.json").write_text(
        json.dumps(
            [
                {
                    "speaker": "Alice",
                    "start": 0.0,
                    "text": "ok",
                    "compound": 0.5,
                    "pos": 0.5,
                    "neu": 0.5,
                    "neg": 0.0,
                }
            ]
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
        appearance_date=date(2026, 1, 15),
        transcript_duration_denominator=1.0,
    )
    profile = _profile()
    appearance = _appearance(managed_transcript_id=mid, ignored=True)
    snap = _snap(profile=profile, appearances=(appearance,), bundles={mid: bundle})
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.sentiment_pack.slug_for_transcript_path",
        lambda _path: "meeting-slug",
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.sentiment_pack.match_keys_for_appearance",
        lambda **_kwargs: frozenset({"alice"}),
    )

    excluded = build_profile_sentiment_pack(
        snap, "p1", include_ignored=False, outputs_dir=outputs
    )
    assert excluded.status == "empty"

    included = build_profile_sentiment_pack(
        snap, "p1", include_ignored=True, outputs_dir=outputs
    )
    assert included.status == "ok"
    assert included.compound_mean == pytest.approx(0.5)
