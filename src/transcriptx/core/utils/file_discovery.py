"""
File discovery utilities: find transcripts and resolve recording folder paths.

Pure path/discovery logic extracted from the CLI layer so that app, io, and
web layers can use it without importing from the CLI package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from transcriptx.core.utils.paths import (
    RECORDINGS_DIR,
    DIARISED_TRANSCRIPTS_DIR,
)
from transcriptx.core.utils.path_utils import get_transcript_dir  # noqa: F401

# Supported audio extensions for merge, convert, preprocessing, and batch
AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg", ".m4a", ".flac", ".aac")

_TRANSCRIPT_PARENT_EXCLUSIONS = {
    "outputs",
    "analysis",
    "charts",
    "metadata",
    "stats",
    "sentiment",
    "emotion",
    "ner",
    "word_clouds",
    "networks",
}
_TRANSCRIPT_FILENAME_EXCLUSIONS = (
    "_summary.json",
    "_manifest.json",
    "_simplified_transcript.json",
)


def _is_excluded_transcript_path(path: Path) -> bool:
    if path.name.endswith(_TRANSCRIPT_FILENAME_EXCLUSIONS):
        return True
    for parent in path.parents:
        if parent.name in _TRANSCRIPT_PARENT_EXCLUSIONS:
            return True
    return False


def _resolve_transcript_discovery_root(root: Optional[Path]) -> Optional[Path]:
    if root is not None:
        return Path(root)

    from transcriptx.core.utils.config import get_config

    config_obj = get_config()
    default_folder = Path(config_obj.output.default_transcript_folder)
    if default_folder.exists():
        return default_folder

    diarised_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    if diarised_dir.exists():
        return diarised_dir

    return None


def discover_all_transcript_paths(root: Optional[Path] = None) -> list[Path]:
    """
    Discover all transcript JSON paths using deterministic rules.

    Root selection:
      1) provided root
      2) config.output.default_transcript_folder if it exists
      3) DIARISED_TRANSCRIPTS_DIR if it exists
      4) else return []
    """
    root_path = _resolve_transcript_discovery_root(root)
    if root_path is None:
        return []

    transcripts_subdir = root_path / "transcripts"
    search_root = transcripts_subdir if transcripts_subdir.exists() else root_path

    resolved_paths: list[Path] = []
    seen: set[str] = set()
    for path in search_root.rglob("*.json"):
        if transcripts_subdir.exists() and transcripts_subdir != search_root:
            continue
        if not transcripts_subdir.exists() and _is_excluded_transcript_path(path):
            continue
        resolved = path.resolve()
        resolved_key = str(resolved)
        if resolved_key in seen:
            continue
        seen.add(resolved_key)
        resolved_paths.append(resolved)

    return sorted(resolved_paths, key=lambda p: str(p))


def get_recordings_folder_start_path(config) -> Path:
    """
    Get the first existing recordings folder path from configuration.

    Iterates through the configured recordings folders list and returns the first
    existing folder path. If none exist, uses fallback logic to find the
    nearest existing parent or defaults to RECORDINGS_DIR.

    Args:
        config: TranscriptXConfig instance

    Returns:
        Path to the first existing recordings folder, or a fallback path if none exist
    """
    if not config.input.recordings_folders:
        return Path(RECORDINGS_DIR)

    for folder_path_str in config.input.recordings_folders:
        folder_path = Path(folder_path_str)
        if folder_path.exists():
            return folder_path

        current_check = folder_path
        while current_check != current_check.parent:
            if current_check.exists():
                return current_check
            current_check = current_check.parent

    return Path(RECORDINGS_DIR)
