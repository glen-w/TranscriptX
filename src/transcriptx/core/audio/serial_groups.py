"""
Detect serial / split audio recordings from filename patterns.

Pure logic — no UI dependencies.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Literal

from transcriptx.core.utils._path_core import strip_duplicate_filename_suffix
from transcriptx.core.utils.rename.smart_name import parse_voice_note_stem

Confidence = Literal["high", "medium", "low"]

_CONFIDENCE_RANK: dict[Confidence, int] = {"high": 3, "medium": 2, "low": 1}

_RULE_CONFIDENCE: dict[str, Confidence] = {
    "timestamp_suffix": "high",
    "part_suffix": "high",
    "voice_note_run": "medium",
    "numeric_index": "medium",
    "duplicate_suffix": "medium",
}

_RULE_LABELS: dict[str, str] = {
    "timestamp_suffix": "timestamp suffix",
    "part_suffix": "part suffix",
    "voice_note_run": "voice note run",
    "numeric_index": "numeric index",
    "duplicate_suffix": "duplicate suffix",
}

_RULE_PRIORITY: tuple[str, ...] = (
    "timestamp_suffix",
    "part_suffix",
    "voice_note_run",
    "numeric_index",
    "duplicate_suffix",
)

_TIMESTAMP_SUFFIX_RE = re.compile(r"^(\d{8,})[_-](\d+)$")
_TIMESTAMP_BARE_RE = re.compile(r"^(\d{8,})$")
_PART_SUFFIX_RE = re.compile(
    r"^(.+?)(?:[\s_.-]+)?part(?:[\s_.-]+)?(\d+)$",
    re.IGNORECASE,
)
_NUMERIC_INDEX_RE = re.compile(r"^(.+?)[_-](\d{2,})$")
_DUPLICATE_INDEX_RE = re.compile(r" \(([1-9]\d{0,2})\)$")


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


def _build_voice_note_run_candidates(
    paths: list[Path],
    config: SerialDetectionConfig,
) -> list[_CandidateGroup]:
    parsed: list[tuple[str, datetime | None, int | None, Path]] = []
    for path in paths:
        result = parse_voice_note_stem(path.stem)
        if result is None:
            continue
        family, recorded_at, sequence = result
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
    max_gap = max(0, int(config.voice_note_max_gap_seconds))
    max_seq_gap = (
        config.max_index_gap if config.max_index_gap is not None else 3
    )
    candidates: list[_CandidateGroup] = []
    cluster: list[tuple[datetime | None, int | None, Path]] = []
    cluster_family = ""

    def flush() -> None:
        if len(cluster) < config.min_group_size:
            cluster.clear()
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
            )
        )
        cluster.clear()

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
        # Date+sequence media (WhatsApp Android PTT/AUD): same day, small WA gap.
        if sequence is not None and prev_seq is not None:
            if recorded_at.date() != prev_dt.date():
                return True
            return (sequence - prev_seq - 1) > max_seq_gap
        # Pure timestamps: wall-clock gap.
        return (recorded_at - prev_dt).total_seconds() > max_gap

    for family, recorded_at, sequence, path in parsed:
        if _breaks_cluster(family, recorded_at, sequence):
            flush()
        if not cluster:
            cluster_family = family
        cluster.append((recorded_at, sequence, path))
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


def _candidate_rank(candidate: _CandidateGroup) -> tuple[int, int]:
    rule_rank = len(_RULE_PRIORITY) - _RULE_PRIORITY.index(candidate.matched_rule)
    return (_CONFIDENCE_RANK[candidate.confidence], rule_rank)


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
        if candidate.matched_rule == "voice_note_run"
        else _index_gap_warnings(indices, config.max_index_gap)
    )

    return SerialGroup(
        base_key=candidate.base_key,
        ordered_paths=tuple(entry.path for entry in ordered),
        confidence=candidate.confidence,
        matched_rule=candidate.matched_rule,
        indices=indices,
        warnings=warnings,
    )


def detect_serial_audio_groups(
    paths: Iterable[Path | str],
    config: SerialDetectionConfig | None = None,
) -> list[SerialGroup]:
    """
    Detect groups of audio paths that look like serial parts of one recording.

    Each path appears in at most one group. When multiple rules match, the
    highest-confidence rule wins; ties break by rule priority order.
    """
    if config is None:
        config = SerialDetectionConfig()

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

    # Sort candidates so higher-priority wins during greedy assignment.
    ranked_candidates = sorted(
        all_candidates,
        key=lambda c: (-_candidate_rank(c)[0], -_candidate_rank(c)[1], c.base_key),
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


def merged_output_filename(base_key: str) -> str:
    """Default merge output name for a serial group."""
    return f"{base_key}_merged.mp3"
