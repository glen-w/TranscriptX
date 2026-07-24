"""Epoch-1 contract identities for llm_custom_qa.

Public persisted schema id is ``transcriptx.llm_custom_qa.v1`` only.
Commit markers use integer ``COMMIT_MARKER_SCHEMA_VERSION = 1``.
"""

from __future__ import annotations

from typing import Literal

# Sole live public schema identity (epoch-1).
SCHEMA_ID = "transcriptx.llm_custom_qa.v1"
MODULE_VERSION = "1"
CONTRACT_VERSION = "1"
COMMIT_MARKER_SCHEMA_VERSION = 1

# Historical aliases retained so older imports resolve; values match epoch-1.
V1_SCHEMA_ID = SCHEMA_ID
V1_MODULE_VERSION = MODULE_VERSION
V1_CONTRACT_VERSION = CONTRACT_VERSION
COMMIT_MARKER_SCHEMA_VERSION_V1 = COMMIT_MARKER_SCHEMA_VERSION
V2_SCHEMA_ID = SCHEMA_ID
V2_MODULE_VERSION = MODULE_VERSION
V2_CONTRACT_VERSION = CONTRACT_VERSION
COMMIT_MARKER_SCHEMA_VERSION_V2 = COMMIT_MARKER_SCHEMA_VERSION

CustomQAActivation = Literal["v1_live", "v2_live"]

# Activation is frozen to the sole epoch-1 writer path.
_ACTIVATION: CustomQAActivation = "v1_live"

SPEAKER_ELIGIBILITY_POLICY_VERSION = "2"
SCHEDULER_VERSION = "1"
TRANSCRIPT_BOUNDING_VERSION = "1"
TRANSCRIPT_FORMAT_VERSION = "1"
EVIDENCE_CATALOG_VERSION = "1"
RENDERED_EVIDENCE_FORMAT_VERSION = "1"
ROUTER_PROMPT_VERSION = "1"
ANSWER_PROMPT_VERSION = "1"
REPAIR_PROMPT_VERSION = "1"


def get_custom_qa_activation() -> CustomQAActivation:
    """Return the current activation branch for new execution/writes."""
    return _ACTIVATION


def set_custom_qa_activation(value: CustomQAActivation) -> None:
    """Set activation (tests only). Epoch-1 always writes the sole live schema."""
    global _ACTIVATION
    if value not in ("v1_live", "v2_live"):
        raise ValueError(f"invalid activation: {value!r}")
    _ACTIVATION = value


def custom_qa_execution_branch() -> Literal["v1", "v2"]:
    # Epoch-1: single writer path; keep return shape for callers.
    return "v1"


def is_v2_execution_enabled() -> bool:
    return False


def live_schema_id_for_writers() -> str:
    """Schema id stamped by writers of *new* runs."""
    return SCHEMA_ID


def live_module_version_for_writers() -> str:
    return MODULE_VERSION
