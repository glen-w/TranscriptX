"""Deterministic smart rename from device filename date/time patterns."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Literal

from transcriptx.core.utils.logger import get_logger

logger = get_logger()

SmartRenameMode = Literal[
    "auto_import",
    "suggest_import",
    "suggest_rename_only",
    "off",
]

DEFAULT_SMART_RENAME_PATTERN = "{yymmdd}_{period}_{n}"
KNOWN_PATTERN_TOKENS = frozenset(
    {
        "yymmdd",
        "yyyymmdd",
        "yyyy",
        "yy",
        "mm",
        "dd",
        "hhmmss",
        "hhmm",
        "hh",
        "period",
        "n",
        "stem",
    }
)
DATE_ROOT_TOKENS = frozenset({"yymmdd", "yyyymmdd", "yyyy", "yy", "mm", "dd"})
_TOKEN_RE = re.compile(r"\{([a-z0-9_]+)\}")

# Device filename patterns (first match wins).
_RE_R_YYYYMMDD_HHMMSS = re.compile(
    r"^R(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})-(?P<H>\d{2})(?P<M>\d{2})(?P<S>\d{2})$"
)
_RE_YYYYMMDDHHMMSS = re.compile(
    r"^(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})(?P<H>\d{2})(?P<M>\d{2})(?P<S>\d{2})$"
)
_RE_YYMMDD_HHMMSS = re.compile(
    r"^(?P<y>\d{2})(?P<m>\d{2})(?P<d>\d{2})-(?P<H>\d{2})(?P<M>\d{2})(?P<S>\d{2})$"
)
_RE_LEADING_YYYYMMDD = re.compile(r"^(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})")
_RE_LEADING_YYMMDD = re.compile(r"^(?P<y>\d{2})(?P<m>\d{2})(?P<d>\d{2})")


@dataclass(frozen=True)
class SmartRenameSuggestion:
    """Suggested rename stem plus UI helpers for the rename form."""

    full: str
    date_root: str
    token_bubbles: tuple[str, ...]
    parsed_datetime: datetime | None = None
    pattern_used: str = DEFAULT_SMART_RENAME_PATTERN
    used_fallback: bool = False


def period_for_hour(hour: int) -> str:
    """Map hour (0-23) to morning/afternoon/evening/night."""
    if 5 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 16:
        return "afternoon"
    if 17 <= hour <= 20:
        return "evening"
    return "night"


def _valid_ymd(year: int, month: int, day: int) -> bool:
    try:
        datetime(year, month, day)
        return True
    except ValueError:
        return False


def _valid_hms(hour: int, minute: int, second: int) -> bool:
    return 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59


def _century_year(yy: int) -> int:
    """Map two-digit year to four-digit; 00-68 -> 2000+, 69-99 -> 1900+."""
    return 2000 + yy if yy <= 68 else 1900 + yy


def parse_recording_datetime_from_stem(stem: str) -> datetime | None:
    """Parse recording datetime from a device filename stem."""
    s = (stem or "").strip()
    if not s:
        return None

    m = _RE_R_YYYYMMDD_HHMMSS.match(s)
    if m:
        y, mo, d = int(m["y"]), int(m["m"]), int(m["d"])
        H, M, S = int(m["H"]), int(m["M"]), int(m["S"])
        if _valid_ymd(y, mo, d) and _valid_hms(H, M, S):
            return datetime(y, mo, d, H, M, S)

    m = _RE_YYYYMMDDHHMMSS.match(s)
    if m:
        y, mo, d = int(m["y"]), int(m["m"]), int(m["d"])
        H, M, S = int(m["H"]), int(m["M"]), int(m["S"])
        if _valid_ymd(y, mo, d) and _valid_hms(H, M, S):
            return datetime(y, mo, d, H, M, S)

    m = _RE_YYMMDD_HHMMSS.match(s)
    if m:
        y = _century_year(int(m["y"]))
        mo, d = int(m["m"]), int(m["d"])
        H, M, S = int(m["H"]), int(m["M"]), int(m["S"])
        if _valid_ymd(y, mo, d) and _valid_hms(H, M, S):
            return datetime(y, mo, d, H, M, S)

    m = _RE_LEADING_YYYYMMDD.match(s)
    if m:
        y, mo, d = int(m["y"]), int(m["m"]), int(m["d"])
        if _valid_ymd(y, mo, d):
            return datetime(y, mo, d)

    m = _RE_LEADING_YYMMDD.match(s)
    if m:
        y = _century_year(int(m["y"]))
        mo, d = int(m["m"]), int(m["d"])
        if _valid_ymd(y, mo, d):
            return datetime(y, mo, d)

    return None


def parse_recording_datetime(
    stem_or_path: str | Path,
    *,
    fallback_mtime: bool = True,
) -> datetime | None:
    """Parse datetime from stem or path; optionally fall back to file mtime."""
    path = Path(stem_or_path)
    stem = path.stem if path.suffix else path.name
    # Prefer raw stem when caller passed a bare name without path separators.
    if isinstance(stem_or_path, str) and ("/" not in stem_or_path and "\\" not in stem_or_path):
        stem = Path(stem_or_path).stem

    parsed = parse_recording_datetime_from_stem(stem)
    if parsed is not None:
        return parsed

    if not fallback_mtime:
        return None
    try:
        if path.exists() and path.is_file():
            return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        pass
    return None


def extract_pattern_tokens(pattern: str) -> list[str]:
    """Return ordered unique token names referenced by ``pattern``."""
    seen: list[str] = []
    for name in _TOKEN_RE.findall(pattern or ""):
        if name not in seen:
            seen.append(name)
    return seen


def validate_smart_rename_pattern(pattern: str) -> tuple[bool, str]:
    """Validate a smart rename pattern string."""
    raw = (pattern or "").strip()
    if not raw:
        return False, "Pattern must not be empty."
    tokens = extract_pattern_tokens(raw)
    unknown = [t for t in tokens if t not in KNOWN_PATTERN_TOKENS]
    if unknown:
        return False, f"Unknown pattern token(s): {', '.join(unknown)}"
    return True, ""


def resolve_smart_rename_pattern(pattern: str | None) -> str:
    """Return a usable pattern, falling back to the default on invalid input."""
    candidate = (pattern or "").strip() or DEFAULT_SMART_RENAME_PATTERN
    ok, reason = validate_smart_rename_pattern(candidate)
    if ok:
        return candidate
    logger.warning(
        "Invalid smart_rename_pattern %r (%s); using default %s",
        pattern,
        reason,
        DEFAULT_SMART_RENAME_PATTERN,
    )
    return DEFAULT_SMART_RENAME_PATTERN


def build_rename_tokens(
    dt: datetime,
    *,
    stem: str = "",
) -> dict[str, str]:
    """Build the token map for pattern rendering (``n`` resolved later)."""
    return {
        "yymmdd": dt.strftime("%y%m%d"),
        "yyyymmdd": dt.strftime("%Y%m%d"),
        "yyyy": dt.strftime("%Y"),
        "yy": dt.strftime("%y"),
        "mm": dt.strftime("%m"),
        "dd": dt.strftime("%d"),
        "hhmmss": dt.strftime("%H%M%S"),
        "hhmm": dt.strftime("%H%M"),
        "hh": dt.strftime("%H"),
        "period": period_for_hour(dt.hour),
        "stem": stem,
        # Placeholder until collision resolution; keep key present for substitution.
        "n": "1",
    }


def _prefix_before_n(pattern: str, tokens: dict[str, str]) -> str:
    """Render the pattern up to (but not including) the first ``{n}`` token."""
    idx = pattern.find("{n}")
    if idx < 0:
        return _substitute_known(pattern, tokens, skip={"n"})
    return _substitute_known(pattern[:idx], tokens, skip={"n"})


def _substitute_known(
    template: str, tokens: dict[str, str], *, skip: set[str] | None = None
) -> str:
    skip = skip or set()

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in skip:
            return match.group(0)
        return tokens.get(name, match.group(0))

    return _TOKEN_RE.sub(repl, template)


def next_sequence_number(
    prefix: str,
    existing_stems: Iterable[str],
    *,
    start: int = 1,
) -> int:
    """Next free positive integer for stems that begin with ``prefix`` + digits."""
    if not prefix:
        used = set()
        for stem in existing_stems:
            m = re.fullmatch(r"(\d+)", stem)
            if m:
                used.add(int(m.group(1)))
        n = max(start, 1)
        while n in used:
            n += 1
        return n

    pattern = re.compile(
        r"^" + re.escape(prefix) + r"(\d+)(?:$|[^0-9])"
    )
    used: set[int] = set()
    for stem in existing_stems:
        m = pattern.match(stem)
        if m:
            used.add(int(m.group(1)))
    n = max(start, 1)
    while n in used:
        n += 1
    return n


def list_transcript_stems(transcripts_dir: str | Path | None) -> list[str]:
    """List ``.json`` stems in the transcripts directory (non-recursive)."""
    if transcripts_dir is None:
        return []
    root = Path(transcripts_dir)
    if not root.is_dir():
        return []
    stems: list[str] = []
    try:
        for path in root.iterdir():
            if path.is_file() and path.suffix.lower() == ".json":
                stems.append(path.stem)
    except OSError:
        return []
    return stems


def render_smart_rename(
    pattern: str,
    tokens: dict[str, str],
    *,
    existing_stems: Iterable[str] | None = None,
    exclude_stem: str | None = None,
) -> str:
    """Render ``pattern`` with tokens, assigning ``{n}`` for uniqueness."""
    resolved = resolve_smart_rename_pattern(pattern)
    working = dict(tokens)
    stems = [s for s in (existing_stems or []) if s != exclude_stem]
    if "{n}" in resolved:
        prefix = _prefix_before_n(resolved, working)
        working["n"] = str(next_sequence_number(prefix, stems))
    rendered = _substitute_known(resolved, working)
    # Safety: if collision remains (pattern without {n}), append _N.
    if rendered in stems:
        n = 2
        candidate = f"{rendered}_{n}"
        while candidate in stems:
            n += 1
            candidate = f"{rendered}_{n}"
        return candidate
    return rendered


def date_root_from_tokens(tokens: dict[str, str], pattern: str) -> str:
    """Preferred date root for rename prefill (``YYMMDD_`` when available)."""
    if "yymmdd" in tokens:
        return f"{tokens['yymmdd']}_"
    # Derive from pattern order when yymmdd absent.
    for name in extract_pattern_tokens(pattern):
        if name in DATE_ROOT_TOKENS and name in tokens:
            return f"{tokens[name]}_"
    return ""


def bubble_tokens_for_suggestion(
    tokens: dict[str, str],
    pattern: str,
    *,
    sequence: str,
) -> tuple[str, ...]:
    """Clickable append bubbles (non-date tokens useful while composing a name)."""
    ordered: list[str] = []
    pattern_tokens = extract_pattern_tokens(pattern)

    def _add(value: str) -> None:
        v = (value or "").strip()
        if v and v not in ordered:
            ordered.append(v)

    if "period" in tokens:
        _add(tokens["period"])
    _add(sequence)
    if "hhmm" in tokens:
        _add(tokens["hhmm"])
    if "hhmmss" in tokens:
        _add(tokens["hhmmss"])
    for name in pattern_tokens:
        if name in DATE_ROOT_TOKENS or name in {"n", "stem"}:
            continue
        if name in tokens:
            _add(tokens[name])
    return tuple(ordered)


def append_token_to_name(current: str, token: str) -> str:
    """Append a bubble token to a rename target with underscore separators."""
    base = (current or "").rstrip()
    piece = (token or "").strip().strip("_")
    if not piece:
        return base
    if not base:
        return piece
    if base.endswith("_"):
        return f"{base}{piece}"
    return f"{base}_{piece}"


def smart_rename_applies_on_import(mode: str) -> bool:
    return mode in {"auto_import", "suggest_import"}


def smart_rename_auto_on_import(mode: str) -> bool:
    return mode == "auto_import"


def smart_rename_suggests_in_rename_workflow(mode: str) -> bool:
    return mode in {"auto_import", "suggest_import", "suggest_rename_only"}


def suggest_smart_rename_base_name(
    transcript_path: str | Path,
    *,
    mode: str = "suggest_import",
    pattern: str = DEFAULT_SMART_RENAME_PATTERN,
    audio_path: Path | None = None,
    existing_stems: Iterable[str] | None = None,
    transcripts_dir: str | Path | None = None,
) -> SmartRenameSuggestion | None:
    """Build a smart rename suggestion when mode is not ``off``.

    Returns ``None`` when smart rename is disabled or datetime cannot be parsed
    (caller should fall back to legacy date-prefix / stem behaviour).
    """
    if mode == "off":
        return None

    path = Path(transcript_path)
    dt = None
    if audio_path is not None:
        dt = parse_recording_datetime(audio_path, fallback_mtime=True)
    if dt is None:
        dt = parse_recording_datetime(path, fallback_mtime=True)
    if dt is None:
        return None

    resolved_pattern = resolve_smart_rename_pattern(pattern)
    tokens = build_rename_tokens(dt, stem=path.stem)
    stems = list(existing_stems) if existing_stems is not None else None
    if stems is None:
        root = transcripts_dir
        if root is None:
            try:
                from transcriptx.core.utils._path_core import get_transcript_dir

                root = get_transcript_dir()
            except Exception:
                root = path.parent
        stems = list_transcript_stems(root)

    full = render_smart_rename(
        resolved_pattern,
        tokens,
        existing_stems=stems,
        exclude_stem=path.stem,
    )
    # Re-read n from rendered when pattern includes {n}.
    seq = tokens["n"]
    if "{n}" in resolved_pattern:
        prefix = _prefix_before_n(resolved_pattern, tokens)
        if full.startswith(prefix):
            rest = full[len(prefix) :]
            m = re.match(r"(\d+)", rest)
            if m:
                seq = m.group(1)
                tokens = {**tokens, "n": seq}

    return SmartRenameSuggestion(
        full=full,
        date_root=date_root_from_tokens(tokens, resolved_pattern),
        token_bubbles=bubble_tokens_for_suggestion(
            tokens, resolved_pattern, sequence=seq
        ),
        parsed_datetime=dt,
        pattern_used=resolved_pattern,
        used_fallback=parse_recording_datetime_from_stem(path.stem) is None
        and (
            audio_path is None
            or parse_recording_datetime_from_stem(Path(audio_path).stem) is None
        ),
    )
