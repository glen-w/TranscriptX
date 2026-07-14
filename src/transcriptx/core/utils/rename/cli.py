"""CLI / interactive rename prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.rename.date_prefix import (
    extract_date_prefix,
    extract_date_prefix_from_transcript,
)
from transcriptx.core.utils.rename.names import (
    normalize_base_name,
    validate_target_name,
)
from transcriptx.core.utils.rename.pipeline import rename_managed_transcript
from transcriptx.core.utils.rename.audio_association import find_original_audio_file

logger = get_logger()


def _prefill_enabled() -> bool:
    try:
        from transcriptx.core.utils.config_provider import get_config

        cfg = get_config()
        return bool(
            getattr(
                getattr(cfg, "input", None), "prefill_rename_with_date_prefix", True
            )
        )
    except Exception:
        return True


def prompt_for_rename(transcript_path: str, default_name: str) -> Optional[str]:
    """Interactive prompt for renaming transcript files."""
    import questionary
    from rich.console import Console

    console = Console()
    try:
        old_name = Path(transcript_path).stem
        console.print("\n[bold cyan]Rename Transcript[/bold cyan]")
        console.print(f"[dim]Current name: {old_name}[/dim]")

        prefill = default_name if _prefill_enabled() else ""
        prompt_msg = "Enter new name for transcript (or press Enter to skip):"
        kwargs = {}
        if prefill:
            kwargs["default"] = prefill
        new_name = questionary.text(prompt_msg, **kwargs).ask()

        if not new_name or new_name.strip() == "":
            console.print("[yellow]Rename skipped[/yellow]")
            return None

        valid, error = validate_target_name(old_name, new_name)
        if not valid:
            console.print(f"[red]{error}[/red]")
            return None

        normalized = normalize_base_name(new_name)
        outcome = rename_managed_transcript(transcript_path, normalized)
        if outcome.ok or outcome.transaction_committed:
            console.print(
                f"[green]Renamed to: {normalized}[/green] "
                f"(status={outcome.status.value})"
            )
            if outcome.status.value == "committed_partial":
                console.print(
                    f"[yellow]Partial success; repair id: {outcome.operation_id}[/yellow]"
                )
            return normalized
        console.print(f"[red]Rename failed: {outcome.message}[/red]")
        return None
    except KeyboardInterrupt:
        console.print("\n[yellow]Rename cancelled[/yellow]")
        return None
    except Exception as e:
        log_error("FILE_RENAME", f"Error in rename prompt: {e}", exception=e)
        return None


def rename_transcript_after_speaker_mapping(transcript_path: str) -> None:
    """Prompt for rename after speaker mapping completes."""
    try:
        audio_file = find_original_audio_file(transcript_path)
        date_prefix = ""
        if audio_file and audio_file.exists():
            date_prefix = extract_date_prefix(audio_file)
        if not date_prefix:
            date_prefix = extract_date_prefix_from_transcript(transcript_path)
        default_name = date_prefix if date_prefix else ""
        if not default_name:
            logger.info(
                "No date prefix found for %s; using empty default", transcript_path
            )
        prompt_for_rename(transcript_path, default_name)
    except Exception as e:
        log_error(
            "FILE_RENAME",
            f"Error in rename after speaker mapping: {e}",
            exception=e,
        )
