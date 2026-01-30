"""
Post-processing workflow module for TranscriptX CLI.

Provides interactive access to transcript post-processing tools such as
corrections review and suggestions.
"""

from __future__ import annotations

from pathlib import Path

import questionary
from rich import print
from rich.panel import Panel

from transcriptx.core.corrections.workflow import (  # type: ignore[import-untyped]
    run_corrections_workflow as run_corrections_postprocessing,
)
from transcriptx.core.utils.config import get_config  # type: ignore[import-untyped]
from transcriptx.core.utils.logger import get_logger  # type: ignore[import-untyped]
from transcriptx.database import get_session  # type: ignore[import-untyped]
from transcriptx.database.database import init_database  # type: ignore[import-untyped]
from transcriptx.database.migrations import (  # type: ignore[import-untyped]
    require_up_to_date_schema,
)
from transcriptx.database.maintenance import (  # type: ignore[import-untyped]
    prune_old_pipeline_runs,
)
from transcriptx.database.models import TranscriptFile  # type: ignore[import-untyped]
from transcriptx.utils.error_handling import graceful_exit  # type: ignore[import-untyped]
from transcriptx.core.utils.paths import OUTPUTS_DIR  # type: ignore[import-untyped]

from .file_selection_utils import select_transcript_files_interactive

logger = get_logger()


def run_corrections_workflow(interactive: bool = True) -> None:
    with graceful_exit():
        print("\n[bold cyan]✏️ Corrections Workflow[/bold cyan]")
        if interactive:
            shortcut_help = "\n".join(
                [
                    "[a] Apply all",
                    "[s] Select occurrences",
                    "[c] Apply all + add rule with conditions",
                    "[l] Apply all + add rule (no conditions)",
                    "[r] Reject suggestion",
                    "[k] Skip suggestion",
                ]
            )
            print(
                Panel.fit(
                    shortcut_help,
                    title="Keyboard Shortcuts",
                    border_style="cyan",
                )
            )

        transcript_files = select_transcript_files_interactive()
        if not transcript_files:
            print(
                "\n[yellow]⚠️ No transcript files selected. Returning to menu.[/yellow]"
            )
            return

        config = get_config()
        config.analysis.corrections.enabled = True

        update_original = questionary.confirm(
            "Update original transcript file with applied corrections?",
            default=config.analysis.corrections.update_original_file,
        ).ask()
        create_backup = True
        if update_original:
            create_backup = questionary.confirm(
                "Create a backup before updating the transcript?",
                default=config.analysis.corrections.create_backup,
            ).ask()

        for transcript_path in transcript_files:
            path_obj = Path(transcript_path)
            if not path_obj.exists():
                print(f"\n[red]❌ Transcript file not found: {path_obj}[/red]")
                continue

            mode_label = "review" if interactive else "suggest"
            print(f"\n[dim]Running corrections ({mode_label}) for {path_obj.name}[/dim]")
            try:
                results = run_corrections_postprocessing(
                    transcript_path=str(path_obj),
                    interactive=interactive,
                    update_original_file=bool(update_original),
                    create_backup=bool(create_backup),
                    config=config,
                )
                suggestions = results.get("suggestions_count", 0)
                applied = results.get("applied_count", 0)
                print(
                    f"[green]✅ Corrections complete: {suggestions} suggestion(s), {applied} applied.[/green]"
                )
            except Exception as exc:
                logger.warning(f"Corrections workflow failed: {exc}", exc_info=True)
                print(f"[red]Corrections workflow failed: {exc}[/red]")


def _show_post_processing_menu() -> None:
    """Display and handle post-processing submenu options."""
    while True:
        try:
            choice = questionary.select(
                "Post-processing Options",
                choices=[
                    "✏️ Corrections Review",
                    "📝 Corrections Suggestions Only",
                    "🧹 Prune old runs (DB only)",
                    "🧹 Prune old runs (DB + outputs)",
                    "⬅️ Back to main menu",
                ],
            ).ask()
        except KeyboardInterrupt:
            print("\n[cyan]Returning to main menu...[/cyan]")
            break

        if choice == "✏️ Corrections Review":
            run_corrections_workflow(interactive=True)
        elif choice == "📝 Corrections Suggestions Only":
            run_corrections_workflow(interactive=False)
        elif choice == "🧹 Prune old runs (DB only)":
            _run_prune_old_runs(delete_files=False)
        elif choice == "🧹 Prune old runs (DB + outputs)":
            _run_prune_old_runs(delete_files=True)
        elif choice == "⬅️ Back to main menu":
            break


def _run_prune_old_runs(*, delete_files: bool) -> None:
    with graceful_exit():
        mode_line = (
            "- This will also delete unreferenced artifact files under data/outputs."
            if delete_files
            else "- This does NOT delete any files on disk (DB only)."
        )
        print(
            Panel.fit(
                "\n".join(
                    [
                        "[bold]This removes historical PipelineRun rows from the database.[/bold]",
                        "- Keeps the most recent run per transcript (by created_at).",
                        "- Deleting runs cascades to module runs and artifact index rows.",
                        mode_line,
                        "- Dry-run is shown first; you must explicitly confirm to apply.",
                    ]
                ),
                title="🧹 Prune old DB runs",
                border_style="yellow",
            )
        )

        scope = questionary.select(
            "What do you want to prune?",
            choices=[
                "All transcripts in DB (that have multiple runs)",
                "Only selected transcript files",
                "Cancel",
            ],
        ).ask()
        if scope in (None, "Cancel"):
            return

        transcript_ids: list[int] | None = None
        if scope == "Only selected transcript files":
            selected_paths = select_transcript_files_interactive()
            if not selected_paths:
                print("\n[yellow]⚠️ No transcript files selected. Returning.[/yellow]")
                return

            # Resolve selected transcript file IDs (skip files not imported into DB).
            init_database()
            require_up_to_date_schema()

            session = get_session()
            try:
                transcript_ids = []
                missing: list[str] = []
                for p in selected_paths:
                    tf = (
                        session.query(TranscriptFile)
                        .filter(TranscriptFile.file_path == str(Path(p).resolve()))
                        .first()
                    )
                    if tf:
                        transcript_ids.append(tf.id)
                    else:
                        missing.append(Path(p).name)
                if missing:
                    print(
                        f"\n[yellow]⚠️ {len(missing)} selected file(s) are not in the DB and will be skipped.[/yellow]"
                    )
                if not transcript_ids:
                    print("\n[yellow]⚠️ None of the selected files exist in the DB. Returning.[/yellow]")
                    return
            finally:
                try:
                    session.close()
                except Exception:
                    pass

        # Dry run
        init_database()
        require_up_to_date_schema()

        session = get_session()
        try:
            report = prune_old_pipeline_runs(
                session,
                transcript_file_ids=transcript_ids,
                apply=False,
                delete_files=delete_files,
            )
        finally:
            try:
                session.close()
            except Exception:
                pass

        # Always show dry run summary
        summary_lines = [
            f"Transcripts considered: {report.transcripts_considered}",
            f"Transcripts with deletions: {report.transcripts_with_deletions}",
            f"Pipeline runs to delete: {report.pipeline_runs_to_delete}",
        ]
        if delete_files:
            summary_lines.append(
                f"Artifact file candidates (max): {report.artifact_candidates}"
            )
        else:
            summary_lines.append("Artifact file deletion: OFF")
        
        # Add disk-only run information (always show, even if 0)
        summary_lines.append("")
        summary_lines.append(f"Disk-only runs (not in DB):")
        summary_lines.append(f"  Slugs scanned: {report.disk_only_slugs_scanned}")
        summary_lines.append(f"  Runs found: {report.disk_only_runs_found}")
        summary_lines.append(f"  Runs to delete: {report.disk_only_runs_to_delete}")
        if report.disk_only_plan:
            summary_lines.append("")
            summary_lines.append("  Examples:")
            for slug, delete_runs, keep_run in report.disk_only_plan[:3]:
                summary_lines.append(f"    {slug}: delete {len(delete_runs)} runs, keep {keep_run}")
            if len(report.disk_only_plan) > 3:
                summary_lines.append(f"    ...and {len(report.disk_only_plan) - 3} more slugs")

        print(
            Panel.fit(
                "\n".join(summary_lines),
                title="Dry-run summary",
                border_style="cyan",
            )
        )

        if report.transcripts_with_deletions == 0 and report.disk_only_runs_to_delete == 0:
            print("\n[green]✅ Nothing to prune.[/green]")
            return

        apply = bool(
            questionary.confirm(
                "Apply these deletions now?",
                default=False,
            ).ask()
        )
        if not apply:
            print("\n[dim]No changes applied.[/dim]")
            return

        confirm = questionary.confirm(
            "⚠️ This will permanently delete database rows. Continue?",
            default=False,
        ).ask()
        if not confirm:
            print("\n[dim]No changes applied.[dim]")
            return

        # Apply
        init_database()
        require_up_to_date_schema()
        session = get_session()
        try:
            applied = prune_old_pipeline_runs(
                session,
                transcript_file_ids=transcript_ids,
                apply=True,
                delete_files=delete_files,
            )
        finally:
            try:
                session.close()
            except Exception:
                pass

        summary_lines = [
            f"Pipeline runs deleted: {applied.pipeline_runs_deleted}",
        ]
        if delete_files:
            summary_lines.append(
                f"Files deleted: {applied.files_deleted} (skipped={applied.files_skipped}, missing={applied.files_missing}, unsafe={applied.files_unsafe_outside_outputs})"
            )
        
        # Add disk-only run deletion results
        if applied.disk_only_runs_deleted > 0:
            summary_lines.append("")
            summary_lines.append(f"Disk-only run directories deleted: {applied.disk_only_runs_deleted}")

        print(
            Panel.fit(
                "\n".join(summary_lines),
                title="[green]✅ Prune complete[/green]",
                border_style="green",
            )
        )


def _scan_outputs_with_multiple_runs() -> list[tuple[str, list[str]]]:
    outputs_dir = Path(OUTPUTS_DIR)
    if not outputs_dir.exists():
        return []
    results: list[tuple[str, list[str]]] = []
    for slug_dir in outputs_dir.iterdir():
        if not slug_dir.is_dir():
            continue
        run_dirs = [p.name for p in slug_dir.iterdir() if p.is_dir()]
        if len(run_dirs) > 1:
            run_dirs.sort()
            results.append((slug_dir.name, run_dirs))
    results.sort(key=lambda item: item[0])
    return results
