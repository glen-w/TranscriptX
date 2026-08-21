"""
Detect serial / split audio recordings and voice-note runs.

Pure logic — no UI dependencies. Profile-driven detection lives in
``detect_merge_groups``; ``detect_serial_audio_groups`` remains the
compatibility entry point (builtin defaults / explicit SerialDetectionConfig).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Literal

from transcriptx.core.utils._path_core import strip_duplicate_filename_suffix
from transcriptx.core.utils.rename.smart_name import (
    parse_recording_datetime,
    parse_voice_note_stem,
)

Confidence = Literal["high", "medium", "low"]

_CONFIDENCE_RANK: dict[Confidence, int] = {"high": 3, "medium": 2, "low": 1}

_RULE_CONFIDENCE: dict[str, Confidence] = {
    "timestamp_suffix": "high",
    "part_suffix": "high",
    "voice_note_run": "medium",
    "numeric_index": "medium",
    "duplicate_suffix": "medium",
    "filename_regex": "medium",
}

_RULE_LABELS: dict[str, str] = {
    "timestamp_suffix": "timestamp suffix",
    "part_suffix": "part suffix",
    "voice_note_run": "voice note run",
    "numeric_index": "numeric index",
    "duplicate_suffix": "duplicate suffix",
    "filename_regex": "filename pattern",
}

_RULE_PRIORITY: tuple[str, ...] = (
    "timestamp_suffix",
    "part_suffix",
    "voice_note_run",
    "numeric_index",
    "duplicate_suffix",
    "filename_regex",
)

_TIMESTAMP_SUFFIX_RE = re.compile(r"^(\d{8,})[_-](\d+)$")
_TIMESTAMP_BARE_RE = re.compile(r"^(\d{8,})$")
_PART_SUFFIX_RE = re.compile(
    r"^(.+?)(?:[\s_.-]+)?part(?:[\s_.-]+)?(\d+)$",
    re.IGNORECASE,
)
_NUMERIC_INDEX_RE = re.compile(r"^(.+?)[_-](\d{2,})$")
_DUPLICATE_INDEX_RE = re.compile(r" \(([1-9]\d{0,2})\)$")
_MERGED_OUTPUT_RE = re.compile(r"_merged\.mp3$", re.IGNORECASE)


@dataclass(frozen=True)
class SerialDetectionConfig:
    enabled: bool = True
    min_group_size: int = 2
    enabled_rules: tuple[str, ...] = (
        "timestamp_suffix",
        "voice_note_run",
        "numeric_index",
        "part_suffix",
        "duplicate_suffix",
    )
    max_index_gap: int | None = 3
    voice_note_max_gap_seconds: int = 20 * 60
    require_same_extension: bool = True
    scan_siblings_in_library: bool = False  # reserved; not used in v1


@dataclass(frozen=True)
class SerialGroup:
    base_key: str
    ordered_paths: tuple[Path, ...]
    confidence: Confidence
    matched_rule: str
    indices: tuple[int | None, ...] = ()
    warnings: tuple[str, ...] = ()
    profile_id: str = ""
    profile_name: str = ""

    @property
    def dismissal_key(self) -> str:
        """Stable identity for hiding a suggestion (rule + stem, not file list)."""
        return f"{self.matched_rule}:{self.base_key}"

    @property
    def rule_label(self) -> str:
        return serial_rule_label(self.matched_rule)


def serial_rule_label(rule: str) -> str:
    """Human-readable label for a detection rule id."""
    return _RULE_LABELS.get(rule, rule.replace("_", " "))


@dataclass(frozen=True)
class _ParsedPath:
    path: Path
    base_key: str
    index: int
    extension: str


@dataclass(frozen=True)
class _CandidateGroup:
    base_key: str
    entries: tuple[_ParsedPath, ...]
    matched_rule: str
    confidence: Confidence
    profile_id: str = ""
    profile_name: str = ""
    profile_priority: int = 100


def _normalize_paths(paths: Iterable[Path | str]) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        if _MERGED_OUTPUT_RE.search(resolved.name):
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def _parse_timestamp_suffix(stem: str) -> tuple[str, int] | None:
    match = _TIMESTAMP_SUFFIX_RE.match(stem)
    if match:
        return match.group(1), int(match.group(2))
    # Recorders often keep the first part unsuffixed (20260619172327) and
    # name continuations 20260619172327-01 / _01. Treat the bare timestamp
    # as index 0 of the same group.
    match = _TIMESTAMP_BARE_RE.match(stem)
    if match:
        return match.group(1), 0
    return None


def _parse_part_suffix(stem: str) -> tuple[str, int] | None:
    match = _PART_SUFFIX_RE.match(stem)
    if not match:
        return None
    base = match.group(1).rstrip("._- ")
    if not base:
        return None
    return base, int(match.group(2))


def _parse_numeric_index(stem: str) -> tuple[str, int] | None:
    if _TIMESTAMP_SUFFIX_RE.match(stem):
        return None
    match = _NUMERIC_INDEX_RE.match(stem)
    if not match:
        return None
    base = match.group(1).rstrip("._- ")
    if not base or base.isdigit():
        return None
    return base, int(match.group(2))


def _parse_duplicate_suffix(stem: str) -> tuple[str, int]:
    match = _DUPLICATE_INDEX_RE.search(stem)
    if match:
        base = strip_duplicate_filename_suffix(stem)
        return base, int(match.group(1))
    return strip_duplicate_filename_suffix(stem), 0


def _parse_for_rule(rule: str, path: Path) -> _ParsedPath | None:
    stem = path.stem
    extension = path.suffix.lower()

    if rule == "timestamp_suffix":
        parsed = _parse_timestamp_suffix(stem)
    elif rule == "part_suffix":
        parsed = _parse_part_suffix(stem)
    elif rule == "numeric_index":
        parsed = _parse_numeric_index(stem)
    elif rule == "duplicate_suffix":
        parsed = _parse_duplicate_suffix(stem)
    else:
        return None

    if parsed is None:
        return None
    base_key, index = parsed
    if not base_key:
        return None
    return _ParsedPath(path=path, base_key=base_key, index=index, extension=extension)


def _day_constraint_breaks(
    *,
    same_day_days: int,
    start: datetime,
    candidate: datetime,
) -> bool:
    if same_day_days <= 0:
        return False
    days_apart = (candidate.date() - start.date()).days
    return days_apart < 0 or days_apart >= same_day_days


_UNSET = object()


def _build_voice_note_run_candidates(
    paths: list[Path],
    config: SerialDetectionConfig,
    *,
    families: Iterable[str] | None = None,
    max_gap_seconds: int | None | object = _UNSET,
    same_day_days: int = 0,
    profile_id: str = "",
    profile_name: str = "",
    profile_priority: int = 100,
) -> list[_CandidateGroup]:
    from transcriptx.core.audio.merge_profiles import family_matches

    family_filter = tuple(families) if families is not None else None
    parsed: list[tuple[str, datetime | None, int | None, Path]] = []
    for path in paths:
        result = parse_voice_note_stem(path.stem)
        if result is None:
            continue
        family, recorded_at, sequence = result
        if family_filter is not None and not family_matches(family, family_filter):
            continue
        parsed.append((family, recorded_at, sequence, path))
    if len(parsed) < config.min_group_size:
        return []

    parsed.sort(
        key=lambda item: (
            item[0].lower(),
            item[1] is None,
            item[1] or datetime.min,
            item[2] if item[2] is not None else -1,
            item[3].name,
        )
    )
    if max_gap_seconds is _UNSET:
        max_gap: int | None = max(0, int(config.voice_note_max_gap_seconds))
    else:
        # Explicit None means unlimited consecutive gap.
        max_gap = max_gap_seconds  # type: ignore[assignment]
    max_seq_gap = config.max_index_gap if config.max_index_gap is not None else 3
    candidates: list[_CandidateGroup] = []
    cluster: list[tuple[datetime | None, int | None, Path]] = []
    cluster_family = ""
    cluster_start: datetime | None = None

    def flush() -> None:
        nonlocal cluster_start
        if len(cluster) < config.min_group_size:
            cluster.clear()
            cluster_start = None
            return
        first_dt, first_seq, _first_path = cluster[0]
        if first_dt is None:
            base_key = f"{cluster_family} {first_seq}"
        elif first_seq is not None:
            base_key = f"{cluster_family} {first_dt:%Y-%m-%d}"
        else:
            base_key = f"{cluster_family} {first_dt:%Y-%m-%d %H:%M:%S}"
        entries = tuple(
            _ParsedPath(
                path=path,
                base_key=base_key,
                index=seq if seq is not None else idx,
                extension=path.suffix.lower(),
            )
            for idx, (_dt, seq, path) in enumerate(cluster)
        )
        candidates.append(
            _CandidateGroup(
                base_key=base_key,
                entries=entries,
                matched_rule="voice_note_run",
                confidence=_RULE_CONFIDENCE["voice_note_run"],
                profile_id=profile_id,
                profile_name=profile_name,
                profile_priority=profile_priority,
            )
        )
        cluster.clear()
        cluster_start = None

    def _breaks_cluster(
        family: str,
        recorded_at: datetime | None,
        sequence: int | None,
    ) -> bool:
        if not cluster:
            return False
        if family != cluster_family:
            return True
        prev_dt, prev_seq, _prev_path = cluster[-1]
        # Sequence-only field recorders (ZOOM0001, VOICE001, TASCAM_0001).
        if recorded_at is None and prev_dt is None:
            if sequence is None or prev_seq is None:
                return True
            return (sequence - prev_seq - 1) > max_seq_gap
        # Do not mix sequence-only names with timestamped names.
        if recorded_at is None or prev_dt is None:
            return True
        start = cluster_start or prev_dt
        # Date+sequence media (WhatsApp Android PTT/AUD): day-scoped sequences.
        if sequence is not None and prev_seq is not None:
            if same_day_days > 0:
                if _day_constraint_breaks(
                    same_day_days=same_day_days, start=start, candidate=recorded_at
                ):
                    return True
            elif recorded_at.date() != prev_dt.date():
                # Preserve 2afe3ad default: date+seq never crosses midnight.
                return True
            return (sequence - prev_seq - 1) > max_seq_gap
        if same_day_days > 0 and _day_constraint_breaks(
            same_day_days=same_day_days, start=start, candidate=recorded_at
        ):
            return True
        # Pure timestamps: consecutive wall-clock gap (None = unlimited).
        if max_gap is None:
            return False
        return (recorded_at - prev_dt).total_seconds() > max_gap

    for family, recorded_at, sequence, path in parsed:
        if _breaks_cluster(family, recorded_at, sequence):
            flush()
        if not cluster:
            cluster_family = family
            cluster_start = recorded_at
        cluster.append((recorded_at, sequence, path))
    flush()
    return candidates


def _resolve_path_datetime(path: Path) -> datetime | None:
    voice = parse_voice_note_stem(path.stem)
    if voice is not None and voice[1] is not None:
        return voice[1]
    return parse_recording_datetime(path, fallback_mtime=True)


def _build_filename_regex_candidates(
    paths: list[Path],
    config: SerialDetectionConfig,
    *,
    patterns: Iterable[str],
    max_gap_seconds: int | None,
    same_day_days: int,
    profile_id: str,
    profile_name: str,
    profile_priority: int,
) -> list[_CandidateGroup]:
    compiled: list[re.Pattern[str]] = []
    for raw in patterns:
        try:
            compiled.append(re.compile(raw))
        except re.error:
            continue
    if not compiled:
        return []

    matched: list[tuple[datetime, Path]] = []
    for path in paths:
        stem = path.stem
        name = path.name
        if not any(rx.search(stem) or rx.search(name) for rx in compiled):
            continue
        dt = _resolve_path_datetime(path)
        if dt is None:
            continue
        matched.append((dt, path))
    if len(matched) < config.min_group_size:
        return []

    matched.sort(key=lambda item: (item[0], item[1].name))
    candidates: list[_CandidateGroup] = []
    cluster: list[tuple[datetime, Path]] = []

    def flush() -> None:
        if len(cluster) < config.min_group_size:
            cluster.clear()
            return
        first_dt = cluster[0][0]
        base_key = f"{profile_id or 'pattern'} {first_dt:%Y-%m-%d %H:%M:%S}"
        entries = tuple(
            _ParsedPath(
                path=path,
                base_key=base_key,
                index=idx,
                extension=path.suffix.lower(),
            )
            for idx, (_dt, path) in enumerate(cluster)
        )
        candidates.append(
            _CandidateGroup(
                base_key=base_key,
                entries=entries,
                matched_rule="filename_regex",
                confidence=_RULE_CONFIDENCE["filename_regex"],
                profile_id=profile_id,
                profile_name=profile_name,
                profile_priority=profile_priority,
            )
        )
        cluster.clear()

    for dt, path in matched:
        if cluster:
            prev_dt = cluster[-1][0]
            start = cluster[0][0]
            if same_day_days > 0 and _day_constraint_breaks(
                same_day_days=same_day_days, start=start, candidate=dt
            ):
                flush()
            elif (
                max_gap_seconds is not None
                and (dt - prev_dt).total_seconds() > max_gap_seconds
            ):
                flush()
        cluster.append((dt, path))
    flush()
    return candidates


def _build_candidates_for_rule(
    rule: str, paths: list[Path], config: SerialDetectionConfig
) -> list[_CandidateGroup]:
    if rule == "voice_note_run":
        return _build_voice_note_run_candidates(paths, config)

    confidence = _RULE_CONFIDENCE[rule]
    by_base: dict[str, list[_ParsedPath]] = defaultdict(list)

    for path in paths:
        parsed = _parse_for_rule(rule, path)
        if parsed is None:
            continue
        by_base[parsed.base_key].append(parsed)

    candidates: list[_CandidateGroup] = []
    for base_key, entries in by_base.items():
        if rule == "duplicate_suffix":
            has_duplicate = any(entry.index > 0 for entry in entries)
            if not has_duplicate:
                continue
        candidates.append(
            _CandidateGroup(
                base_key=base_key,
                entries=tuple(entries),
                matched_rule=rule,
                confidence=confidence,
            )
        )
    return candidates


def _same_extension(entries: tuple[_ParsedPath, ...]) -> bool:
    extensions = {entry.extension for entry in entries}
    return len(extensions) == 1


def _order_entries(entries: tuple[_ParsedPath, ...]) -> tuple[_ParsedPath, ...]:
    return tuple(sorted(entries, key=lambda e: (e.index, e.path.name)))


def _index_gap_warnings(
    indices: tuple[int | None, ...], max_gap: int | None
) -> tuple[str, ...]:
    if max_gap is None:
        return ()
    numeric = [idx for idx in indices if idx is not None]
    if len(numeric) < 2:
        return ()
    sorted_idx = sorted(numeric)
    warnings: list[str] = []
    for left, right in zip(sorted_idx, sorted_idx[1:]):
        gap = right - left - 1
        if gap > max_gap:
            warnings.append(
                f"Index gap of {gap} between part {left} and part {right} "
                f"(max allowed gap is {max_gap})."
            )
    return tuple(warnings)


def _candidate_rank(candidate: _CandidateGroup) -> tuple[int, int, int]:
    rule_rank = len(_RULE_PRIORITY) - _RULE_PRIORITY.index(candidate.matched_rule)
    # Lower profile_priority wins (serial builtins default to 10).
    return (
        _CONFIDENCE_RANK[candidate.confidence],
        rule_rank,
        -candidate.profile_priority,
    )


def _to_serial_group(
    candidate: _CandidateGroup,
    *,
    config: SerialDetectionConfig,
) -> SerialGroup | None:
    if len(candidate.entries) < config.min_group_size:
        return None
    ordered = _order_entries(candidate.entries)
    if config.require_same_extension and not _same_extension(ordered):
        return None

    indices = tuple(entry.index for entry in ordered)
    warnings = (
        ()
        if candidate.matched_rule in {"voice_note_run", "filename_regex"}
        else _index_gap_warnings(indices, config.max_index_gap)
    )

    return SerialGroup(
        base_key=candidate.base_key,
        ordered_paths=tuple(entry.path for entry in ordered),
        confidence=candidate.confidence,
        matched_rule=candidate.matched_rule,
        indices=indices,
        warnings=warnings,
        profile_id=candidate.profile_id,
        profile_name=candidate.profile_name,
    )


def _choose_groups(
    all_candidates: list[_CandidateGroup],
    *,
    config: SerialDetectionConfig,
) -> list[SerialGroup]:
    ranked_candidates = sorted(
        all_candidates,
        key=lambda c: (
            -_candidate_rank(c)[0],
            -_candidate_rank(c)[1],
            -_candidate_rank(c)[2],
            c.base_key,
        ),
    )

    assigned_paths: set[Path] = set()
    chosen_groups: list[SerialGroup] = []

    for candidate in ranked_candidates:
        entry_paths = {entry.path for entry in candidate.entries}
        if entry_paths & assigned_paths:
            continue
        group = _to_serial_group(candidate, config=config)
        if group is None:
            continue
        chosen_groups.append(group)
        assigned_paths.update(group.ordered_paths)

    chosen_groups.sort(key=lambda g: (g.base_key, str(g.ordered_paths[0])))
    return chosen_groups


def detect_serial_audio_groups(
    paths: Iterable[Path | str],
    config: SerialDetectionConfig | None = None,
) -> list[SerialGroup]:
    """
    Detect groups of audio paths that look like serial parts of one recording.

    Each path appears in at most one group. When multiple rules match, the
    highest-confidence rule wins; ties break by rule priority order.

    When ``config`` is omitted, builtin merge source profiles drive detection
    (20-minute voice-note gap). Pass an explicit ``config`` for the legacy
    single-pass rule path (tests). The Merge UI loads on-disk profiles via
    ``detect_merge_groups``.
    """
    if config is not None:
        return _detect_with_legacy_config(paths, config)

    try:
        from transcriptx.core.audio.merge_profiles import builtin_merge_source_profiles

        return detect_merge_groups(paths, profiles=builtin_merge_source_profiles())
    except Exception:
        return _detect_with_legacy_config(paths, SerialDetectionConfig())


def _detect_with_legacy_config(
    paths: Iterable[Path | str],
    config: SerialDetectionConfig,
) -> list[SerialGroup]:
    if not config.enabled:
        return []

    # v1: sibling scan is reserved and intentionally not implemented.
    _ = config.scan_siblings_in_library

    normalized = _normalize_paths(paths)
    if len(normalized) < config.min_group_size:
        return []

    enabled = [rule for rule in _RULE_PRIORITY if rule in config.enabled_rules]
    all_candidates: list[_CandidateGroup] = []
    for rule in enabled:
        all_candidates.extend(_build_candidates_for_rule(rule, normalized, config))
    return _choose_groups(all_candidates, config=config)


def detect_merge_groups(
    paths: Iterable[Path | str],
    *,
    profiles: Iterable[Any] | None = None,
    config: SerialDetectionConfig | None = None,
) -> list[SerialGroup]:
    """Detect merge groups using merge source profiles."""
    from transcriptx.core.audio.merge_profiles import (
        MergeSourceProfile,
        builtin_merge_source_profiles,
        max_gap_hours_to_seconds,
    )

    if config is None:
        config = SerialDetectionConfig()
    if not config.enabled:
        return []

    if profiles is None:
        profile_list: list[MergeSourceProfile] = list(builtin_merge_source_profiles())
    else:
        profile_list = [p for p in profiles if getattr(p, "enabled", True)]

    normalized = _normalize_paths(paths)
    if len(normalized) < config.min_group_size:
        return []

    all_candidates: list[_CandidateGroup] = []
    for profile in sorted(profile_list, key=lambda p: (p.priority, p.id)):
        match = profile.match
        grouping = profile.grouping
        if match.kind == "builtin_serial":
            rules = [
                rule
                for rule in _RULE_PRIORITY
                if rule in match.builtin_rules and rule != "voice_note_run"
            ]
            for rule in rules:
                for candidate in _build_candidates_for_rule(rule, normalized, config):
                    all_candidates.append(
                        _CandidateGroup(
                            base_key=candidate.base_key,
                            entries=candidate.entries,
                            matched_rule=candidate.matched_rule,
                            confidence=candidate.confidence,
                            profile_id=profile.id,
                            profile_name=profile.name,
                            profile_priority=profile.priority,
                        )
                    )
        elif match.kind == "voice_note_family":
            gap_seconds = (
                None
                if grouping.mode == "serial"
                else max_gap_hours_to_seconds(grouping.max_gap_hours)
            )
            # serial mode for a family profile still uses seq/time clustering
            # but with an unlimited gap (always merge within family constraints).
            if grouping.mode == "serial":
                gap_seconds = None
            all_candidates.extend(
                _build_voice_note_run_candidates(
                    normalized,
                    config,
                    families=match.families,
                    max_gap_seconds=gap_seconds,
                    same_day_days=grouping.same_day_days,
                    profile_id=profile.id,
                    profile_name=profile.name,
                    profile_priority=profile.priority,
                )
            )
        elif match.kind == "filename_regex":
            gap_seconds = max_gap_hours_to_seconds(grouping.max_gap_hours)
            if grouping.mode == "serial":
                gap_seconds = None
            all_candidates.extend(
                _build_filename_regex_candidates(
                    normalized,
                    config,
                    patterns=match.patterns,
                    max_gap_seconds=gap_seconds,
                    same_day_days=grouping.same_day_days,
                    profile_id=profile.id,
                    profile_name=profile.name,
                    profile_priority=profile.priority,
                )
            )

    return _choose_groups(all_candidates, config=config)


def partition_dismissed_serial_groups(
    groups: Iterable[SerialGroup],
    dismissed_keys: Iterable[str],
) -> tuple[list[SerialGroup], list[SerialGroup]]:
    """Split groups into visible vs hidden using ``SerialGroup.dismissal_key``."""
    dismissed = set(dismissed_keys)
    visible: list[SerialGroup] = []
    hidden: list[SerialGroup] = []
    for group in groups:
        if group.dismissal_key in dismissed:
            hidden.append(group)
        else:
            visible.append(group)
    return visible, hidden


def partition_serial_group_visibility(
    groups: Iterable[SerialGroup],
    *,
    session_keys: Iterable[str],
    permanent_keys: Iterable[str],
) -> tuple[list[SerialGroup], list[SerialGroup], list[SerialGroup]]:
    """Split groups into visible, session-hidden, and never-suggest lists.

    Permanent dismissal wins over session hide.
    """
    session = set(session_keys)
    permanent = set(permanent_keys)
    visible: list[SerialGroup] = []
    hidden: list[SerialGroup] = []
    never_suggest: list[SerialGroup] = []
    for group in groups:
        key = group.dismissal_key
        if key in permanent:
            never_suggest.append(group)
        elif key in session:
            hidden.append(group)
        else:
            visible.append(group)
    return visible, hidden, never_suggest


def merged_output_filename(base_key: str) -> str:
    """Default merge output name for a serial group."""
    return f"{base_key}_merged.mp3"
