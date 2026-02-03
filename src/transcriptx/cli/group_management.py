"""
Interactive group management menu.
"""

from __future__ import annotations

from typing import List, Optional

import questionary
from rich import print
from rich.table import Table

from transcriptx.core.pipeline.module_registry import get_default_modules
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.target_resolver import GroupRef
from transcriptx.core.services.group_service import GroupService
from transcriptx.database import init_database
from transcriptx.cli.file_selection_utils import select_transcript_files_interactive


def _format_group_label(group) -> str:
    name = group.name or "Unnamed"
    count = len(group.transcript_file_uuids or [])
    return f"{name} | {group.uuid} | {count} transcripts"


def _choose_group_identifier(prompt: str) -> Optional[str]:
    groups = GroupService.list_groups()
    if not groups:
        print("\n[yellow]No groups found.[/yellow]")
        return None
    choices = [_format_group_label(group) for group in groups]
    choices.append("🔎 Enter identifier manually")
    choices.append("⬅️ Back")
    selection = questionary.select(prompt, choices=choices).ask()
    if selection in (None, "⬅️ Back"):
        return None
    if selection == "🔎 Enter identifier manually":
        entered = questionary.text("Enter group UUID, key, or name:").ask()
        return entered.strip() if entered else None
    index = choices.index(selection)
    return groups[index].uuid


def _list_groups() -> None:
    groups = GroupService.list_groups()
    if not groups:
        print("\n[yellow]No groups found.[/yellow]")
        return
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("UUID", style="cyan", overflow="fold")
    table.add_column("Name", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Count", style="blue")
    table.add_column("Key Prefix", style="dim")
    for group in groups:
        name = group.name or "(unnamed)"
        count = str(len(group.transcript_file_uuids or []))
        table.add_row(
            group.uuid,
            name,
            group.type,
            count,
            group.key[:12],
        )
    print(table)


def _create_group() -> None:
    selected = select_transcript_files_interactive()
    if not selected:
        print("\n[yellow]No transcripts selected.[/yellow]")
        return
    transcript_refs = [str(path) for path in selected]
    name = questionary.text("Group name (optional):").ask() or None
    group_type = questionary.select(
        "Group type:",
        choices=["merged_event", "baseline", "comparison", "other"],
    ).ask()
    description = questionary.text("Description (optional):").ask() or None
    try:
        group = GroupService.create_or_get_group(
            name=name,
            group_type=group_type,
            transcript_refs=transcript_refs,
            description=description,
        )
    except ValueError as exc:
        print(f"[red]Failed to create group:[/red] {exc}")
        return
    print(
        f"[green]Group:[/green] {group.uuid} | key={group.key} | "
        f"{len(group.transcript_file_uuids)} transcripts"
    )


def _show_group_details() -> None:
    identifier = _choose_group_identifier("Select a group to view:")
    if not identifier:
        return
    group = GroupService.resolve_group_identifier(identifier)
    members = GroupService.get_members(group.id) if group.id is not None else []
    print(f"\n[bold]Group:[/bold] {group.uuid}")
    if group.name:
        print(f"Name: {group.name}")
    print(f"Type: {group.type}")
    print(f"Key: {group.key}")
    print(f"Transcript count: {len(group.transcript_file_uuids or [])}")
    if members:
        print("Transcript files:")
        for member in members:
            print(f"- {member.file_path}")


def _run_group() -> None:
    identifier = _choose_group_identifier("Select a group to run analysis:")
    if not identifier:
        return
    group = GroupService.resolve_group_identifier(identifier)
    members = GroupService.get_members(group.id) if group.id is not None else []
    transcript_paths = [m.file_path for m in members if m.file_path]
    modules_choice = questionary.select(
        "Modules:",
        choices=["all", "custom"],
    ).ask()
    if modules_choice == "custom":
        modules_input = questionary.text(
            "Comma-separated module names:"
        ).ask() or ""
        selected_modules = [m.strip() for m in modules_input.split(",") if m.strip()]
    else:
        selected_modules = get_default_modules(transcript_paths)
    persist = questionary.confirm("Persist run metadata to DB?").ask()
    run_analysis_pipeline(
        target=GroupRef(group_uuid=group.uuid),
        selected_modules=selected_modules,
        persist=bool(persist),
    )


def _delete_group() -> None:
    identifier = _choose_group_identifier("Select a group to delete:")
    if not identifier:
        return
    group = GroupService.resolve_group_identifier(identifier)
    confirm = questionary.confirm(
        f"Delete group {group.uuid}? This is permanent."
    ).ask()
    if not confirm:
        print("\n[cyan]Delete cancelled.[/cyan]")
        return
    deleted = GroupService.delete_group(group.uuid)
    if deleted:
        print("[green]Group deleted.[/green]")
    else:
        print("[yellow]Group not found.[/yellow]")


def _show_group_management_menu() -> None:
    """Display and handle group management menu."""
    init_database()
    while True:
        try:
            choice = questionary.select(
                "Group Management",
                choices=[
                    "📋 List Groups",
                    "➕ Create Group",
                    "🔍 Show Group",
                    "▶️ Run Group Analysis",
                    "🗑️ Delete Group",
                    "⬅️ Back to main menu",
                ],
            ).ask()
        except KeyboardInterrupt:
            print("\n[cyan]Returning to main menu...[/cyan]")
            break

        if choice == "📋 List Groups":
            _list_groups()
        elif choice == "➕ Create Group":
            _create_group()
        elif choice == "🔍 Show Group":
            _show_group_details()
        elif choice == "▶️ Run Group Analysis":
            _run_group()
        elif choice == "🗑️ Delete Group":
            _delete_group()
        elif choice == "⬅️ Back to main menu":
            break
