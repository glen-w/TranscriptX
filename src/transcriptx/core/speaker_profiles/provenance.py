"""Typed link provenance for speaker-profile mutations (voice phase + manual)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError

LinkMethod = Literal[
    "manual",
    "suggestion_assisted",
    "choose_other",
    "create_new",
    "relink",
    "supersede",
]

ConfidenceCategory = Literal["strong", "possible", "weak"]


class LinkProvenanceV1(BaseModel):
    """Validated provenance stored on ``SpeakerProfileLinkV1.provenance``.

    UI and façades must construct this model — never pass an unrestricted dict.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    link_method: LinkMethod = "manual"
    suggestion_id: Optional[str] = None
    suggestion_digest: Optional[str] = None
    decision_id: Optional[str] = None
    model_generation_id: Optional[str] = None
    confidence_category: Optional[ConfidenceCategory] = None
    voice_acceptance_op_id: Optional[str] = None
    relinked_from: Optional[str] = None

    @model_validator(mode="after")
    def _check_suggestion_fields(self) -> LinkProvenanceV1:
        if self.link_method == "suggestion_assisted":
            if not self.suggestion_id or not self.suggestion_digest:
                raise SpeakerProfileContractError(
                    "suggestion_assisted provenance requires suggestion_id "
                    "and suggestion_digest"
                )
        return self

    def to_storage_dict(self) -> dict[str, Any]:
        """Serialize for the link ``provenance`` JSON object (omit nulls)."""
        raw = self.model_dump(mode="python")
        return {k: v for k, v in raw.items() if v is not None}


def coerce_link_provenance(
    provenance: LinkProvenanceV1 | None,
    *,
    default_method: LinkMethod = "manual",
) -> LinkProvenanceV1:
    """Return validated provenance; default manual when omitted."""
    if provenance is None:
        return LinkProvenanceV1(link_method=default_method)
    if not isinstance(provenance, LinkProvenanceV1):
        raise SpeakerProfileContractError(
            "provenance must be LinkProvenanceV1, not a raw mapping"
        )
    return provenance


def parse_stored_provenance(raw: dict[str, Any] | None) -> LinkProvenanceV1 | None:
    """Best-effort parse of stored provenance; unknown shapes return None."""
    if not raw:
        return None
    try:
        return LinkProvenanceV1.model_validate(raw)
    except Exception:
        # Legacy / partial dicts (e.g. migrate-only keys) are not LinkProvenanceV1
        return None
