"""Profile NER location mentions aggregated across linked appearances."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from transcriptx.core.speaker_profiles.aggregates import (
    AppearanceRow,
    series_eligible,
)
from transcriptx.core.speaker_profiles.errors import (
    ProfileAnalyticsMergedError,
    ProfileAnalyticsNotFoundError,
)
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from transcriptx.core.speaker_profiles.snapshot import AggregationSnapshot
from transcriptx.core.utils.paths import OUTPUTS_DIR, PATHS
from transcriptx.core.utils.slug_manager import load_index
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    normalize_diarized_id,
    resolve_speaker_display_label,
)

__all__ = [
    "ProfileLocationMention",
    "ProfileLocationsPack",
    "build_profile_locations_pack",
    "find_ner_locations_path",
]


@dataclass(frozen=True)
class ProfileLocationMention:
    name: str
    lat: float
    lon: float
    sentence: str
    session_slug: str
    run_id: str
    segment_index: int
    start_time: float | None
    managed_transcript_id: str
    transcript_label: str
    appearance_date: date | None


@dataclass(frozen=True)
class ProfileLocationsPack:
    profile_id: str
    freshness_token: str
    include_ignored: bool
    mentions: tuple[ProfileLocationMention, ...]
    appearances_without_ner: int
    unresolved_mentions: int
    status: str  # "ok" | "empty"


def find_ner_locations_path(run_root: Path) -> Path | None:
    """Locate ner-locations JSON under a run root (canonical or legacy layout)."""
    ner_dir = run_root / "ner"
    if not ner_dir.is_dir():
        return None
    global_dir = ner_dir / "data" / "global"
    if global_dir.is_dir():
        matches = sorted(global_dir.glob("*_ner-locations.json"))
        if matches:
            return matches[-1]
    direct = ner_dir / "ner-locations.json"
    if direct.is_file():
        return direct
    nested = sorted(ner_dir.rglob("*ner-locations.json"))
    return nested[0] if nested else None


def _paths_match(left: str | Path, right: str | Path) -> bool:
    try:
        left_path = Path(left).expanduser().resolve(strict=False)
        right_path = Path(right).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return str(left) == str(right)
    if left_path == right_path:
        return True
    try:
        if left_path.is_file() and right_path.is_file():
            return os.path.samefile(left_path, right_path)
    except (OSError, ValueError):
        pass
    return False


def _slug_for_transcript_path(path: Path) -> str | None:
    normalized = str(path.expanduser().resolve(strict=False))
    try:
        index = load_index()
    except Exception:
        return None
    for entry in index.get("transcripts", {}).values():
        if not isinstance(entry, dict):
            continue
        source_path = entry.get("source_path", "")
        if not source_path:
            continue
        if _paths_match(source_path, normalized):
            slug = entry.get("slug")
            return str(slug) if slug else None
    return None


def _appearance_transcript_path(
    snap: AggregationSnapshot, row: AppearanceRow
) -> Path | None:
    bundle = snap.bundles.get(row.managed_transcript_id)
    if bundle is not None and bundle.resolved is not None:
        return Path(bundle.resolved.transcript_path)
    if row.current_relpath:
        return PATHS.transcripts_dir / row.current_relpath
    if row.observed_transcript_relpath:
        return PATHS.transcripts_dir / row.observed_transcript_relpath
    return None


def _match_keys_for_appearance(
    *,
    profile: SpeakerProfileV1,
    local_speaker_key: str,
    transcript_path: Path,
) -> frozenset[str]:
    keys: set[str] = {local_speaker_key.casefold(), profile.display_name.casefold()}
    for alias in profile.aliases:
        alias_s = str(alias or "").strip()
        if alias_s:
            keys.add(alias_s.casefold())
    try:
        state = SpeakerMapResolver().load_mapping(transcript_path)
        mapped = resolve_speaker_display_label(local_speaker_key, state)
        if mapped:
            keys.add(mapped.casefold())
    except Exception:
        pass
    return frozenset(k for k in keys if k)


def _coords_for_speaker(
    payload: Mapping[str, Any], match_keys: frozenset[str]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for speaker_key, records in payload.items():
        if str(speaker_key).casefold() not in match_keys:
            continue
        if not isinstance(records, list):
            continue
        for record in records:
            if isinstance(record, dict):
                out.append(record)
    return out


def _segment_belongs_to_key(seg: Mapping[str, Any], local_speaker_key: str) -> bool:
    raw = seg.get("speaker")
    if raw is None:
        return False
    key = normalize_diarized_id(raw)
    return bool(key) and key == local_speaker_key


def _resolve_segment_index(
    *,
    record: Mapping[str, Any],
    segments: Sequence[Mapping[str, Any]],
    local_speaker_key: str,
) -> tuple[int | None, float | None]:
    raw_idx = record.get("segment_index")
    start_time: float | None = None
    start_raw = record.get("start")
    if start_raw is not None:
        try:
            start_time = float(start_raw)
        except (TypeError, ValueError):
            start_time = None

    if isinstance(raw_idx, int) and not isinstance(raw_idx, bool):
        if raw_idx >= 0 and (not segments or raw_idx < len(segments)):
            return raw_idx, start_time
    if isinstance(raw_idx, float) and raw_idx.is_integer():
        idx = int(raw_idx)
        if idx >= 0 and (not segments or idx < len(segments)):
            return idx, start_time

    sentence = str(record.get("sentence") or "")
    if not sentence:
        return None, start_time

    for idx, seg in enumerate(segments):
        if not _segment_belongs_to_key(seg, local_speaker_key):
            continue
        if str(seg.get("text") or "") == sentence:
            if start_time is None:
                try:
                    start_time = (
                        float(seg["start"]) if seg.get("start") is not None else None
                    )
                except (TypeError, ValueError):
                    start_time = None
            return idx, start_time
    return None, start_time


def _load_locations_json(path: Path) -> Mapping[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _newest_run_with_locations(session_slug: str) -> tuple[str, Path] | None:
    base = Path(OUTPUTS_DIR) / session_slug
    if not base.is_dir():
        return None
    candidates: list[tuple[float, str, Path]] = []
    for run_dir in base.iterdir():
        if not run_dir.is_dir() or run_dir.name.startswith("."):
            continue
        loc_path = find_ner_locations_path(run_dir)
        if loc_path is None:
            continue
        try:
            mtime = float(run_dir.stat().st_mtime)
        except OSError:
            mtime = float("-inf")
        candidates.append((mtime, run_dir.name, loc_path))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _mtime, run_id, loc_path = candidates[0]
    return run_id, loc_path


def build_profile_locations_pack(
    snap: AggregationSnapshot,
    profile_id: str,
    *,
    include_ignored: bool = False,
) -> ProfileLocationsPack:
    """Aggregate geocoded NER locations for a profile across headline appearances."""
    profile = snap.profiles_by_id.get(profile_id)
    profile_model = next((p for p in snap.profiles if p.profile_id == profile_id), None)
    if profile is None or profile_model is None:
        raise ProfileAnalyticsNotFoundError(f"profile not found: {profile_id}")
    if profile.status == "merged":
        raise ProfileAnalyticsMergedError(
            f"profile {profile_id} is merged into {profile.merged_into_profile_id}"
        )

    agg = snap.aggregates_by_profile.get(profile_id)
    freshness = agg.freshness_token if agg is not None else ""
    appearances = snap.appearances_by_profile.get(profile_id, ())
    eligible = [
        row
        for row in appearances
        if series_eligible(row, include_ignored=include_ignored)
    ]

    mentions: list[ProfileLocationMention] = []
    appearances_without_ner = 0
    unresolved_mentions = 0

    for row in eligible:
        path = _appearance_transcript_path(snap, row)
        if path is None:
            appearances_without_ner += 1
            continue
        session_slug = _slug_for_transcript_path(path)
        if not session_slug:
            appearances_without_ner += 1
            continue

        found = _newest_run_with_locations(session_slug)
        if found is None:
            appearances_without_ner += 1
            continue
        run_id, loc_path = found
        payload = _load_locations_json(loc_path)
        if not payload:
            appearances_without_ner += 1
            continue

        match_keys = _match_keys_for_appearance(
            profile=profile_model,
            local_speaker_key=row.local_speaker_key,
            transcript_path=path,
        )
        records = _coords_for_speaker(payload, match_keys)
        if not records:
            appearances_without_ner += 1
            continue

        bundle = snap.bundles.get(row.managed_transcript_id)
        segments: Sequence[Mapping[str, Any]] = (
            bundle.segments if bundle is not None else ()
        )
        transcript_label = row.current_relpath or row.observed_transcript_relpath

        for record in records:
            try:
                lat = float(record["lat"])
                lon = float(record["lon"])
            except (KeyError, TypeError, ValueError):
                unresolved_mentions += 1
                continue
            name = str(record.get("name") or "").strip()
            if not name:
                unresolved_mentions += 1
                continue
            sentence = str(record.get("sentence") or "")
            segment_index, start_time = _resolve_segment_index(
                record=record,
                segments=segments,
                local_speaker_key=row.local_speaker_key,
            )
            if segment_index is None:
                unresolved_mentions += 1
                continue
            mentions.append(
                ProfileLocationMention(
                    name=name,
                    lat=lat,
                    lon=lon,
                    sentence=sentence,
                    session_slug=session_slug,
                    run_id=run_id,
                    segment_index=segment_index,
                    start_time=start_time,
                    managed_transcript_id=row.managed_transcript_id,
                    transcript_label=transcript_label,
                    appearance_date=row.appearance_date,
                )
            )

    return ProfileLocationsPack(
        profile_id=profile_id,
        freshness_token=freshness,
        include_ignored=include_ignored,
        mentions=tuple(mentions),
        appearances_without_ner=appearances_without_ner,
        unresolved_mentions=unresolved_mentions,
        status="ok" if mentions else "empty",
    )
