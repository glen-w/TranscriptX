from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR  # type: ignore[import-untyped]

LANGUAGE_CODE_RE = re.compile(r"^[a-z]{2}$")


def normalize_language_code(language: str | None) -> str | None:
    """Normalize language code, returning None for auto/empty values."""
    if language is None:
        return None
    code = str(language).strip().lower()
    if not code or code in {"auto", "none"}:
        return None
    return code


def is_valid_language_code(language: str) -> bool:
    """Return True for two-letter codes or 'auto'."""
    if not language:
        return False
    code = str(language).strip().lower()
    if code == "auto":
        return True
    return bool(LANGUAGE_CODE_RE.fullmatch(code))


def get_transcript_path_for_language(base_name: str, language: str | None) -> Path:
    """Return the target transcript path for the given language."""
    transcripts_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    language_code = normalize_language_code(language)
    if language_code is None or language_code == "en":
        return transcripts_dir / f"{base_name}.json"
    return transcripts_dir / language_code / f"{base_name}_{language_code}.json"


def get_transcript_candidates_for_language(
    base_name: str, language: str | None
) -> list[Path]:
    """Return possible transcript paths for the given language."""
    transcripts_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    language_code = normalize_language_code(language)
    if language_code is None or language_code == "en":
        return [
            transcripts_dir / f"{base_name}.json",
            transcripts_dir / f"{base_name}_transcript_diarised.json",
        ]
    return [transcripts_dir / language_code / f"{base_name}_{language_code}.json"]


def transcript_exists_for_language(base_name: str, language: str | None) -> bool:
    """Return True if any transcript exists for the given language."""
    return any(path.exists() for path in get_transcript_candidates_for_language(base_name, language))


def ensure_parent_dir(path: Path) -> None:
    """Ensure the parent directory exists."""
    path.parent.mkdir(parents=True, exist_ok=True)


def filter_existing_paths(paths: Iterable[Path]) -> list[Path]:
    """Return only the paths that exist."""
    return [path for path in paths if path.exists()]
