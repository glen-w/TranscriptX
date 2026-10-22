"""
Validation and normalization for transcript library tags.

Tags are organisation metadata (e.g. meeting, voice note) stored on
processing_state entries. This module centralises rules so CLI, batch,
and state persistence share the same constraints.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Semantic tags produced by tag_extraction (also valid manual tags).
KNOWN_SEMANTIC_TAGS = frozenset({"idea", "reflection", "meeting", "todo", "question"})
# First-class organisation kinds (Theme F). Overlaps `meeting` with semantic tags.
KNOWN_KIND_TAGS = frozenset({"meeting", "voice note", "lone speaker"})
KNOWN_LIBRARY_TAGS = KNOWN_SEMANTIC_TAGS | KNOWN_KIND_TAGS

MAX_TAG_LENGTH = 64
_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9 _-]*[a-z0-9]$|^[a-z0-9]$")

_INVALID_TAG_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def normalize_tag(raw: str) -> str:
    """Normalize user input to a canonical tag string."""
    normalized = raw.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def validate_tag(raw: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a single tag string.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if raw is None:
        return False, "Tag cannot be empty"

    tag = normalize_tag(str(raw))
    if not tag:
        return False, "Tag cannot be empty"

    if len(tag) > MAX_TAG_LENGTH:
        return False, f"Tag is too long (max {MAX_TAG_LENGTH} characters)"

    if ".." in tag or "/" in tag or "\\" in tag:
        return False, "Tag contains invalid characters"

    if _INVALID_TAG_CHARS.search(tag):
        return False, "Tag contains control characters"

    if not _TAG_PATTERN.match(tag):
        return False, (
            "Tag must start and end with a letter or digit and contain only "
            "letters, digits, spaces, hyphens, and underscores"
        )

    return True, None


def sanitize_tag(raw: str) -> Optional[str]:
    """
    Normalize and validate a tag, returning None when invalid.
    """
    is_valid, _ = validate_tag(raw)
    if not is_valid:
        return None
    return normalize_tag(raw)


def sanitize_tag_list(
    tags: Optional[List[str]],
    *,
    preserve_order: bool = True,
) -> List[str]:
    """
    Normalize, validate, and deduplicate a list of tags.

    Invalid entries are dropped silently (callers should validate user
    input interactively before relying on this for persistence).
    """
    if not tags:
        return []

    seen: set[str] = set()
    result: List[str] = []
    for raw in tags:
        if not isinstance(raw, str):
            continue
        tag = sanitize_tag(raw)
        if tag is None or tag in seen:
            continue
        seen.add(tag)
        if preserve_order:
            result.append(tag)
        else:
            result.append(tag)

    return result


def validate_tag_details(
    tag_details: Any,
    *,
    tags: Optional[List[str]] = None,
) -> Tuple[bool, List[str]]:
    """
    Validate tag_details structure for processing_state persistence.

    Args:
        tag_details: Mapping of tag name -> metadata dict
        tags: Optional tag list to cross-check keys against
    """
    errors: List[str] = []

    if tag_details is None:
        return True, errors

    if not isinstance(tag_details, dict):
        return False, ["tag_details must be a dictionary"]

    for tag_name, details in tag_details.items():
        is_valid, err = validate_tag(tag_name)
        if not is_valid:
            errors.append(f"Invalid tag name in tag_details: {err}")
            continue

        if not isinstance(details, dict):
            errors.append(f"tag_details[{tag_name!r}] must be a dictionary")
            continue

        confidence = details.get("confidence")
        if confidence is not None:
            if not isinstance(confidence, (int, float)):
                errors.append(f"tag_details[{tag_name!r}].confidence must be numeric")
            elif not 0.0 <= float(confidence) <= 1.0:
                errors.append(
                    f"tag_details[{tag_name!r}].confidence must be between 0 and 1"
                )

        source = details.get("source")
        if source is not None and source not in ("auto", "manual"):
            errors.append(
                f"tag_details[{tag_name!r}].source must be 'auto' or 'manual'"
            )

    if tags is not None:
        if not isinstance(tags, list):
            errors.append("tags must be a list when provided with tag_details")
        else:
            detail_keys = set(tag_details.keys())
            tag_set = set(sanitize_tag_list(tags))
            for tag in tag_set:
                normalized = sanitize_tag(tag)
                if normalized and normalized not in detail_keys:
                    errors.append(
                        f"tag {normalized!r} listed in tags but missing from tag_details"
                    )

    return len(errors) == 0, errors


def build_tag_details(
    tags: List[str],
    auto_tags: List[str],
    existing_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Build a tag_details map with source and confidence metadata.
    """
    auto_set = set(sanitize_tag_list(auto_tags))
    details: Dict[str, Dict[str, Any]] = {}
    base = existing_details or {}

    for tag in sanitize_tag_list(tags):
        prior = base.get(tag, {})
        if tag in auto_set:
            details[tag] = {
                **prior,
                "source": "auto",
                "confidence": prior.get("confidence", 0.0),
            }
        else:
            details[tag] = {
                **prior,
                "source": "manual",
                "confidence": prior.get("confidence", 1.0),
            }

    return details


def suggest_kind_tags(
    *,
    named_speaker_count: int | None = None,
    turn_taking_speaker_count: int | None = None,
    conversation_type: str | None = None,
) -> List[str]:
    """Heuristic kind tags. Never writes Groups. Caller applies with manual-wins."""
    suggested: List[str] = []
    kind = str(conversation_type or "").strip().lower().replace("-", "_")
    if kind in {"meeting", "conversation"}:
        suggested.append("meeting")
    if kind in {"voice_note", "voice note"}:
        suggested.append("voice note")
    named = 0 if named_speaker_count is None else int(named_speaker_count)
    turns = 0 if turn_taking_speaker_count is None else int(turn_taking_speaker_count)
    if named <= 1 and turns <= 1:
        suggested.append("lone speaker")
    return sanitize_tag_list(suggested)


def merge_auto_tags_manual_wins(
    existing_tags: Optional[List[str]],
    suggested: Optional[List[str]],
) -> Tuple[List[str], List[str]]:
    """Return (merged_tags, new_auto_tags). Existing tags are never replaced."""
    current = sanitize_tag_list(list(existing_tags or []))
    current_set = set(current)
    new_auto = [
        tag
        for tag in sanitize_tag_list(list(suggested or []))
        if tag not in current_set
    ]
    return [*current, *new_auto], new_auto
