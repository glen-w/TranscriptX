"""Unit tests for profile NER locations pack aggregation."""

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
from transcriptx.core.speaker_profiles.locations_pack import (
    build_profile_locations_pack,
    find_ner_locations_path,
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


def test_locations_pack_missing_profile_raises() -> None:
    from transcriptx.core.speaker_profiles.errors import ProfileAnalyticsNotFoundError

    profile = _profile()
    snap = _snap(profile=profile, appearances=(), bundles={})
    with pytest.raises(ProfileAnalyticsNotFoundError):
        build_profile_locations_pack(snap, "missing-id")


def test_locations_pack_merged_profile_raises() -> None:
    from transcriptx.core.speaker_profiles.errors import ProfileAnalyticsMergedError

    profile = _profile(status="merged", merged_into_profile_id="p-target")
    snap = _snap(profile=profile, appearances=(), bundles={})
    with pytest.raises(ProfileAnalyticsMergedError):
        build_profile_locations_pack(snap, "p1")


def test_find_ner_locations_path_missing_and_rglob(tmp_path: Path) -> None:
    assert find_ner_locations_path(tmp_path / "nope") is None

    run = tmp_path / "run-nested"
    nested = run / "ner" / "extra" / "deep"
    nested.mkdir(parents=True)
    target = nested / "x_ner-locations.json"
    target.write_text("{}", encoding="utf-8")
    assert find_ner_locations_path(run) == target


def test_paths_match_and_appearance_path_fallbacks(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from transcriptx.core.speaker_profiles import locations_pack as lp

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text("x", encoding="utf-8")
    b.write_text("y", encoding="utf-8")
    assert lp._paths_match(a, a) is True
    assert lp._paths_match(a, b) is False
    assert lp._paths_match("/no/such/left", "/no/such/right") is False

    profile = _profile()
    row = _appearance(current_relpath="", observed_transcript_relpath="obs.json")
    snap = _snap(profile=profile, appearances=(row,), bundles={})
    # No bundle resolved path → falls through to PATHS.transcripts_dir / relpath
    monkey_path = tmp_path / "tx"
    monkey_path.mkdir()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(lp, "PATHS", SimpleNamespace(transcripts_dir=monkey_path))
        path = lp._appearance_transcript_path(snap, row)
        assert path == monkey_path / "obs.json"


def test_find_ner_locations_path_canonical_and_legacy(tmp_path: Path) -> None:
    run = tmp_path / "run1"
    global_dir = run / "ner" / "data" / "global"
    global_dir.mkdir(parents=True)
    target = global_dir / "sample_ner-locations.json"
    target.write_text("{}", encoding="utf-8")
    assert find_ner_locations_path(run) == target

    run2 = tmp_path / "run2"
    legacy = run2 / "ner" / "ner-locations.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("{}", encoding="utf-8")
    assert find_ner_locations_path(run2) == legacy


def test_locations_pack_matches_alias_and_resolves_segment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    run = outputs / "meeting-slug" / "20260101_120000_abcd1234"
    loc_dir = run / "ner" / "data" / "global"
    loc_dir.mkdir(parents=True)
    payload = {
        "Ally": [
            {
                "name": "Paris",
                "lat": 48.8,
                "lon": 2.3,
                "speaker": "Ally",
                "sentence": "I flew to Paris last week.",
                "segment_index": 0,
                "start": 1.5,
            }
        ]
    }
    (loc_dir / "meeting_ner-locations.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    tx_path = transcripts / "meeting.json"
    tx_path.write_text("{}", encoding="utf-8")

    mid = "550e8400-e29b-41d4-a716-446655440000"
    segments = (
        {
            "speaker": "SPEAKER_00",
            "text": "I flew to Paris last week.",
            "start": 1.5,
            "end": 4.0,
        },
        {"speaker": "SPEAKER_01", "text": "Nice.", "start": 4.0, "end": 5.0},
    )
    resolved = MagicMock()
    resolved.transcript_path = tx_path
    bundle = TranscriptBundle(
        managed_transcript_id=mid,
        resolved=resolved,
        segments=segments,
        occurrences=(),
        ignored_keys=frozenset(),
        appearance_date=date(2026, 1, 15),
        transcript_duration_denominator=5.0,
    )
    profile = _profile(aliases=["Ally"])
    appearance = _appearance(managed_transcript_id=mid)
    snap = _snap(profile=profile, appearances=(appearance,), bundles={mid: bundle})

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.locations_pack.OUTPUTS_DIR", outputs
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.locations_pack._slug_for_transcript_path",
        lambda _path: "meeting-slug",
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.locations_pack._match_keys_for_appearance",
        lambda **_kwargs: frozenset({"ally", "alice", "speaker_00"}),
    )

    pack = build_profile_locations_pack(snap, "p1")
    assert pack.status == "ok"
    assert len(pack.mentions) == 1
    mention = pack.mentions[0]
    assert mention.name == "Paris"
    assert mention.segment_index == 0
    assert mention.start_time == 1.5
    assert mention.session_slug == "meeting-slug"
    assert mention.run_id == "20260101_120000_abcd1234"
    assert pack.unresolved_mentions == 0


def test_locations_pack_skips_unresolved_segment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    run = outputs / "meeting-slug" / "runA"
    loc_dir = run / "ner"
    loc_dir.mkdir(parents=True)
    payload = {
        "Alice": [
            {
                "name": "London",
                "lat": 51.5,
                "lon": -0.1,
                "speaker": "Alice",
                "sentence": "This sentence is not in the transcript.",
                # no segment_index — fallback text match must fail
            }
        ]
    }
    (loc_dir / "ner-locations.json").write_text(json.dumps(payload), encoding="utf-8")

    mid = "550e8400-e29b-41d4-a716-446655440000"
    tx_path = tmp_path / "meeting.json"
    tx_path.write_text("{}", encoding="utf-8")
    resolved = MagicMock()
    resolved.transcript_path = tx_path
    bundle = TranscriptBundle(
        managed_transcript_id=mid,
        resolved=resolved,
        segments=(
            {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
        ),
        occurrences=(),
        ignored_keys=frozenset(),
        appearance_date=None,
        transcript_duration_denominator=1.0,
    )
    profile = _profile()
    appearance = _appearance(managed_transcript_id=mid)
    snap = _snap(profile=profile, appearances=(appearance,), bundles={mid: bundle})

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.locations_pack.OUTPUTS_DIR", outputs
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.locations_pack._slug_for_transcript_path",
        lambda _path: "meeting-slug",
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.locations_pack._match_keys_for_appearance",
        lambda **_kwargs: frozenset({"alice", "speaker_00"}),
    )

    pack = build_profile_locations_pack(snap, "p1")
    assert pack.status == "empty"
    assert pack.mentions == ()
    assert pack.unresolved_mentions == 1


def test_locations_pack_aggregates_two_appearances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    for slug, place, lat, lon, idx in (
        ("slug-a", "Paris", 48.8, 2.3, 0),
        ("slug-b", "Berlin", 52.5, 13.4, 0),
    ):
        run = outputs / slug / f"run-{slug}"
        loc = run / "ner" / "ner-locations.json"
        loc.parent.mkdir(parents=True)
        loc.write_text(
            json.dumps(
                {
                    "Alice": [
                        {
                            "name": place,
                            "lat": lat,
                            "lon": lon,
                            "speaker": "Alice",
                            "sentence": f"In {place}.",
                            "segment_index": idx,
                            "start": 0.0,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

    mid_a = "550e8400-e29b-41d4-a716-446655440000"
    mid_b = "550e8400-e29b-41d4-a716-446655440001"
    bundles: dict[str, TranscriptBundle] = {}
    appearances: list[AppearanceRow] = []
    for mid, slug, place in (
        (mid_a, "slug-a", "Paris"),
        (mid_b, "slug-b", "Berlin"),
    ):
        tx = tmp_path / f"{slug}.json"
        tx.write_text("{}", encoding="utf-8")
        resolved = MagicMock()
        resolved.transcript_path = tx
        bundles[mid] = TranscriptBundle(
            managed_transcript_id=mid,
            resolved=resolved,
            segments=(
                {
                    "speaker": "SPEAKER_00",
                    "text": f"In {place}.",
                    "start": 0.0,
                    "end": 1.0,
                },
            ),
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
    snap = _snap(
        profile=profile,
        appearances=tuple(appearances),
        bundles=bundles,
    )

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.locations_pack.OUTPUTS_DIR", outputs
    )

    def _slug(path: Path) -> str | None:
        name = path.stem
        return "slug-a" if name == "slug-a" else "slug-b"

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.locations_pack._slug_for_transcript_path",
        _slug,
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.locations_pack._match_keys_for_appearance",
        lambda **_kwargs: frozenset({"alice", "speaker_00"}),
    )

    pack = build_profile_locations_pack(snap, "p1")
    assert pack.status == "ok"
    names = {m.name for m in pack.mentions}
    assert names == {"Paris", "Berlin"}
    assert len(pack.mentions) == 2
