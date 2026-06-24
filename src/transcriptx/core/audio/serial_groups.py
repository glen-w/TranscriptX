"""
Detect serial / split audio recordings from filename patterns.

Pure logic — no UI dependencies.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from transcriptx.core.utils._path_core import strip_duplicate_filename_suffix

Confidence = Literal["high", "medium", "low"]

_CONFIDENCE_RANK: dict[Confidence, int] = {"high": 3, "medium": 2, "low": 1}

_RULE_CONFIDENCE: dict[str, Confidence] = {
    "timestamp_suffix": "high",
    "part_suffix": "high",
    "numeric_index": "medium",
    "duplicate_suffix": "medium",
}

_RULE_PRIORITY: tuple[str, ...] = (
    "timestamp_suffix",
    "part_suffix",
    "numeric_index",
    "duplicate_suffix",
)

_TIMESTAMP_SUFFIX_RE = re.compile(r"^(\d{8,})[_-](\d+)$")
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
        "numeric_index",
        "part_suffix",
        "duplicate_suffix",
    )
    max_index_gap: int | None = 3
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
    if not match:
        return None
    return match.group(1), int(match.group(2))


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


def _build_candidates_for_rule(rule: str, paths: list[Path]) -> list[_CandidateGroup]:
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
    warnings = _index_gap_warnings(indices, config.max_index_gap)

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
        all_candidates.extend(_build_candidates_for_rule(rule, normalized))

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


def merged_output_filename(base_key: str) -> str:
    """Default merge output name for a serial group."""
    return f"{base_key}_merged.mp3"
