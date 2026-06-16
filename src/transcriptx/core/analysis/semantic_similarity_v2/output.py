"""v2 output filenames and schema_version stamping."""

from __future__ import annotations

from typing import Any, Dict

SCHEMA_VERSION = "semantic_similarity_v2.1"

SUPPORTED_V2_MAJOR = (1,)


def with_schema(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow copy with ``schema_version`` set."""
    return {**payload, "schema_version": SCHEMA_VERSION}


def parse_schema_major(schema_version: str) -> int | None:
    """Return major version int or None if missing / malformed."""
    if not schema_version or not isinstance(schema_version, str):
        return None
    if not schema_version.startswith("semantic_similarity_v2."):
        return None
    rest = schema_version[len("semantic_similarity_v2.") :]
    parts = rest.split(".", 1)
    if not parts or not parts[0].isdigit():
        return None
    return int(parts[0])


def reader_accepts_schema(schema_version: str) -> bool:
    """True if this codebase should parse the payload (same major)."""
    major = parse_schema_major(schema_version)
    return major is not None and major in SUPPORTED_V2_MAJOR
