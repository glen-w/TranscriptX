"""
WAV Processing Workflow package for TranscriptX CLI.

Provides workflows for processing WAV files: convert to MP3, merge, preprocess,
and compress backups. Re-exports public API and internal symbols so existing
imports and test patches continue to work.
"""

import sys
from pathlib import Path
from typing import Any, Callable, Literal

from rich.console import Console
from rich.progress import Progress

from . import _ui_wrappers as _ui

# Re-exports for test patches: must be before submodule imports so submodules can "from . import questionary" etc.
import questionary
from rich import print as print_rich

from transcriptx.cli.audio import (
    backup_audio_files_to_storage,
    check_ffmpeg_available,
    convert_audio_to_mp3,
    get_audio_duration,
    merge_audio_files,
)
from transcriptx.cli.file_selection_utils import (
    get_wav_folder_start_path,
    reorder_files_interactive,
    select_audio_files_interactive,
)
from transcriptx.core.utils.file_rename import rename_mp3_after_conversion

print = print_rich  # so patch('...print') works

# Wrappers defined so submodules can "from . import create_audio_progress" (patch-stable)


def create_audio_progress(
    show_pct: bool = True,
    *,
    progress_cls: type[Progress] | None = None,
    console: Console | None = None,
) -> Progress:
    if progress_cls is None:
        pkg = sys.modules[__name__]
        progress_cls = pkg.Progress
    return _ui.create_audio_progress(
        show_pct, progress_cls=progress_cls, console=console
    )


def collect_audio_file_infos(
    files: list[Path],
    get_duration: Callable[[Path], float | None] | None = None,
) -> list[Any]:
    if get_duration is None:
        pkg = sys.modules[__name__]
        get_duration = pkg.get_audio_duration
    return _ui.collect_audio_file_infos(files, get_duration=get_duration)


def print_audio_file_list(
    infos: list[Any],
    *,
    show_total: bool = False,
    show_total_duration: bool = False,
) -> None:
    _ui.print_audio_file_list(
        infos, show_total=show_total, show_total_duration=show_total_duration
    )


def run_workflow_safely(
    label: str,
    fn: Callable[[], Any],
    *,
    interactive: bool = True,
    cancelled_message: str = "\n[cyan]Cancelled. Returning to menu.[/cyan]",
) -> Any:
    return _ui.run_workflow_safely(
        label, fn, interactive=interactive, cancelled_message=cancelled_message
    )


def post_convert_backup_and_cleanup(
    pairs: list[tuple[Path, Path]],
    *,
    delete_originals_if_already_backed_up: bool,
    kind: Literal["wav", "audio"] = "wav",
) -> tuple[int, int, int]:
    return _ui.post_convert_backup_and_cleanup(
        pairs,
        delete_originals_if_already_backed_up=delete_originals_if_already_backed_up,
        kind=kind,
    )


from .compress import _run_compress_workflow, run_wav_compress_non_interactive
from .convert import _run_convert_workflow, run_wav_convert_non_interactive
from .menu import _run_wav_processing_workflow_impl, run_wav_processing_workflow
from .merge import _run_merge_workflow, run_wav_merge_non_interactive
from .preprocess import _run_preprocessing_workflow, run_preprocess_single_file

__all__ = [
    "Progress",
    "create_audio_progress",
    "collect_audio_file_infos",
    "print_audio_file_list",
    "run_workflow_safely",
    "post_convert_backup_and_cleanup",
    "run_wav_processing_workflow",
    "_run_wav_processing_workflow_impl",
    "run_preprocess_single_file",
    "_run_preprocessing_workflow",
    "_run_convert_workflow",
    "run_wav_convert_non_interactive",
    "_run_merge_workflow",
    "run_wav_merge_non_interactive",
    "_run_compress_workflow",
    "run_wav_compress_non_interactive",
]
