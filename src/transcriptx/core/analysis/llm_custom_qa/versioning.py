"""Contract identities for llm_custom_qa.

Public persisted schema id is ``transcriptx.llm_custom_qa.v1`` only.
Commit markers use integer ``COMMIT_MARKER_SCHEMA_VERSION = 1``.
"""

from __future__ import annotations

SCHEMA_ID = "transcriptx.llm_custom_qa.v1"
MODULE_VERSION = "1"
CONTRACT_VERSION = "1"
COMMIT_MARKER_SCHEMA_VERSION = 1

# Structured execution (scopes / packs / question_order) stays off in release
# builds; see docs/runtime/llm.md ("Live path vs structured path"). Test-only
# toggle: set_structured_execution_enabled(True).
_STRUCTURED_EXECUTION = False

SPEAKER_ELIGIBILITY_POLICY_VERSION = "2"
SCHEDULER_VERSION = "1"
TRANSCRIPT_BOUNDING_VERSION = "1"
TRANSCRIPT_FORMAT_VERSION = "1"
EVIDENCE_CATALOG_VERSION = "1"
RENDERED_EVIDENCE_FORMAT_VERSION = "1"
ROUTER_PROMPT_VERSION = "1"
ANSWER_PROMPT_VERSION = "1"
REPAIR_PROMPT_VERSION = "1"


def is_structured_execution_enabled() -> bool:
    return _STRUCTURED_EXECUTION


def set_structured_execution_enabled(value: bool) -> None:
    """Test-only toggle for the structured writer path."""
    global _STRUCTURED_EXECUTION
    _STRUCTURED_EXECUTION = bool(value)


def live_schema_id_for_writers() -> str:
    """Schema id stamped by writers of *new* runs."""
    return SCHEMA_ID


def live_module_version_for_writers() -> str:
    return MODULE_VERSION
