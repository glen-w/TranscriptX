"""Frozen V1/V2 contract identities and activation predicate.

Historical validators import only V1_* or V2_* — never live writer aliases.
Activation selects the writer branch for *new* execution only.
"""

from __future__ import annotations

from typing import Literal

# --- Permanent V1 identities (never redefined by activation) ---
V1_SCHEMA_ID = "transcriptx.llm_custom_qa.v1"
V1_MODULE_VERSION = "1"
V1_CONTRACT_VERSION = "1"
COMMIT_MARKER_SCHEMA_VERSION_V1 = "1"

# --- Permanent V2 identities (never redefined by activation) ---
V2_SCHEMA_ID = "transcriptx.llm_custom_qa.v2"
V2_MODULE_VERSION = "2"
V2_CONTRACT_VERSION = "1"
COMMIT_MARKER_SCHEMA_VERSION_V2 = "2"

CustomQAActivation = Literal["v1_live", "v2_live"]

# Sole activation authority for new execution/writes.
_ACTIVATION: CustomQAActivation = "v2_live"

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
    """Set activation (tests / Stage 5 flip only)."""
    global _ACTIVATION
    if value not in ("v1_live", "v2_live"):
        raise ValueError(f"invalid activation: {value!r}")
    _ACTIVATION = value


def custom_qa_execution_branch() -> Literal["v1", "v2"]:
    return "v2" if _ACTIVATION == "v2_live" else "v1"


def is_v2_execution_enabled() -> bool:
    return _ACTIVATION == "v2_live"


def live_schema_id_for_writers() -> str:
    """Schema id stamped by writers of *new* runs (not for historical parse)."""
    return V2_SCHEMA_ID if _ACTIVATION == "v2_live" else V1_SCHEMA_ID


def live_module_version_for_writers() -> str:
    return V2_MODULE_VERSION if _ACTIVATION == "v2_live" else V1_MODULE_VERSION
