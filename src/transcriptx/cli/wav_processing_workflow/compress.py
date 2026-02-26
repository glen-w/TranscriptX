"""Compress WAV backups workflow (interactive and non-interactive)."""

import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from rich import print

from . import questionary

from transcriptx.cli.audio import compress_wav_backups
from transcriptx.core.utils.paths import WAV_STORAGE_DIR
from transcriptx.core.utils.performance_estimator import (
    PerformanceEstimator,
    format_time_estimate,
)

from . import create_audio_progress, run_workflow_safely


def _run_compress_workflow() -> None:
    """Run the compress WAV backups workflow."""

    def _body() -> None:
        print("\n[bold cyan]🗜️ Compress WAV Backups[/bold cyan]")
        print("[dim]Compress WAV files in data/backups/wav into zip archives[/dim]")

        wav_storage_dir = Path(WAV_STORAGE_DIR)
        if not wav_storage_dir.exists():
            print(
                f"\n[yellow]⚠️ WAV storage directory does not exist: {wav_storage_dir}[/yellow]"
            )
            print("[cyan]No WAV files to compress. Returning to menu.[/cyan]")
            return

        wav_files = [
            f
            for f in wav_storage_dir.iterdir()
            if f.is_file() and f.suffix.lower() == ".wav"
        ]

        if not wav_files:
            print(f"\n[yellow]⚠️ No WAV files found in {wav_storage_dir}[/yellow]")
            print("[cyan]Returning to menu.[/cyan]")
            return

        total_size = sum(f.stat().st_size for f in wav_files)
        total_size_mb = total_size / (1024 * 1024)

        print(f"\n[bold]Found {len(wav_files)} WAV file(s) to compress[/bold]")
        print(f"[dim]Total size: {total_size_mb:.1f} MB[/dim]")
        print(f"[dim]Location: {wav_storage_dir}[/dim]")

        estimated_compressed_mb = total_size_mb * 0.15
        estimated_savings_mb = total_size_mb - estimated_compressed_mb
        print(
            f"[dim]Estimated compressed size: ~{estimated_compressed_mb:.1f} MB[/dim]"
        )
        print(f"[dim]Estimated space savings: ~{estimated_savings_mb:.1f} MB[/dim]")

        try:
            estimator = PerformanceEstimator()
            estimate = estimator.estimate_compression_time(
                total_size_mb=total_size_mb, file_count=len(wav_files)
            )
            if estimate.get("estimated_seconds") is not None:
                estimate_str = format_time_estimate(estimate)
                print(f"[dim]Estimated time: {estimate_str}[/dim]")
        except Exception:
            pass

        if not questionary.confirm(f"\nCompress {len(wav_files)} WAV file(s)?").ask():
            print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
            return

        delete_originals = questionary.confirm(
            "Delete original WAV files after successful compression?", default=False
        ).ask()

        if delete_originals:
            print(
                "[yellow]⚠️ Original WAV files will be deleted after compression[/yellow]"
            )

        print("\n[bold]Compressing files...[/bold]")

        start_time = time.time()

        with create_audio_progress(show_pct=True) as progress:
            task = progress.add_task(
                "[cyan]Compressing WAV files...", total=len(wav_files)
            )

            def progress_callback(current: int, total: int, message: str):
                progress.update(task, advance=1, description=f"[cyan]{message}[/cyan]")

            try:
                zip_paths, files_compressed, zip_count = compress_wav_backups(
                    delete_originals=delete_originals,
                    progress_callback=progress_callback,
                )

                progress.update(
                    task,
                    completed=len(wav_files),
                    description="[green]✅ Compression completed![/green]",
                )

            except Exception as e:
                progress.update(
                    task, description=f"[red]❌ Compression failed: {e}[/red]"
                )
                raise

        elapsed_time = time.time() - start_time

        print("\n[bold green]✅ Compression Complete![/bold green]")
        print(
            f"[green]Successfully compressed {files_compressed} file(s) into {zip_count} zip file(s)[/green]"
        )
        print(f"[dim]Time taken: {timedelta(seconds=int(elapsed_time))}[/dim]")

        if zip_paths:
            print("\n[bold]Created zip files:[/bold]")
            for zip_path in zip_paths:
                zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
                print(f"  ✅ {zip_path.name} ({zip_size_mb:.1f} MB)")

        if delete_originals:
            print("\n[green]✅ Original WAV files have been deleted[/green]")
        else:
            print("\n[cyan]Original WAV files have been preserved[/cyan]")

    if (
        run_workflow_safely(
            "WAV_COMPRESS",
            _body,
            interactive=True,
            cancelled_message="\n[cyan]Compression cancelled. Returning to menu.[/cyan]",
        )
        is not None
    ):
        return


def run_wav_compress_non_interactive(
    delete_originals: bool = False,
    storage_dir: Path | str | None = None,
    skip_confirm: bool = False,
) -> dict[str, Any]:
    """
    Compress WAV files in backups directory into zip archives non-interactively.

    Args:
        delete_originals: Delete original WAV files after successful compression (default: False)
        storage_dir: Custom WAV storage directory path (default: data/backups/wav)
        skip_confirm: Skip confirmation prompts (default: False)

    Returns:
        Dictionary containing compression results
    """
    if storage_dir is None:
        wav_storage_dir = Path(WAV_STORAGE_DIR)
    elif isinstance(storage_dir, str):
        wav_storage_dir = Path(storage_dir)
    else:
        wav_storage_dir = storage_dir

    if not wav_storage_dir.exists():
        raise FileNotFoundError(
            f"WAV storage directory does not exist: {wav_storage_dir}"
        )

    wav_files = [
        f
        for f in wav_storage_dir.iterdir()
        if f.is_file() and f.suffix.lower() == ".wav"
    ]

    if not wav_files:
        print(f"\n[yellow]⚠️ No WAV files found in {wav_storage_dir}[/yellow]")
        return {
            "status": "completed",
            "files_compressed": 0,
            "zip_count": 0,
            "zip_files": [],
        }

    total_size = sum(f.stat().st_size for f in wav_files)
    total_size_mb = total_size / (1024 * 1024)

    print(f"\n[bold]Found {len(wav_files)} WAV file(s) to compress[/bold]")
    print(f"[dim]Total size: {total_size_mb:.1f} MB[/dim]")
    print(f"[dim]Location: {wav_storage_dir}[/dim]")

    estimated_compressed_mb = total_size_mb * 0.15
    estimated_savings_mb = total_size_mb - estimated_compressed_mb
    print(f"[dim]Estimated compressed size: ~{estimated_compressed_mb:.1f} MB[/dim]")
    print(f"[dim]Estimated space savings: ~{estimated_savings_mb:.1f} MB[/dim]")

    if not skip_confirm:
        from rich.prompt import Confirm

        if not Confirm.ask(f"Compress {len(wav_files)} WAV file(s)?"):
            return {"status": "cancelled"}

        if delete_originals:
            if not Confirm.ask(
                "Delete original WAV files after successful compression?"
            ):
                delete_originals = False

    print("\n[bold]Compressing files...[/bold]")
    start_time = time.time()

    with create_audio_progress(show_pct=True) as progress:
        task = progress.add_task("[cyan]Compressing WAV files...", total=len(wav_files))

        def progress_callback(current: int, total: int, message: str):
            progress.update(task, advance=1, description=f"[cyan]{message}[/cyan]")

        try:
            zip_paths, files_compressed, zip_count = compress_wav_backups(
                delete_originals=delete_originals, progress_callback=progress_callback
            )
            progress.update(
                task,
                completed=len(wav_files),
                description="[green]✅ Compression completed![/green]",
            )
        except Exception as e:
            progress.update(task, description=f"[red]❌ Compression failed: {e}[/red]")
            raise

    elapsed_time = time.time() - start_time

    print("\n[bold green]✅ Compression Complete![/bold green]")
    print(
        f"[green]Successfully compressed {files_compressed} file(s) into {zip_count} zip file(s)[/green]"
    )
    print(f"[dim]Time taken: {timedelta(seconds=int(elapsed_time))}[/dim]")

    if zip_paths:
        print("\n[bold]Created zip files:[/bold]")
        for zip_path in zip_paths:
            zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
            print(f"  ✅ {zip_path.name} ({zip_size_mb:.1f} MB)")

    return {
        "status": "completed",
        "files_compressed": files_compressed,
        "zip_count": zip_count,
        "zip_files": [str(z) for z in zip_paths],
        "deleted_originals": delete_originals,
    }
