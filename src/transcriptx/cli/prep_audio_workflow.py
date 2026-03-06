"""
Batch audio preparation: discover audio in folder, convert to MP3 per file.

No transcription. Uses prep_audio.prep_single_audio and optional checkpoint/resume.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from rich import print

from transcriptx.cli.audio import check_ffmpeg_available
from transcriptx.cli.file_discovery import discover_audio_files
from transcriptx.cli.prep_audio import prep_single_audio
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def run_prep_audio_workflow(
    folder: Path,
    output_dir: Optional[Path] = None,
    extensions: tuple[str, ...] = (".wav", ".mp3", ".ogg", ".m4a", ".flac", ".aac"),
) -> Dict[str, Any]:
    """
    Discover audio files in folder and convert each to MP3.

    Args:
        folder: Path to folder containing audio files
        output_dir: Optional output directory; default is same as each file's parent
        extensions: Audio extensions to discover

    Returns:
        Dict with status, processed_count, failed_count, failed_files
    """
    if not folder.exists() or not folder.is_dir():
        return {
            "status": "failed",
            "error": f"Folder not found or not a directory: {folder}",
        }
    if not check_ffmpeg_available():
        return {"status": "failed", "error": "ffmpeg is not available"}
    files = discover_audio_files(folder, extensions)
    if not files:
        print(f"[yellow]No audio files found in {folder}[/yellow]")
        return {
            "status": "completed",
            "processed_count": 0,
            "failed_count": 0,
            "failed_files": [],
        }
    out = output_dir or folder
    processed = 0
    failed_files: List[str] = []
    for audio_path in files:
        result_path = prep_single_audio(audio_path, out)
        if result_path is not None:
            processed += 1
        else:
            failed_files.append(str(audio_path))
    print(f"[green]Converted {processed}/{len(files)} file(s)[/green]")
    if failed_files:
        print(f"[yellow]Failed: {len(failed_files)} file(s)[/yellow]")
    return {
        "status": "completed",
        "processed_count": processed,
        "failed_count": len(failed_files),
        "failed_files": failed_files,
    }


def run_prep_audio_non_interactive(
    folder: Path,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """CLI entry point for prep-audio command."""
    return run_prep_audio_workflow(folder, output_dir=output_dir)
