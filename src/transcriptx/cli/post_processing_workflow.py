"""
Post-processing workflow module for TranscriptX CLI.

Provides interactive access to transcript post-processing tools such as
corrections review and suggestions.
"""

from __future__ import annotations

from pathlib import Path
import os
import shutil
import sys

import questionary
from rich import print
from rich.panel import Panel

from transcriptx.core.corrections.workflow import (  # type: ignore[import-untyped]
    run_corrections_workflow as run_corrections_postprocessing,
    write_corrected_transcript as write_corrected_transcript_file,
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

from .file_selection_utils import (
    select_transcript_file_interactive,
    select_transcript_files_interactive,
)

logger = get_logger()

DELETE_ALL_CONFIRM_PHRASE = "DELETE ALL"


def run_corrections_workflow(interactive: bool = True) -> None:
    with graceful_exit():
        print("\n[bold cyan]✏️ Corrections Workflow[/bold cyan]")
        print(
            "[dim]We’ll suggest fixes; you choose what to apply. The original file stays unchanged unless you later opt in to update it.[/dim]"
        )
        if interactive:
            shortcut_help = "\n".join(
                [
                    "[a] Apply all",
                    "[s] Select occurrences",
                    "[l] Learn as project rule",
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

        transcript_path = None
        if not sys.stdin.isatty():
            print(
                "\n[yellow]⚠️ Non-interactive mode detected. Running suggestions only (no review, no apply, no write-back).[/yellow]"
            )
            interactive = False
            transcript_path = os.environ.get("TRANSCRIPTX_TRANSCRIPT_PATH")
            if transcript_path:
                transcript_path = str(Path(transcript_path).expanduser())
        if transcript_path is None:
            if not sys.stdin.isatty():
                print(
                    "\n[yellow]⚠️ Non-interactive mode requires TRANSCRIPTX_TRANSCRIPT_PATH to be set. Returning.[/yellow]"
                )
                return
            transcript_path = select_transcript_file_interactive()
        if not transcript_path:
            print(
                "\n[yellow]⚠️ No transcript file selected. Returning to menu.[/yellow]"
            )
            return

        config = get_config()
        config.analysis.corrections.enabled = True
        path_obj = Path(transcript_path)
        if not path_obj.exists():
            print(f"\n[red]❌ Transcript file not found: {path_obj}[/red]")
            return

        mode_label = "review" if interactive else "suggestions"
        print(f"\n[dim]Running corrections ({mode_label}) for {path_obj.name}[/dim]")
        try:
            results = run_corrections_postprocessing(
                transcript_path=str(path_obj),
                interactive=interactive,
                apply_changes=interactive,
                update_original_file=False,
                create_backup=True,
                config=config,
            )
            suggestions = results.get("suggestions_count", 0)
            applied = results.get("applied_count", 0)
            decisions_path = results.get("decisions_path")
            patch_log_path = results.get("patch_log_path")
            corrected_path = results.get("corrected_transcript_path")
            suggestions_path = results.get("suggestions_path")

            if suggestions_path:
                print(f"[dim]Suggestions: {suggestions_path}[/dim]")
            if decisions_path:
                print(f"[dim]Decisions: {decisions_path}[/dim]")
            if patch_log_path:
                print(f"[dim]Patch log: {patch_log_path}[/dim]")
            if corrected_path:
                print(f"[dim]Corrected transcript: {corrected_path}[/dim]")

            print(
                f"[green]✅ Corrections complete: {suggestions} suggestion(s), {applied} applied.[/green]"
            )

            if interactive and applied > 0:
                update_original = questionary.confirm(
                    "Update original transcript file with these corrections?",
                    default=False,
                ).ask()
                if update_original:
                    backup_path = write_corrected_transcript_file(
                        transcript_path=str(path_obj),
                        updated_segments=results.get("updated_segments"),
                        create_backup=True,
                    )
                    if backup_path:
                        print(f"[dim]Backup created: {backup_path}[/dim]")
        except Exception as exc:
            logger.warning(f"Corrections workflow failed: {exc}", exc_info=True)
            print(f"[red]Corrections workflow failed: {exc}[/red]")


def _build_post_processing_choices() -> list[str]:
    """Build post-processing menu choices; prune options only if enabled in settings."""
    choices = [
        "✏️ Corrections Review",
        "📝 Corrections Suggestions Only",
    ]
    if get_config().workflow.cli_pruning_enabled:
        choices.extend(
            [
                "🧹 Prune old runs (DB only)",
                "🧹 Prune old runs (DB + outputs)",
                "🗑️ Delete all artefacts",
            ]
        )
    choices.append("⬅️ Back to main menu")
    return choices


def _show_post_processing_menu() -> None:
    """Display and handle post-processing submenu options."""
    while True:
        try:
            choice = questionary.select(
                "Post-processing Options",
                choices=_build_post_processing_choices(),
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
        elif choice == "🗑️ Delete all artefacts":
            _run_delete_all_artefacts()
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
                    print(
                        "\n[yellow]⚠️ None of the selected files exist in the DB. Returning.[/yellow]"
                    )
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
        summary_lines.append("Disk-only runs (not in DB):")
        summary_lines.append(f"  Slugs scanned: {report.disk_only_slugs_scanned}")
        summary_lines.append(f"  Runs found: {report.disk_only_runs_found}")
        summary_lines.append(f"  Runs to delete: {report.disk_only_runs_to_delete}")
        if report.disk_only_plan:
            summary_lines.append("")
            summary_lines.append("  Examples:")
            for slug, delete_runs, keep_run in report.disk_only_plan[:3]:
                summary_lines.append(
                    f"    {slug}: delete {len(delete_runs)} runs, keep {keep_run}"
                )
            if len(report.disk_only_plan) > 3:
                summary_lines.append(
                    f"    ...and {len(report.disk_only_plan) - 3} more slugs"
                )

        print(
            Panel.fit(
                "\n".join(summary_lines),
                title="Dry-run summary",
                border_style="cyan",
            )
        )

        if (
            report.transcripts_with_deletions == 0
            and report.disk_only_runs_to_delete == 0
        ):
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
            summary_lines.append(
                f"Disk-only run directories deleted: {applied.disk_only_runs_deleted}"
            )

        print(
            Panel.fit(
                "\n".join(summary_lines),
                title="[green]✅ Prune complete[/green]",
                border_style="green",
            )
        )


def _run_delete_all_artefacts() -> None:
    """Delete all artefact files and run directories under the outputs root.

    Flow: dry run (show what would be deleted), y/n gate, require typing
    DELETE ALL, then a final y/n before performing deletion.
    """
    with graceful_exit():
        outputs_dir = Path(OUTPUTS_DIR).resolve()
        if not outputs_dir.exists():
            print(
                Panel.fit(
                    f"Outputs directory does not exist: {outputs_dir}\nNothing to delete.",
                    title="🗑️ Delete all artefacts",
                    border_style="yellow",
                )
            )
            return

        # Dry run: collect what would be deleted
        slug_dirs: list[Path] = []
        total_dirs = 0
        for slug_dir in sorted(outputs_dir.iterdir()):
            if not slug_dir.is_dir() or slug_dir.name.startswith("."):
                continue
            slug_dirs.append(slug_dir)
            run_count = sum(
                1
                for p in slug_dir.iterdir()
                if p.is_dir() and not p.name.startswith(".")
            )
            total_dirs += run_count

        summary_lines = [
            f"Outputs root: {outputs_dir}",
            f"Slug directories: {len(slug_dirs)}",
            f"Run directories (total): {total_dirs}",
            "",
            "All run directories under each slug would be removed.",
            "Database rows are NOT deleted; run 'Prune old runs' if you want to clean the DB.",
        ]
        if slug_dirs:
            summary_lines.append("")
            summary_lines.append("Examples (first 5 slugs):")
            for slug_dir in slug_dirs[:5]:
                runs = [
                    p.name
                    for p in slug_dir.iterdir()
                    if p.is_dir() and not p.name.startswith(".")
                ]
                summary_lines.append(f"  {slug_dir.name}: {len(runs)} run(s)")

        print(
            Panel.fit(
                "\n".join(summary_lines),
                title="🗑️ Delete all artefacts (dry run)",
                border_style="yellow",
            )
        )

        if not slug_dirs:
            print("\n[green]✅ No artefact directories to delete.[/green]")
            return

        proceed = questionary.confirm(
            "Proceed with deletion? (y/n)",
            default=False,
        ).ask()
        if not proceed:
            print("\n[dim]No changes made.[/dim]")
            return

        typed = questionary.text(
            f"Type {DELETE_ALL_CONFIRM_PHRASE!r} (exactly) to confirm:",
            default="",
        ).ask()
        if typed is None or (typed or "").strip() != DELETE_ALL_CONFIRM_PHRASE:
            print("\n[red]Confirmation phrase did not match. No changes made.[/red]")
            return

        final_confirm = questionary.confirm(
            "Last chance: permanently delete all artefact directories? (y/n)",
            default=False,
        ).ask()
        if not final_confirm:
            print("\n[dim]No changes made.[/dim]")
            return

        # Perform deletion: remove each slug's run directories (and their contents)
        deleted_slugs = 0
        deleted_runs = 0
        errors: list[str] = []
        for slug_dir in slug_dirs:
            for run_dir in list(slug_dir.iterdir()):
                if not run_dir.is_dir() or run_dir.name.startswith("."):
                    continue
                try:
                    shutil.rmtree(run_dir)
                    deleted_runs += 1
                except Exception as e:
                    errors.append(f"{run_dir}: {e}")
            if not any(run_dir.is_dir() for run_dir in slug_dir.iterdir()):
                deleted_slugs += 1

        result_lines = [
            f"Run directories deleted: {deleted_runs}",
            f"Slug directories now empty: {deleted_slugs}",
        ]
        if errors:
            result_lines.append("")
            result_lines.append(f"Errors ({len(errors)}):")
            result_lines.extend(f"  {e}" for e in errors[:10])
            if len(errors) > 10:
                result_lines.append(f"  ... and {len(errors) - 10} more")

        print(
            Panel.fit(
                "\n".join(result_lines),
                title="[green]✅ Delete all artefacts complete[/green]",
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
