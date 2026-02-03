"""
Group analysis CLI commands.
"""

from __future__ import annotations

from typing import Optional

import typer
from rich import print

from transcriptx.core.pipeline.pipeline import run_analysis_pipeline  # type: ignore[import]
from transcriptx.core.pipeline.module_registry import get_default_modules  # type: ignore[import]
from transcriptx.core.utils.group_resolver import (  # type: ignore[import]
    resolve_group,
    to_domain_transcript_set,
)
from transcriptx.database import get_session  # type: ignore[import]
from transcriptx.database.repositories.transcript_set import (  # type: ignore[import]
    TranscriptSetRepository,
)


app = typer.Typer(help="Group analysis commands")


@app.command("list")
def list_groups() -> None:
    """List persisted TranscriptSets."""
    session = get_session()
    try:
        repo = TranscriptSetRepository(session)
        groups = repo.list_sets()
    finally:
        session.close()

    if not groups:
        print("[yellow]No TranscriptSets found.[/yellow]")
        return

    print("[bold]TranscriptSets[/bold]")
    for group in groups:
        name = group.name or "(unnamed)"
        count = len(group.transcript_ids or [])
        created = group.created_at.isoformat() if group.created_at else "unknown"
        print(f"- {group.uuid} | {name} | {count} transcripts | {created}")


@app.command("show")
def show_group(identifier: str = typer.Option(..., "--identifier", "-i", help="UUID, key, or name")) -> None:
    """Show details for a TranscriptSet."""
    group = resolve_group(identifier)

    session = get_session()
    try:
        repo = TranscriptSetRepository(session)
        members = repo.resolve_members(group)
    finally:
        session.close()

    print(f"[bold]Group:[/bold] {group.uuid}")
    if group.name:
        print(f"Name: {group.name}")
    print(f"Transcript IDs: {len(group.transcript_ids or [])}")
    if members:
        print("Transcript files:")
        for member in members:
            print(f"- {member.file_path}")
    else:
        for transcript_id in group.transcript_ids or []:
            print(f"- {transcript_id}")


@app.command("analyze")
def analyze_group(
    identifier: str = typer.Option(..., "--identifier", "-i", help="UUID, key, or name"),
    modules: str = typer.Option(
        "all", "--modules", help="Comma-separated list of modules or 'all'"
    ),
    persist: bool = typer.Option(
        False, "--persist", help="Persist run metadata and artifacts to DB"
    ),
) -> None:
    """Run analysis for a persisted TranscriptSet."""
    group = resolve_group(identifier)
    transcript_set = to_domain_transcript_set(group)
    transcript_paths: list[str] = []
    session = get_session()
    try:
        repo = TranscriptSetRepository(session)
        members = repo.resolve_members(group)
        transcript_paths = [m.file_path for m in members if m.file_path]
    finally:
        session.close()

    if modules.lower() == "all":
        selected_modules = get_default_modules(transcript_paths)
    else:
        selected_modules = [m.strip() for m in modules.split(",") if m.strip()]

    run_analysis_pipeline(
        target=transcript_set,
        selected_modules=selected_modules,
        persist=persist,
    )


@app.command("delete")
def delete_group(
    identifier: str = typer.Option(..., "--identifier", "-i", help="UUID, key, or name"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Delete without confirmation"
    ),
) -> None:
    """Delete a persisted TranscriptSet."""
    group = resolve_group(identifier)
    group_uuid = group.uuid
    if not force:
        confirm = typer.confirm(
            f"Delete TranscriptSet {group_uuid}? This is permanent."
        )
        if not confirm:
            print("[yellow]Delete cancelled.[/yellow]")
            return

    session = get_session()
    try:
        repo = TranscriptSetRepository(session)
        refreshed = repo.get_by_uuid(group_uuid)
        if refreshed is None:
            print("[yellow]TranscriptSet not found.[/yellow]")
            return
        repo.delete_transcript_set(refreshed)
    finally:
        session.close()

    print("[green]TranscriptSet deleted.[/green]")
