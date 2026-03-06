"""
Custom audio file selection with playback support using prompt_toolkit.

This module provides a wrapper around the generic file selection interface
for backward compatibility. New code should use file_selection_interface directly.
"""

from pathlib import Path
from typing import List, Optional

from transcriptx.cli.file_selection_interface import (
    FileSelectionConfig,
    select_files_interactive,
    format_audio_file,
)
from transcriptx.cli.file_selection_utils import validate_wav_file
from transcriptx.core.utils.config import get_config


def select_wav_files_with_playback(
    wav_files: List[Path],
    current_path: Path,
) -> Optional[List[Path]]:
    """
    Select WAV files with ability to play them by pressing right arrow.

    This function is a wrapper around the generic file selection interface
    for backward compatibility. New code should use file_selection_interface directly.

    Args:
        wav_files: List of WAV file paths
        current_path: Current directory path

    Returns:
        List of selected file paths, or None if cancelled
    """
    # Use the new generic selection interface
    config = get_config()
    selection_config = FileSelectionConfig(
        multi_select=True,
        enable_playback=True,
        enable_rename=True,
        enable_select_all=True,
        title="🎵 WAV File Selection",
        current_path=current_path,
        metadata_formatter=format_audio_file,
        validator=validate_wav_file,
        skip_seconds_short=config.input.playback_skip_seconds_short,
        skip_seconds_long=config.input.playback_skip_seconds_long,
    )

    result = select_files_interactive(wav_files, selection_config)
    return result  # type: ignore[return-value]
