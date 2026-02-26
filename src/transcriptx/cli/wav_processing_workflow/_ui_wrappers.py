"""
Thin wrappers around wav_workflow_ui so tests can patch at this package path.
"""

from pathlib import Path
from typing import Any, Callable, Literal

from rich.console import Console
from rich.progress import Progress

from transcriptx.cli import wav_workflow_ui

_default_console = Console()


def create_audio_progress(
    show_pct: bool = True,
    *,
    progress_cls: type[Progress] = Progress,
    console: Console | None = None,
) -> Progress:
    return wav_workflow_ui.create_audio_progress(
        show_pct,
        progress_cls=progress_cls,
        console=console if console is not None else _default_console,
    )


def collect_audio_file_infos(
    files: list[Path],
    get_duration: Callable[[Path], float | None] | None = None,
) -> list[wav_workflow_ui.AudioFileInfo]:
    return wav_workflow_ui.collect_audio_file_infos(files, get_duration=get_duration)


def print_audio_file_list(
    infos: list[wav_workflow_ui.AudioFileInfo],
    *,
    show_total: bool = False,
    show_total_duration: bool = False,
) -> None:
    wav_workflow_ui.print_audio_file_list(
        infos, show_total=show_total, show_total_duration=show_total_duration
    )


def run_workflow_safely(
    label: str,
    fn: Callable[[], Any],
    *,
    interactive: bool = True,
    cancelled_message: str = "\n[cyan]Cancelled. Returning to menu.[/cyan]",
) -> Any:
    return wav_workflow_ui.run_workflow_safely(
        label, fn, interactive=interactive, cancelled_message=cancelled_message
    )


def post_convert_backup_and_cleanup(
    pairs: list[tuple[Path, Path]],
    *,
    delete_originals_if_already_backed_up: bool,
    kind: Literal["wav", "audio"] = "wav",
) -> tuple[int, int, int]:
    return wav_workflow_ui.post_convert_backup_and_cleanup(
        pairs,
        delete_originals_if_already_backed_up=delete_originals_if_already_backed_up,
        kind=kind,
    )
