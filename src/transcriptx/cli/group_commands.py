"""
Group analysis CLI commands.
"""

from __future__ import annotations

from typing import List, Optional

import typer
from rich import print

from transcriptx.core.pipeline.module_registry import get_default_modules
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.target_resolver import GroupRef
from transcriptx.core.services.group_service import GroupService

app = typer.Typer(help="Group analysis commands")


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@app.command("create")
def create_group(
    name: Optional[str] = typer.Option(None, "--name", help="Group name"),
    group_type: str = typer.Option(
        "merged_event",
        "--type",
        help="Group type: merged_event|baseline|comparison|other",
    ),
    transcripts: str = typer.Option(
        ...,
        "--transcripts",
        help="Comma-separated transcript paths or transcript_file UUIDs",
    ),
    description: Optional[str] = typer.Option(None, "--description"),
) -> None:
    """Create a group (or return existing by deterministic key)."""
    transcript_refs = _split_csv(transcripts)
    GroupService.validate_transcripts_exist(transcript_refs)
    group = GroupService.create_or_get_group(
        name=name,
        group_type=group_type,
        transcript_refs=transcript_refs,
        description=description,
    )
    print(
        f"[green]Group:[/green] {group.uuid} | key={group.key} | "
        f"{len(group.transcript_file_uuids)} transcripts"
    )


@app.command("list")
def list_groups(
    group_type: Optional[str] = typer.Option(None, "--type", help="Filter by type")
) -> None:
    """List persisted groups."""
    groups = GroupService.list_groups(group_type=group_type)
    if not groups:
        print("[yellow]No groups found.[/yellow]")
        return

    print("[bold]Groups[/bold]")
    for group in groups:
        name = group.name or "(unnamed)"
        count = len(group.transcript_file_uuids or [])
        updated = group.updated_at.isoformat() if group.updated_at else "unknown"
        key_prefix = group.key[:12]
        print(f"- {group.uuid} | {name} | {group.type} | {count} | {key_prefix} | {updated}")


@app.command("show")
def show_group(
    identifier: str = typer.Option(..., "--identifier", "-i", help="UUID, key, or name")
) -> None:
    """Show details for a group."""
    group = GroupService.resolve_group_identifier(identifier)
    members = GroupService.get_members(group.id) if group.id is not None else []

    print(f"[bold]Group:[/bold] {group.uuid}")
    if group.name:
        print(f"Name: {group.name}")
    print(f"Type: {group.type}")
    print(f"Key: {group.key}")
    print(f"Transcript count: {len(group.transcript_file_uuids or [])}")
    if members:
        print("Transcript files:")
        for member in members:
            print(f"- {member.file_path}")


@app.command("run")
def run_group(
    identifier: str = typer.Option(..., "--identifier", "-i", help="UUID, key, or name"),
    modules: str = typer.Option(
        "all", "--modules", help="Comma-separated list of modules or 'all'"
    ),
    persist: bool = typer.Option(
        False, "--persist", help="Persist run metadata and artifacts to DB"
    ),
) -> None:
    """Run analysis for a persisted group."""
    group = GroupService.resolve_group_identifier(identifier)
    members = GroupService.get_members(group.id) if group.id is not None else []
    transcript_paths = [m.file_path for m in members if m.file_path]

    if modules.lower() == "all":
        selected_modules = get_default_modules(transcript_paths)
    else:
        selected_modules = [m.strip() for m in modules.split(",") if m.strip()]

    run_analysis_pipeline(
        target=GroupRef(group_uuid=group.uuid),
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
    """Delete a group."""
    group = GroupService.resolve_group_identifier(identifier)
    if not force:
        confirm = typer.confirm(f"Delete group {group.uuid}? This is permanent.")
        if not confirm:
            print("[yellow]Delete cancelled.[/yellow]")
            return

    deleted = GroupService.delete_group(group.uuid)
    if deleted:
        print("[green]Group deleted.[/green]")
    else:
        print("[yellow]Group not found.[/yellow]")
