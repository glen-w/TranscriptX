"""
Single-file audio preparation: convert, compress, normalize.

No transcript paths or Docker references. Used by prep-audio CLI and prep_audio_workflow.
"""

from pathlib import Path
from typing import Optional

from transcriptx.cli.audio import convert_audio_to_mp3, check_ffmpeg_available
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def prep_single_audio(
    audio_path: Path,
    output_dir: Optional[Path] = None,
) -> Optional[Path]:
    """
    Convert a single audio file to MP3.

    Args:
        audio_path: Path to input audio (WAV, MP3, OGG, etc.)
        output_dir: Optional output directory; default is same as input.

    Returns:
        Path to output MP3 file, or None if conversion failed/skipped.
    """
    if not audio_path.exists():
        logger.warning("Audio file not found: %s", audio_path)
        return None
    if not check_ffmpeg_available():
        logger.warning("ffmpeg not available; skipping conversion")
        return None
    out_dir = output_dir or audio_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        output_path = convert_audio_to_mp3(audio_path, out_dir)
        return Path(output_path) if output_path else None
    except Exception as e:
        logger.exception("Conversion failed for %s: %s", audio_path, e)
        return None
