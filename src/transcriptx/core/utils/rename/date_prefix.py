"""Date-prefix helpers for rename prompts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from transcriptx.core.utils.logger import get_logger, log_error

logger = get_logger()


def extract_date_prefix_from_filename(filename: str) -> str:
    """Extract date prefix (YYMMDD_) from filename."""
    try:
        stem = Path(filename).stem
        # Prefer structured device datetime parsers (covers RYYYYMMDD-HHMMSS, etc.).
        try:
            from transcriptx.core.utils.rename.smart_name import (
                parse_recording_datetime_from_stem,
            )

            parsed = parse_recording_datetime_from_stem(stem)
            if parsed is not None:
                return parsed.strftime("%y%m%d_")
        except Exception:
            pass
        if len(stem) >= 8 and stem[:8].isdigit():
            year = stem[:4]
            month = stem[4:6]
            day = stem[6:8]
            if int(month) in range(1, 13) and int(day) in range(1, 32):
                return f"{year[2:4]}{month}{day}_"
        if len(stem) >= 6 and stem[:6].isdigit():
            yy, mm, dd = stem[:2], stem[2:4], stem[4:6]
            if int(mm) in range(1, 13) and int(dd) in range(1, 32):
                return f"{yy}{mm}{dd}_"
        return ""
    except (ValueError, IndexError):
        return ""


def extract_date_prefix(audio_file_path: Path) -> str:
    """Extract date prefix (YYMMDD_) from audio file name or mtime."""
    try:
        date_prefix = extract_date_prefix_from_filename(audio_file_path.name)
        if date_prefix:
            return date_prefix
        if not audio_file_path.exists():
            logger.warning("Audio file not found: %s", audio_file_path)
            return ""
        mtime = audio_file_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%y%m%d_")
    except Exception as e:
        log_error(
            "FILE_RENAME",
            f"Error extracting date from {audio_file_path}: {e}",
            exception=e,
        )
        return ""


def extract_date_prefix_from_transcript(transcript_path: str | Path) -> str:
    """Extract date prefix (YYMMDD_) from transcript filename or mtime."""
    try:
        transcript_file = Path(transcript_path)
        date_prefix = extract_date_prefix_from_filename(transcript_file.name)
        if date_prefix:
            return date_prefix
        if not transcript_file.exists():
            logger.info(
                "Transcript file not found for date extraction: %s", transcript_path
            )
            return ""
        mtime = transcript_file.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%y%m%d_")
    except Exception as e:
        log_error(
            "FILE_RENAME",
            f"Error extracting date from transcript {transcript_path}: {e}",
            exception=e,
        )
        return ""


def resolve_rename_date_prefix(
    transcript_path: str | Path,
    *,
    audio_path: Path | None = None,
) -> str:
    """Resolve ``YYMMDD_`` from linked audio (preferred) then transcript.

    Audio lookup uses ``find_original_audio_file`` when ``audio_path`` is omitted.
    """
    transcript = Path(transcript_path)
    audio = audio_path
    if audio is None:
        try:
            from transcriptx.core.utils.rename.audio_association import (
                find_original_audio_file,
            )

            found = find_original_audio_file(str(transcript))
            if found is not None:
                audio = found
        except Exception as e:
            log_error(
                "FILE_RENAME",
                f"Error resolving audio for date prefix ({transcript}): {e}",
                exception=e,
            )
            audio = None
    if audio is not None:
        try:
            if Path(audio).exists():
                prefix = extract_date_prefix(Path(audio))
                if prefix:
                    return prefix
        except OSError:
            pass
    return extract_date_prefix_from_transcript(transcript)


def _smart_rename_settings() -> tuple[str, str, bool]:
    """Return (mode, pattern, legacy_prefill)."""
    try:
        from transcriptx.core.utils.config_provider import get_config

        cfg = get_config()
        input_cfg = getattr(cfg, "input", None)
        mode = str(getattr(input_cfg, "smart_rename_mode", "suggest_import") or "suggest_import")
        pattern = str(
            getattr(input_cfg, "smart_rename_pattern", "{yymmdd}_{period}_{n}")
            or "{yymmdd}_{period}_{n}"
        )
        legacy = bool(getattr(input_cfg, "prefill_rename_with_date_prefix", True))
        return mode, pattern, legacy
    except Exception:
        return "suggest_import", "{yymmdd}_{period}_{n}", True


def suggest_rename_base_name(
    transcript_path: str | Path,
    *,
    prefill_with_date_prefix: bool = True,
    audio_path: Path | None = None,
    smart_rename_mode: str | None = None,
    smart_rename_pattern: str | None = None,
) -> str:
    """Suggested rename stem for CLI/web prompts (not a second validation path).

    When smart rename mode is active (not ``off``), prefer the deterministic
    pattern-based suggestion. Otherwise, when prefill is enabled, auto-prefixes
    the current stem with ``YYMMDD_`` unless the stem already starts with that
    prefix. Submitters must still run ``validate_target_name`` /
    ``normalize_base_name`` before rename.
    """
    transcript = Path(transcript_path)
    stem = transcript.stem

    mode, pattern, legacy_prefill = _smart_rename_settings()
    if smart_rename_mode is not None:
        mode = smart_rename_mode
    if smart_rename_pattern is not None:
        pattern = smart_rename_pattern

    if mode != "off":
        try:
            from transcriptx.core.utils.rename.smart_name import (
                suggest_smart_rename_base_name,
            )

            suggestion = suggest_smart_rename_base_name(
                transcript,
                mode=mode,
                pattern=pattern,
                audio_path=audio_path,
            )
            if suggestion is not None and suggestion.full:
                return suggestion.full
        except Exception as e:
            log_error(
                "FILE_RENAME",
                f"Smart rename suggestion failed for {transcript}: {e}",
                exception=e,
            )

    # Legacy bridge: when smart mode is off (or smart suggestion failed),
    # honour the caller's / config date-prefix prefill flag.
    use_prefill = prefill_with_date_prefix
    if smart_rename_mode is None and mode == "off":
        use_prefill = legacy_prefill and prefill_with_date_prefix
    if not use_prefill:
        return stem
    prefix = resolve_rename_date_prefix(transcript, audio_path=audio_path)
    if not prefix:
        return stem
    if stem.startswith(prefix):
        return stem
    return f"{prefix}{stem}"
