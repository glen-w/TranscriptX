"""
Centralized tag editing workflow for TranscriptX.

This module provides a unified interface for tag loading, editing, state updates,
and database storage, consolidating functionality that was previously duplicated
across multiple modules.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import questionary
from rich import print

from transcriptx.cli.processing_state import (
    get_current_transcript_path_from_state,
    load_processing_state,
    save_processing_state,
)
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.core.utils.path_utils import resolve_file_path
from transcriptx.io.tag_management import manage_tags_interactive
from transcriptx.io.transcript_loader import load_segments

logger = get_logger()


def _get_transcript_manager():
    try:
        from transcriptx.database import init_database
        from transcriptx.database.transcript_manager import TranscriptManager
    except ImportError:
        return None

    init_database()
    return TranscriptManager()


def _resolve_transcript_path(transcript_path: str) -> str:
    """
    Resolve a transcript path to an existing file.

    This function uses the unified path resolution system.

    Args:
        transcript_path: Original transcript path (may be just filename or full path)

    Returns:
        Resolved path to existing transcript file

    Raises:
        FileNotFoundError: If transcript file cannot be found
    """
    return resolve_file_path(
        transcript_path, file_type="transcript", validate_state=True
    )


def load_tags_for_transcript(transcript_path: str) -> Dict[str, Any]:
    """
    Load tags for a transcript from processing state or extract them.

    This function:
    1. Searches processing state for existing tags
    2. Resolves transcript path (handles renamed files)
    3. Falls back to tag extraction if not found in state

    Args:
        transcript_path: Path to transcript file (may be old path if file was renamed)

    Returns:
        Dictionary with:
            - auto_tags: List of auto-generated tags
            - tag_details: Dictionary with tag details
            - current_tags: List of current tags (auto + manual)
            - transcript_path: Resolved transcript path
    """
    # Try to load tags from processing state first (this has the updated path after rename)
    state = load_processing_state()
    auto_tags = []
    tag_details = {}
    current_tags = []
    actual_transcript_path = transcript_path

    # Search for this transcript in processing state (check both old and new paths)
    # This is the most reliable way to get the updated path after renaming
    for file_key, entry in state.get("processed_files", {}).items():
        entry_transcript_path = entry.get("transcript_path", "")
        # Check if this entry matches the transcript (by path or by base name)
        if (
            entry_transcript_path == transcript_path
            or Path(entry_transcript_path).stem == Path(transcript_path).stem
        ):
            # Steps are stored at top level, not under "steps" key
            auto_tags = entry.get("extract_tags", {}).get("tags", [])
            tag_details = entry.get("extract_tags", {}).get("tag_details", {})
            # Use entry tags if available and non-empty, otherwise fall back to auto_tags
            entry_tags = entry.get("tags", [])
            current_tags = (
                entry_tags if entry_tags else (auto_tags.copy() if auto_tags else [])
            )
            # Use the actual transcript path from the entry (may be updated after rename)
            actual_transcript_path = entry_transcript_path
            break

    # If not found in processing state, try to resolve the path
    if not Path(actual_transcript_path).exists():
        try:
            actual_transcript_path = _resolve_transcript_path(transcript_path)
        except FileNotFoundError:
            # If resolution fails, try to find by base name in outputs directory
            base_name = Path(transcript_path).stem
            outputs_dir = Path(OUTPUTS_DIR)
            for json_file in outputs_dir.rglob(f"{base_name}.json"):
                if json_file.exists():
                    actual_transcript_path = str(json_file)
                    break
            # If still not found, use original path
            if not Path(actual_transcript_path).exists():
                actual_transcript_path = transcript_path

    # If no tags found in state, extract them
    if not auto_tags:
        # Check if file exists before trying to load it
        if not Path(actual_transcript_path).exists():
            logger.warning(
                f"Transcript file not found: {actual_transcript_path}. Skipping tag extraction."
            )
            # Continue with empty tags - user can still add tags manually
            auto_tags = []
            tag_details = {}
            current_tags = []
        else:
            try:
                segments = load_segments(actual_transcript_path)
                from transcriptx.core.analysis.tag_extraction import extract_tags

                tag_result = extract_tags(segments)
                auto_tags = tag_result.get("tags", [])
                tag_details = tag_result.get("tag_details", {})
                current_tags = auto_tags.copy()
            except Exception as e:
                logger.warning(
                    f"Could not extract tags for {actual_transcript_path}: {e}"
                )
                # Continue with empty tags - user can still add tags manually
                auto_tags = []
                tag_details = {}
                current_tags = []

    return {
        "auto_tags": auto_tags,
        "tag_details": tag_details,
        "current_tags": current_tags,
        "transcript_path": actual_transcript_path,
    }


def update_tags_in_state(
    transcript_path: str, tags: List[str], tag_details: Dict[str, Any]
) -> None:
    """
    Update tags in processing state.

    This function finds the entry for the transcript (by path or stem name)
    and updates both the `tags` and `extract_tags` entries.

    Args:
        transcript_path: Path to transcript file
        tags: List of tags to store
        tag_details: Dictionary with tag details
    """
    state = load_processing_state()
    for file_key, entry in state.get("processed_files", {}).items():
        entry_transcript_path = entry.get("transcript_path", "")
        # Match by path or base name
        if (
            entry_transcript_path == transcript_path
            or Path(entry_transcript_path).stem == Path(transcript_path).stem
        ):
            entry["tags"] = tags
            entry["tag_details"] = tag_details
            # Update the extract_tags step with new tags (stored at top level, not under "steps")
            if "extract_tags" not in entry:
                entry["extract_tags"] = {}
            entry["extract_tags"]["tags"] = tags
            entry["extract_tags"]["tag_details"] = tag_details
            break

    save_processing_state(state)


def store_tags_in_database(
    transcript_path: str,
    tags: List[str],
    tag_details: Dict[str, Any],
    conversation_type: Optional[str] = None,
    type_confidence: float = 0.0,
) -> None:
    """
    Store tags and optional conversation metadata in database.

    This is a unified function that replaces both `_store_metadata_in_database()`
    and `_store_tags_in_database()`. It handles both tags-only and full metadata storage.

    Args:
        transcript_path: Path to transcript file (may be old path if file was renamed)
        tags: List of tags to store
        tag_details: Dictionary with tag details
        conversation_type: Optional conversation type to store
        type_confidence: Optional confidence score for type detection
    """
    try:
        manager = _get_transcript_manager()
        if manager is None:
            return

        # Resolve transcript path first (handles renamed files)
        try:
            resolved_path = _resolve_transcript_path(transcript_path)
        except FileNotFoundError:
            # If path resolution fails, try to get current path from processing state
            resolved_path = (
                get_current_transcript_path_from_state(transcript_path)
                or transcript_path
            )

        # Find conversation by transcript path (try both resolved path and original)
        conversation = None
        try:
            # First try with resolved path
            conversation = manager.get_conversation_by_transcript_path(resolved_path)
            if not conversation and resolved_path != transcript_path:
                # If not found, try with original path (in case database has old path)
                conversation = manager.get_conversation_by_transcript_path(
                    transcript_path
                )
        except Exception as e:
            logger.debug(f"Could not find conversation: {e}")

        if not conversation:
            logger.debug(
                f"Conversation not found for transcript {resolved_path}, skipping metadata storage"
            )
            return

        # Store conversation type if provided
        if conversation_type:
            manager.conversation_repo.add_conversation_metadata(
                conversation_id=conversation.id,
                key="conversation_type",
                value=conversation_type,
                value_type="string",
                category="classification",
            )

            # Store type confidence
            manager.conversation_repo.add_conversation_metadata(
                conversation_id=conversation.id,
                key="type_confidence",
                value=str(type_confidence),
                value_type="number",
                category="classification",
            )

        # Store tags
        if tags:
            manager.conversation_repo.add_conversation_metadata(
                conversation_id=conversation.id,
                key="tags",
                value=json.dumps(tags),
                value_type="json",
                category="classification",
            )

            # Store tag details if available
            # Tag details now include source information (auto/manual)
            if tag_details:
                manager.conversation_repo.add_conversation_metadata(
                    conversation_id=conversation.id,
                    key="tag_details",
                    value=json.dumps(tag_details),
                    value_type="json",
                    category="classification",
                )

        logger.info(f"✅ Stored metadata for conversation {conversation.id}")

    except Exception as e:
        # Don't fail the workflow if database storage fails
        logger.warning(f"Failed to store metadata in database: {e}")


def offer_and_edit_tags(
    transcript_path: str, batch_mode: bool = False, auto_prompt: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Main entry point for tag editing workflow.

    This function:
    1. Loads tags from processing state or extracts them
    2. Optionally prompts user to edit tags (if `auto_prompt=True`)
    3. Calls `manage_tags_interactive()` for editing
    4. Updates processing state and database
    5. Returns tag result dict or None if cancelled/skipped

    Args:
        transcript_path: Path to transcript file (may be old path if file was renamed)
        batch_mode: If True, skip interactive prompts
        auto_prompt: If True, automatically prompt user; if False, return tags without prompting

    Returns:
        Dictionary with tags and tag_details, or None if cancelled/skipped
    """
    try:
        # Load tags
        tag_data = load_tags_for_transcript(transcript_path)
        auto_tags = tag_data["auto_tags"]
        tag_details = tag_data["tag_details"]
        current_tags = tag_data["current_tags"]
        actual_transcript_path = tag_data["transcript_path"]

        # In batch mode, return current tags without prompting
        if batch_mode:
            tags_to_return = current_tags.copy() if current_tags else auto_tags.copy()
            return {"tags": tags_to_return, "tag_details": tag_details.copy()}

        # Optionally prompt user
        if auto_prompt:
            print("\n[bold cyan]🏷️  Tag Management[/bold cyan]")
            if not questionary.confirm(
                f"Would you like to review/edit tags for {Path(actual_transcript_path).name}?",
                default=True,
            ).ask():
                # User declined, return current tags without editing
                return {
                    "tags": current_tags.copy() if current_tags else auto_tags.copy(),
                    "tag_details": tag_details.copy(),
                }

        # Run tag management interface
        tag_result = manage_tags_interactive(
            actual_transcript_path,
            auto_tags,
            tag_details,
            current_tags=current_tags,
            batch_mode=False,  # Allow interactive editing
        )

        final_tags = tag_result.get("tags", [])
        final_tag_details = tag_result.get("tag_details", {})

        # Update processing state
        update_tags_in_state(actual_transcript_path, final_tags, final_tag_details)

        # Update database (tags only, don't update conversation type)
        store_tags_in_database(
            actual_transcript_path,
            final_tags,
            final_tag_details,
            conversation_type=None,
            type_confidence=0.0,
        )

        if auto_prompt:
            print(
                f"[green]✅ Tags updated for {Path(actual_transcript_path).name}[/green]"
            )

        return tag_result

    except Exception as e:
        logger.warning(f"Tag editing failed for {transcript_path}: {e}")
        # Don't fail the batch process if tag editing fails
        return None
