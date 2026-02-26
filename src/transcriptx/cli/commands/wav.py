"""
WAV/audio process-wav command implementations.

Convert, merge, and compress. Typer decorators and option parsing
live in main.py; these functions take parsed arguments and call
the workflow entry points.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional


def do_wav_convert(
    file_paths: List[Path],
    output_dir: Optional[Path] = None,
    move_wavs: bool = False,
    auto_rename: bool = True,
    skip_confirm: bool = False,
) -> Dict[str, Any]:
    """
    Convert audio files to MP3. Called from process-wav convert command.
    Returns result dict from run_wav_convert_non_interactive.
    """
    from transcriptx.cli.wav_processing_workflow import run_wav_convert_non_interactive

    result: Dict[str, Any] = run_wav_convert_non_interactive(
        files=file_paths,
        output_dir=output_dir,
        move_wavs=move_wavs,
        auto_rename=auto_rename,
        skip_confirm=skip_confirm,
    )
    return result


def do_wav_merge(
    file_paths: List[Path],
    output_file: Optional[str] = None,
    output_dir: Optional[Path] = None,
    backup_wavs: bool = True,
    overwrite: bool = False,
    skip_confirm: bool = False,
) -> Dict[str, Any]:
    """
    Merge multiple audio files into one MP3. Called from process-wav merge command.
    Returns result dict from run_wav_merge_non_interactive.
    """
    from transcriptx.cli.wav_processing_workflow import run_wav_merge_non_interactive

    result: Dict[str, Any] = run_wav_merge_non_interactive(
        files=file_paths,
        output_file=output_file,
        output_dir=output_dir,
        backup_wavs=backup_wavs,
        overwrite=overwrite,
        skip_confirm=skip_confirm,
    )
    return result


def do_wav_compress(
    delete_originals: bool = False,
    storage_dir: Optional[Path] = None,
    skip_confirm: bool = False,
) -> Dict[str, Any]:
    """
    Compress WAV files in backups directory. Called from process-wav compress command.
    Returns result dict from run_wav_compress_non_interactive.
    """
    from transcriptx.cli.wav_processing_workflow import (
        run_wav_compress_non_interactive,
    )

    result: Dict[str, Any] = run_wav_compress_non_interactive(
        delete_originals=delete_originals,
        storage_dir=storage_dir,
        skip_confirm=skip_confirm,
    )
    return result
