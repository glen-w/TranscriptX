"""Retired public module / schema identities (epoch-1).

These must not appear in live registries, presets, aggregation maps, or
generated fixtures. Selection strips retired module IDs from user lists.
"""

from __future__ import annotations

# Public analysis module ids retired in the 0.9.3 schema epoch.
RETIRED_PUBLIC_MODULE_IDS: frozenset[str] = frozenset(
    {
        "semantic_similarity_advanced",
        "semantic_similarity_v2",
    }
)

# Obsolete dual-writer / pre-epoch public schema identity strings.
OBSOLETE_PUBLIC_SCHEMA_IDS: frozenset[str] = frozenset(
    {
        "transcriptx.llm_custom_qa.v2",
        "transcriptx.llm_action_items.v2",
    }
)

# Pattern: public module ids must not end with _vN (N >= 2).
PUBLIC_MODULE_VN_SUFFIX_RE = r"^[a-z][a-z0-9_]*_v[2-9]\d*$"
