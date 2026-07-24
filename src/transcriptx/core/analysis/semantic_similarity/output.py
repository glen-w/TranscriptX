"""Semantic similarity output filenames and method-fingerprint stamping.

``SCHEMA_VERSION`` is a method/semantics fingerprint, not the public module id.
"""

from __future__ import annotations

from typing import Any, Dict

# Method fingerprint (not a public module id / schema envelope).
SCHEMA_VERSION = "transcriptx.semantic_similarity.semantics.1.1"

SUPPORTED_SEMANTICS_MAJOR = (1,)

# Embedding semantics version for cross-session provenance (B14).
EMBEDDING_SEMANTICS_VERSION = "semantic_embed_sem.1"

POOLED_SCHEMA_VERSION = "transcriptx.semantic_similarity_pooled.v1"


def with_schema(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow copy with ``schema_version`` set."""
    return {**payload, "schema_version": SCHEMA_VERSION}


def parse_schema_major(schema_version: str) -> int | None:
    """Return major version int or None if missing / malformed."""
    if not schema_version or not isinstance(schema_version, str):
        return None
    prefix = "transcriptx.semantic_similarity.semantics."
    if schema_version.startswith(prefix):
        rest = schema_version[len(prefix) :]
        parts = rest.split(".", 1)
        if parts and parts[0].isdigit():
            return int(parts[0])
        return None
    # Unsupported method stamps are refused (no dual-accept).
    return None


def reader_accepts_schema(schema_version: str) -> bool:
    """True if this codebase should parse the payload (same major)."""
    major = parse_schema_major(schema_version)
    return major is not None and major in SUPPORTED_SEMANTICS_MAJOR
