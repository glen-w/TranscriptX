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
        The new tag string, or None if cancelled
    """
    tag = questionary.text(
        "Enter a new tag:",
        validate=lambda text: len(text.strip()) > 0 if text else False,
    ).ask()

    if tag:
        return tag.strip().lower()
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

    # Create choices with indicators
    choices = []
    for tag in tags:
        choices.append(tag)

    selected = questionary.checkbox("Select tags to remove:", choices=choices).ask()

    return selected if selected else []


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
        current_tags: Optional list of current tags (to preserve manual tags)
        batch_mode: If True, skip interactive prompts

    Returns:
        Dictionary with:
            - tags: Final list of tags
            - tag_details: Updated tag details with source information
    """
    if batch_mode:
        # In batch mode, return current tags or auto tags
        tags_to_return = current_tags.copy() if current_tags else auto_tags.copy()
        return {"tags": tags_to_return, "tag_details": tag_details.copy()}

    # Start with current tags if provided and non-empty, otherwise auto-generated tags
    working_tags = (
        current_tags.copy()
        if (current_tags and len(current_tags) > 0)
        else auto_tags.copy()
    )

    # Create tag_details with source information
    updated_tag_details = {}
    for tag in working_tags:
        if tag in auto_tags:
            # Auto-generated tag
            updated_tag_details[tag] = {**tag_details.get(tag, {}), "source": "auto"}
        else:
            # Manual tag
            updated_tag_details[tag] = {
                **tag_details.get(tag, {}),
                "source": "manual",
                "confidence": tag_details.get(tag, {}).get("confidence", 1.0),
            }

    while True:
        # Display current tags
        console.print("\n[bold cyan]🏷️  Tag Management[/bold cyan]")
        display_tags(working_tags, auto_tags, updated_tag_details)

        # Show menu options
        choices = [
            "✅ Done - proceed with current tags",
            "➕ Add a new tag",
        ]

        if working_tags:
            choices.append("➖ Remove tags")

        action = questionary.select("What would you like to do?", choices=choices).ask()

        if not action or "done" in action.lower() or "proceed" in action.lower():
            break
        elif "add" in action.lower():
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
                    if tag in updated_tag_details:
                        del updated_tag_details[tag]
                console.print(
                    f"  [yellow]Removed {len(tags_to_remove)} tag(s)[/yellow]"
                )

    return {"tags": working_tags, "tag_details": updated_tag_details}
