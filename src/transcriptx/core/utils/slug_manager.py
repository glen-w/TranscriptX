"""
Slug management for human-friendly output folder names.

This module provides utilities for generating and managing slugs (human-readable
folder names) while maintaining hash-based identity for transcripts.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils._path_core import get_canonical_base_name
from transcriptx.core.utils.artifact_writer import write_json

logger = get_logger()

INDEX_FILE = Path(OUTPUTS_DIR) / ".transcriptx_index.json"


def load_index() -> Dict[str, Any]:
    """
    Load the transcript index from disk.

    Returns:
        Dictionary with structure:
        {
            "transcripts": {
                "transcript_key": {
                    "slug": "human_readable_slug",
                    "runs": ["run_id1", "run_id2", ...],
                    "source_basename": "original_filename",
                    "source_path": "/path/to/transcript.json"  # optional
                }
            },
            "slug_to_key": {
                "human_readable_slug": "transcript_key"
            }
        }
    """
    if not INDEX_FILE.exists():
        return {"transcripts": {}, "slug_to_key": {}}

    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load index file: {e}")
        return {"transcripts": {}, "slug_to_key": {}}


def save_index(index: Dict[str, Any]) -> None:
    """
    Save the transcript index to disk.

    Args:
        index: Index dictionary to save
    """
    try:
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        write_json(INDEX_FILE, index, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save index file: {e}")
        raise


def generate_slug_from_path(transcript_path: str) -> str:
    """
    Generate a slug from transcript file path.

    Uses the canonical base name (with suffix stripping) as the slug.

    Args:
        transcript_path: Path to transcript file

    Returns:
        Slug string (e.g., "260114_team_facilitation_1")
    """
    return get_canonical_base_name(transcript_path)


def find_available_slug(
    base_slug: str, transcript_key: str, index: Dict[str, Any]
) -> str:
    """
    Find an available slug, disambiguating if necessary.

    If the base slug is already used by a different transcript_key, appends
    numeric suffixes (__2, __3, etc.) until an available slug is found.

    Args:
        base_slug: Base slug to use
        transcript_key: Transcript hash key
        index: Current index dictionary

    Returns:
        Available slug (may be disambiguated)
    """
    slug_to_key = index.get("slug_to_key", {})

    # If slug is available or already belongs to this transcript, use it
    if base_slug not in slug_to_key:
        return base_slug

    if slug_to_key[base_slug] == transcript_key:
        return base_slug

    # Slug is taken by another transcript, disambiguate
    counter = 2
    while True:
        candidate_slug = f"{base_slug}__{counter}"
        if candidate_slug not in slug_to_key:
            return candidate_slug
        if slug_to_key[candidate_slug] == transcript_key:
            return candidate_slug
        counter += 1


def register_transcript(
    transcript_key: str,
    transcript_path: str,
    run_id: str,
    source_basename: Optional[str] = None,
    source_path: Optional[str] = None,
) -> str:
    """
    Register a transcript in the index and return its slug.

    If the transcript is already registered, adds the run_id to its runs list.
    Otherwise, creates a new entry with slug disambiguation if needed.

    Args:
        transcript_key: Transcript content hash (canonical identifier)
        transcript_path: Path to transcript file
        run_id: Run ID for this analysis run
        source_basename: Optional source basename (defaults to extracted from path)
        source_path: Optional source path (defaults to transcript_path)

    Returns:
        Slug assigned to this transcript
    """
    index = load_index()

    if source_basename is None:
        source_basename = get_canonical_base_name(transcript_path)
    if source_path is None:
        source_path = transcript_path

    # Check if transcript is already registered
    transcripts = index.get("transcripts", {})
    if transcript_key in transcripts:
        # Transcript exists, add run_id if not already present
        entry = transcripts[transcript_key]
        runs = entry.get("runs", [])
        if run_id not in runs:
            runs.append(run_id)
            entry["runs"] = runs
        return entry["slug"]

    # New transcript, generate slug
    base_slug = generate_slug_from_path(transcript_path)
    slug_to_key = index.get("slug_to_key", {})
    existing_key = slug_to_key.get(base_slug)
    if existing_key and existing_key != transcript_key:
        existing_entry = transcripts.get(existing_key)
        if existing_entry and existing_entry.get("source_path") == source_path:
            # Same transcript file path, treat as the same slug identity.
            merged_runs = list({*existing_entry.get("runs", []), run_id})
            transcripts.pop(existing_key, None)
            transcripts[transcript_key] = {
                "slug": base_slug,
                "runs": merged_runs,
                "source_basename": source_basename,
                "source_path": source_path,
            }
            slug_to_key[base_slug] = transcript_key
            index["slug_to_key"] = slug_to_key
            save_index(index)
            logger.debug(
                f"Reused slug '{base_slug}' for updated transcript key {transcript_key}"
            )
            return base_slug

    slug = find_available_slug(base_slug, transcript_key, index)

    # Register in index
    transcripts[transcript_key] = {
        "slug": slug,
        "runs": [run_id],
        "source_basename": source_basename,
        "source_path": source_path,
    }

    slug_to_key[slug] = transcript_key
    index["slug_to_key"] = slug_to_key

    save_index(index)

    logger.debug(f"Registered transcript {transcript_key} with slug '{slug}'")
    return slug


def get_slug_for_transcript(transcript_key: str) -> Optional[str]:
    """
    Get the slug for a transcript key.

    Args:
        transcript_key: Transcript content hash

    Returns:
        Slug if found, None otherwise
    """
    index = load_index()
    transcripts = index.get("transcripts", {})
    entry = transcripts.get(transcript_key)
    return entry["slug"] if entry else None


def get_transcript_key_for_slug(slug: str) -> Optional[str]:
    """
    Get the transcript key for a slug.

    Args:
        slug: Human-readable slug

    Returns:
        Transcript key if found, None otherwise
    """
    index = load_index()
    slug_to_key = index.get("slug_to_key", {})
    return slug_to_key.get(slug)


def list_all_transcripts() -> List[Dict[str, Any]]:
    """
    List all registered transcripts.

    Returns:
        List of transcript dictionaries with keys: transcript_key, slug, runs, source_basename, source_path
    """
    index = load_index()
    transcripts = index.get("transcripts", {})

    result = []
    for transcript_key, entry in transcripts.items():
        result.append(
            {
                "transcript_key": transcript_key,
                "slug": entry["slug"],
                "runs": entry.get("runs", []),
                "source_basename": entry.get("source_basename"),
                "source_path": entry.get("source_path"),
            }
        )

    return result
