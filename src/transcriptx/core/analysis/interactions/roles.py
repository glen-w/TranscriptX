"""Interaction role resolution (actor → target).

semantics_version 2: interrupter→interrupted; responder→addressee.
Legacy (missing/1) inverted initiated/received polarity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from transcriptx.core.analysis.interactions.events import InteractionEvent

# Current corrected actor→target semantics.
INTERACTIONS_SEMANTICS_VERSION = 2
LEGACY_SEMANTICS_VERSION = 1

INTERRUPTION_TYPES = frozenset({"interruption_overlap", "interruption_gap"})
RESPONSE_TYPE = "response"
SUPPORTED_INTERACTION_TYPES = INTERRUPTION_TYPES | {RESPONSE_TYPE}

InteractionFamily = Literal["interruption", "response"]


@dataclass(frozen=True)
class InteractionRoles:
    """Resolved actor (initiates) and target (receives) for one event."""

    family: InteractionFamily
    actor: str
    target: str
    matrix_key: str  # "interruptions" | "responses"


def resolve_interaction_roles(event: InteractionEvent) -> InteractionRoles | None:
    """
    Map an event to actor→target roles.

    Event field convention (unchanged):
    - speaker_a = interrupted / prior (addressee)
    - speaker_b = interrupter / responder

    Returns None for unknown interaction types (caller skips).
    """
    itype = event.interaction_type
    if itype in INTERRUPTION_TYPES:
        return InteractionRoles(
            family="interruption",
            actor=event.speaker_b,  # interrupter
            target=event.speaker_a,  # interrupted
            matrix_key="interruptions",
        )
    if itype == RESPONSE_TYPE:
        return InteractionRoles(
            family="response",
            actor=event.speaker_b,  # responder
            target=event.speaker_a,  # addressee
            matrix_key="responses",
        )
    return None


def interruption_balance_index(asymmetry_index: float | None) -> float | None:
    """Presentation-only: 1 − asymmetry when defined. Not persisted."""
    if asymmetry_index is None:
        return None
    return 1.0 - float(asymmetry_index)
