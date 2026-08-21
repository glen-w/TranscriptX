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
from transcriptx.core.utils.rename.io_atomic import write_json_atomic

logger = get_logger()

INDEX_FILE = Path(OUTPUTS_DIR) / ".transcriptx_index.json"


class SlugConflictError(RuntimeError):
    """Desired slug is owned by a different transcript."""


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
    Save the transcript index to disk (crash-safe staged write).

    Args:
        index: Index dictionary to save
    """
    try:
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(INDEX_FILE, index, indent=2)
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
    run_id: Optional[str] = None,
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
        run_id: Optional run ID for this analysis run
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
        # Transcript exists, add run_id if not already present and refresh source metadata.
        # If the source basename changed (rename), prefer moving to the new base slug when
        # it's available, so future runs land in the renamed folder.
        entry = transcripts[transcript_key]
        runs = entry.get("runs", [])
        if run_id and run_id not in runs:
            runs.append(run_id)
            entry["runs"] = runs

        current_slug = str(entry.get("slug", "")).strip()
        base_slug = generate_slug_from_path(transcript_path)
        slug_to_key = index.get("slug_to_key", {})

        target_slug = current_slug
        if base_slug and base_slug != current_slug:
            owner = slug_to_key.get(base_slug)
            # Safe to move if target slug is free or already points to this key.
            if owner is None or owner == transcript_key:
                target_slug = base_slug
                if current_slug and slug_to_key.get(current_slug) == transcript_key:
                    slug_to_key.pop(current_slug, None)
                slug_to_key[target_slug] = transcript_key
                index["slug_to_key"] = slug_to_key

        if target_slug:
            entry["slug"] = target_slug
        entry["source_basename"] = source_basename
        entry["source_path"] = source_path
        transcripts[transcript_key] = entry
        index["transcripts"] = transcripts
        save_index(index)
        return entry["slug"]

    # New transcript, generate slug
    base_slug = generate_slug_from_path(transcript_path)
    slug_to_key = index.get("slug_to_key", {})
    existing_key = slug_to_key.get(base_slug)
    if existing_key and existing_key != transcript_key:
        existing_entry = transcripts.get(existing_key)
        same_file = existing_entry and (
            existing_entry.get("source_path") == source_path
            or existing_entry.get("source_basename") == source_basename
        )
        if same_file:
            # Same transcript (file moved or content changed), reuse the slug.
            existing_runs = list(existing_entry.get("runs", []))
            merged_runs = (
                list({*existing_runs, run_id}) if run_id else list(existing_runs)
            )
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
        "runs": [run_id] if run_id else [],
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


def _paths_equivalent(left: str | Path, right: str | Path) -> bool:
    """Tolerant path equality for registration validity checks."""
    try:
        left_path = Path(left).expanduser().resolve(strict=False)
        right_path = Path(right).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return str(left) == str(right)
    if left_path == right_path:
        return True
    try:
        if left_path.is_file() and right_path.is_file():
            return left_path.samefile(right_path)
    except (OSError, ValueError):
        pass
    return False


def registration_is_valid(transcript_path: str | Path, identity_hash: str) -> bool:
    """True when index entry for ``identity_hash`` points at ``transcript_path``.

    Validity requires both the transcript identity key and a matching canonical
    ``source_path``. Slug existence or basename alone is not sufficient.
    """
    key = str(identity_hash or "").strip()
    if not key:
        return False
    index = load_index()
    entry = index.get("transcripts", {}).get(key)
    if not isinstance(entry, dict):
        return False
    source_path = entry.get("source_path")
    if not source_path:
        return False
    return _paths_equivalent(source_path, transcript_path)


def get_registered_slug_for_path_and_identity(
    transcript_path: str | Path, identity_hash: str
) -> Optional[str]:
    """Return slug when registration is valid for path + identity; else None."""
    if not registration_is_valid(transcript_path, identity_hash):
        return None
    entry = load_index().get("transcripts", {}).get(str(identity_hash).strip())
    if not isinstance(entry, dict):
        return None
    slug = entry.get("slug")
    return str(slug) if slug else None


def unregister_slug(slug: str) -> bool:
    """
    Remove a slug and its transcript entry from the index.

    Use when cleaning up stale output directories (e.g. test artifacts) so
    the slug no longer appears in session dropdowns.

    Args:
        slug: Human-readable slug to remove (e.g. "test__6")

    Returns:
        True if the slug was found and removed, False otherwise
    """
    index = load_index()
    slug_to_key = index.get("slug_to_key", {})
    transcript_key = slug_to_key.pop(slug, None)
    if transcript_key is None:
        return False
    index["slug_to_key"] = slug_to_key
    transcripts = index.get("transcripts", {})
    transcripts.pop(transcript_key, None)
    index["transcripts"] = transcripts
    save_index(index)
    logger.debug(f"Unregistered slug '{slug}' from index")
    return True


def unregister_source_path(
    transcript_path: str | Path,
    *,
    retarget_to: str | Path | None = None,
) -> bool:
    """Remove index mappings for one library path without wiping a shared key.

    If the extra shares ``transcript_key`` with a kept file, ``retarget_to``
    updates ``source_path`` instead of deleting the key. Slug mappings whose
    ``source_path`` is the extra are dropped; a slug is restored from the
    keeper when the key would otherwise have none.
    """
    try:
        extra = str(Path(transcript_path).expanduser().resolve(strict=False))
    except OSError:
        extra = str(transcript_path)
    keep: str | None
    if retarget_to is None:
        keep = None
    else:
        try:
            keep = str(Path(retarget_to).expanduser().resolve(strict=False))
        except OSError:
            keep = str(retarget_to)

    index = load_index()
    transcripts = index.get("transcripts", {}) or {}
    slug_to_key = index.get("slug_to_key", {}) or {}
    changed = False

    affected_keys: set[str] = set()
    for slug, key in list(slug_to_key.items()):
        entry = transcripts.get(key)
        if not isinstance(entry, dict):
            continue
        source = entry.get("source_path")
        if source and _paths_equivalent(source, extra):
            slug_to_key.pop(slug, None)
            affected_keys.add(str(key))
            changed = True

    for key, entry in list(transcripts.items()):
        if not isinstance(entry, dict):
            continue
        source = entry.get("source_path")
        if not source or not _paths_equivalent(source, extra):
            continue
        affected_keys.add(str(key))
        remaining = [s for s, k in slug_to_key.items() if k == key]
        if keep:
            entry["source_path"] = keep
            entry["source_basename"] = get_canonical_base_name(keep)
            if not remaining:
                slug = str(entry.get("slug") or "").strip() or generate_slug_from_path(
                    keep
                )
                owner = slug_to_key.get(slug)
                if owner is None or owner == key:
                    slug_to_key[slug] = key
                    entry["slug"] = slug
            transcripts[key] = entry
            changed = True
            continue
        if remaining:
            continue
        transcripts.pop(key, None)
        changed = True

    if changed:
        index["transcripts"] = transcripts
        index["slug_to_key"] = slug_to_key
        save_index(index)
        logger.debug("Unregistered source path %s from slug index", extra)
    return changed


def list_slugs_matching(prefix: str) -> List[str]:
    """
    List all slugs that start with the given prefix.

    Useful for finding test artifacts (e.g. prefix "test__").

    Args:
        prefix: Slug prefix to match (e.g. "test__")

    Returns:
        Sorted list of matching slug names
    """
    index = load_index()
    slug_to_key = index.get("slug_to_key", {})
    return sorted(s for s in slug_to_key if s.startswith(prefix))


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


def update_index_after_transcript_rename(
    old_transcript_path: str | Path,
    new_transcript_path: str | Path,
) -> tuple[str | None, str | None]:
    """
    Refresh slug index metadata after a managed transcript rename.

    Idempotent when the old path is already gone and the new path is already
    registered. Raises ``SlugConflictError`` when the desired new slug is owned
    by a different transcript (never overwrites).

    Returns (old_slug, new_slug) when an index entry was updated, else (None, None).
    """
    index = load_index()
    transcripts = index.get("transcripts", {})
    slug_to_key = index.get("slug_to_key", {})

    try:
        old_resolved = str(Path(old_transcript_path).expanduser().resolve())
        new_resolved = str(Path(new_transcript_path).expanduser().resolve())
    except OSError:
        old_resolved = str(old_transcript_path)
        new_resolved = str(new_transcript_path)

    transcript_key: str | None = None
    old_slug: str | None = None

    for key, entry in transcripts.items():
        source_path = entry.get("source_path", "")
        if not source_path:
            continue
        try:
            resolved = str(Path(source_path).expanduser().resolve())
        except OSError:
            resolved = source_path
        if resolved == old_resolved:
            transcript_key = key
            old_slug = entry.get("slug")
            break
        if resolved == new_resolved:
            # Already pointing at new path — idempotent no-op.
            return entry.get("slug"), entry.get("slug")

    if transcript_key is None:
        return None, None

    desired_slug = generate_slug_from_path(new_resolved)
    owner = slug_to_key.get(desired_slug)
    if owner is not None and owner != transcript_key:
        raise SlugConflictError(
            f"Desired slug {desired_slug!r} is owned by transcript key {owner!r}"
        )

    from transcriptx.core.utils.file_lock import FileLock

    with FileLock(Path(INDEX_FILE), timeout=30) as lock:
        if not lock.acquired:
            raise RuntimeError("Could not acquire slug index lock")
        # Re-check conflict under lock after reload.
        index = load_index()
        slug_to_key = index.get("slug_to_key", {})
        owner = slug_to_key.get(desired_slug)
        if owner is not None and owner != transcript_key:
            raise SlugConflictError(
                f"Desired slug {desired_slug!r} is owned by transcript key {owner!r}"
            )
        new_slug = register_transcript(
            transcript_key,
            new_resolved,
            source_basename=get_canonical_base_name(new_resolved),
            source_path=new_resolved,
        )
        return old_slug, new_slug
