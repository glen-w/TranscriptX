"""
Tag Management Module for TranscriptX.

This module provides interactive tag management functionality, allowing users to:
- View auto-generated tags
- Manually add custom tags
- Remove tags (both auto-generated and manual)
- Edit tags before proceeding with analysis
"""

from typing import Any, Dict, List, Optional
import questionary
from rich.console import Console

from transcriptx.io.tag_validation import (
    build_tag_details,
    sanitize_tag,
    sanitize_tag_list,
    validate_tag,
)

console = Console()


def display_tags(
    current_tags: List[str], auto_tags: List[str], tag_details: Dict[str, Any]
) -> None:
    """
    Display current tags with indicators for auto-generated vs manual tags.

    Args:
        current_tags: List of all current tags (auto + manual)
        auto_tags: List of auto-generated tags
        tag_details: Dictionary with tag details including confidence scores
    """
    if not current_tags:
        console.print("  [dim]No tags assigned[/dim]")
        return

    console.print("\n  [bold]Current Tags:[/bold]")

    for tag in current_tags:
        is_auto = tag in auto_tags
        if is_auto:
            confidence = tag_details.get(tag, {}).get("confidence", 0.0)
            confidence_str = (
                f" (confidence: {confidence:.2f})" if confidence > 0 else ""
            )
            console.print(
                f"    • [cyan]{tag}[/cyan] [dim](auto-generated{confidence_str})[/dim]"
            )
        else:
            console.print(f"    • [green]{tag}[/green] [dim](manual)[/dim]")


def prompt_add_tag() -> Optional[str]:
    """
    Prompt user to add a new tag.

    Returns:
        The new tag string, or None if cancelled or invalid
    """
    tag = questionary.text(
        "Enter a new tag:",
        validate=lambda text: validate_tag(text or "")[0],
    ).ask()

    if tag:
        sanitized = sanitize_tag(tag)
        if sanitized is None:
            console.print("  [red]Invalid tag format[/red]")
            return None
        return sanitized
    return None


def prompt_remove_tag(tags: List[str]) -> List[str]:
    """
    Allow user to select tags to remove.

    Args:
        tags: List of current tags

    Returns:
        List of tags to remove
    """
    if not tags:
        console.print("  [dim]No tags to remove[/dim]")
        return []

    selected = questionary.checkbox("Select tags to remove:", choices=tags).ask()

    return selected if selected else []


def _resolve_initial_tags(
    auto_tags: List[str],
    current_tags: Optional[List[str]],
) -> List[str]:
    """Choose starting tag list: explicit current_tags wins over auto_tags."""
    if current_tags is not None:
        return sanitize_tag_list(current_tags)
    return sanitize_tag_list(auto_tags)


def manage_tags_interactive(
    transcript_path: str,
    auto_tags: List[str],
    tag_details: Dict[str, Any],
    current_tags: Optional[List[str]] = None,
    batch_mode: bool = False,
) -> Dict[str, Any]:
    """
    Interactive interface for viewing, adding, and removing tags.

    Args:
        transcript_path: Path to the transcript file
        auto_tags: List of auto-generated tags
        tag_details: Dictionary with tag details (confidence, indicators, etc.)
        current_tags: Optional list of current tags (None = use auto_tags)
        batch_mode: If True, skip interactive prompts

    Returns:
        Dictionary with:
            - tags: Final list of tags
            - tag_details: Updated tag details with source information
    """
    safe_auto_tags = sanitize_tag_list(auto_tags or [])
    safe_details = dict(tag_details or {})
    working_tags = _resolve_initial_tags(safe_auto_tags, current_tags)

    if batch_mode:
        return {
            "tags": working_tags,
            "tag_details": build_tag_details(
                working_tags, safe_auto_tags, safe_details
            ),
        }

    updated_tag_details = build_tag_details(
        working_tags, safe_auto_tags, safe_details
    )

    while True:
        console.print("\n[bold cyan]🏷️  Tag Management[/bold cyan]")
        console.print(f"  [dim]Transcript: {transcript_path}[/dim]")
        display_tags(working_tags, safe_auto_tags, updated_tag_details)

        choices = [
            "✅ Done - proceed with current tags",
            "➕ Add a new tag",
        ]

        if working_tags:
            choices.append("➖ Remove tags")

        action = questionary.select("What would you like to do?", choices=choices).ask()

        if not action or "done" in action.lower() or "proceed" in action.lower():
            break
        if "add" in action.lower():
            new_tag = prompt_add_tag()
            if new_tag and new_tag not in working_tags:
                working_tags.append(new_tag)
                updated_tag_details[new_tag] = {"source": "manual", "confidence": 1.0}
                console.print(f"  [green]✓ Added tag: {new_tag}[/green]")
            elif new_tag in working_tags:
                console.print(f"  [yellow]Tag '{new_tag}' already exists[/yellow]")
        elif "remove" in action.lower():
            tags_to_remove = prompt_remove_tag(working_tags)
            if tags_to_remove:
                for tag in tags_to_remove:
                    working_tags.remove(tag)
                    updated_tag_details.pop(tag, None)
                console.print(
                    f"  [yellow]Removed {len(tags_to_remove)} tag(s)[/yellow]"
                )

    return {
        "tags": sanitize_tag_list(working_tags),
        "tag_details": build_tag_details(
            working_tags, safe_auto_tags, updated_tag_details
        ),
    }


def offer_and_edit_tags(
    transcript_path: str,
    segments: List[Dict[str, Any]],
    *,
    batch_mode: bool = False,
) -> Dict[str, Any]:
    """Extract (and optionally review) tags, then persist to processing state."""
    from transcriptx.services.transcript_tags import TranscriptTagService

    return TranscriptTagService().extract_and_persist(
        transcript_path, segments, batch_mode=batch_mode
    )
