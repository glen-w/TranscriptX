"""
Interactive analysis target picker (files vs group) and hydration helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Literal, Optional

import questionary
from rich import print
from transcriptx.core.pipeline.target_resolver import (
    GroupRef,
    resolve_group_member_ids,
    resolve_transcript_paths,
)
from transcriptx.core.services.group_service import GroupService
from transcriptx.cli.file_selection_utils import select_transcript_files_interactive


@dataclass(frozen=True)
class TargetSelection:
    kind: Literal["paths", "group"]
    paths: Optional[list[Path]] = None
    group_ref: Optional[GroupRef] = None
    member_transcript_ids: Optional[list[int]] = None
    member_paths: Optional[list[Path]] = None

    def get_member_paths(
        self, resolver: Optional[Callable[[Iterable[int]], list[Path]]] = None
    ) -> list[Path]:
        """
        Resolve member paths from frozen IDs. Cached paths are best-effort only.
        """
        if self.kind != "group":
            return []
        if self.member_transcript_ids is None:
            return []
        if resolver is None:
            resolver = resolve_transcript_paths
        return resolver(self.member_transcript_ids)


def hydrate_group_selection(group_ref: GroupRef) -> TargetSelection:
    """
    Hydrate a GroupRef into a TargetSelection with frozen member IDs.
    """
    member_ids = resolve_group_member_ids(group_ref)
    member_paths = resolve_transcript_paths(member_ids)
    return TargetSelection(
        kind="group",
        group_ref=group_ref,
        member_transcript_ids=member_ids,
        member_paths=member_paths,
    )


def _format_group_label(group) -> str:
    name = group.name or "Unnamed"
    count = len(group.transcript_file_uuids or [])
    return f"📁 {name} ({count} transcripts)"


def select_analysis_target_interactive() -> TargetSelection | None:
    """
    Two-step picker: choose Files vs Group, then select target.
    """
    choice = questionary.select(
        "What do you want to analyze?",
        choices=["Files", "Group", "Cancel"],
    ).ask()
    if choice in (None, "Cancel"):
        return None

    if choice == "Files":
        selected = select_transcript_files_interactive()
        if not selected:
            return None
        return TargetSelection(kind="paths", paths=selected)

    groups = GroupService.list_groups()
    if not groups:
        print("\n[yellow]No groups found.[/yellow]")
        return None
    labels = [_format_group_label(group) for group in groups]
    labels.append("Cancel")
    selected_label = questionary.select("Select a group:", choices=labels).ask()
    if selected_label in (None, "Cancel"):
        return None
    index = labels.index(selected_label)
    group = groups[index]
    group_ref = GroupRef(group_uuid=group.uuid)
    return hydrate_group_selection(group_ref)
