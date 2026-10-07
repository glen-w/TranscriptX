"""Typed models for assistive speaker name suggestions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SuggestionBasis = Literal[
    "self_intro",
    "moderator_list",
    "vocative",
    "roster",
    "moderator_intro",
    "peer_reference",
]
SuggestionConfidence = Literal["strong", "possible", "likely"]


@dataclass(frozen=True)
class NameOption:
    """One pickable name for a diarized speaker."""

    display_name: str
    basis: SuggestionBasis
    confidence: SuggestionConfidence
    quote: str = ""
    source: Literal["deterministic", "llm"] = "deterministic"


@dataclass(frozen=True)
class RosterPerson:
    """A person name seen in the transcript (NER roster)."""

    display_name: str
    normalized_key: str
    mention_count: int
    mentioned_by_speakers: tuple[str, ...] = ()
    sample_quote: str = ""


@dataclass
class NameSuggestionsResult:
    """Per-transcript suggestion run (assistive; never auto-writes)."""

    transcript_path: str
    managed_transcript_id: str | None
    transcript_fingerprint: str
    roster: tuple[RosterPerson, ...] = ()
    per_speaker: dict[str, tuple[NameOption, ...]] = field(default_factory=dict)
    status_message: str = ""
    llm_used: bool = False
    llm_model: str | None = None
    llm_model_source: str | None = None
    from_cache: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": "transcriptx.name_suggestions.v1",
            "transcript_path": self.transcript_path,
            "managed_transcript_id": self.managed_transcript_id,
            "transcript_fingerprint": self.transcript_fingerprint,
            "status_message": self.status_message,
            "llm_used": self.llm_used,
            "llm_model": self.llm_model,
            "llm_model_source": self.llm_model_source,
            "roster": [
                {
                    "display_name": p.display_name,
                    "normalized_key": p.normalized_key,
                    "mention_count": p.mention_count,
                    "mentioned_by_speakers": list(p.mentioned_by_speakers),
                    "sample_quote": p.sample_quote,
                }
                for p in self.roster
            ],
            "per_speaker": {
                sid: [
                    {
                        "display_name": o.display_name,
                        "basis": o.basis,
                        "confidence": o.confidence,
                        "quote": o.quote,
                        "source": o.source,
                    }
                    for o in options
                ]
                for sid, options in self.per_speaker.items()
            },
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> NameSuggestionsResult | None:
        if raw.get("schema_id") != "transcriptx.name_suggestions.v1":
            return None
        roster: list[RosterPerson] = []
        for row in raw.get("roster") or []:
            if not isinstance(row, dict):
                continue
            name = str(row.get("display_name") or "").strip()
            if not name:
                continue
            roster.append(
                RosterPerson(
                    display_name=name,
                    normalized_key=str(row.get("normalized_key") or name).casefold(),
                    mention_count=int(row.get("mention_count") or 0),
                    mentioned_by_speakers=tuple(
                        str(x) for x in (row.get("mentioned_by_speakers") or ())
                    ),
                    sample_quote=str(row.get("sample_quote") or ""),
                )
            )
        per: dict[str, tuple[NameOption, ...]] = {}
        raw_per = raw.get("per_speaker")
        if isinstance(raw_per, dict):
            for sid, options in raw_per.items():
                if not isinstance(options, list):
                    continue
                parsed: list[NameOption] = []
                for opt in options:
                    if not isinstance(opt, dict):
                        continue
                    dn = str(opt.get("display_name") or "").strip()
                    if not dn:
                        continue
                    parsed.append(
                        NameOption(
                            display_name=dn,
                            basis=str(opt.get("basis") or "roster"),  # type: ignore[arg-type]
                            confidence=str(opt.get("confidence") or "possible"),  # type: ignore[arg-type]
                            quote=str(opt.get("quote") or ""),
                            source=str(opt.get("source") or "deterministic"),  # type: ignore[arg-type]
                        )
                    )
                per[str(sid)] = tuple(parsed)
        return cls(
            transcript_path=str(raw.get("transcript_path") or ""),
            managed_transcript_id=raw.get("managed_transcript_id"),
            transcript_fingerprint=str(raw.get("transcript_fingerprint") or ""),
            roster=tuple(roster),
            per_speaker=per,
            status_message=str(raw.get("status_message") or ""),
            llm_used=bool(raw.get("llm_used")),
            llm_model=raw.get("llm_model"),
            llm_model_source=raw.get("llm_model_source"),
            from_cache=True,
            error=raw.get("error"),
        )

    def workspace_payload(self) -> dict[str, Any]:
        """JSON-safe payload for the Speaker ID CCv2 workspace."""
        return {
            "status_message": self.status_message,
            "llm_used": self.llm_used,
            "llm_model": self.llm_model,
            "roster": [
                {
                    "display_name": p.display_name,
                    "mention_count": p.mention_count,
                    "sample_quote": p.sample_quote,
                }
                for p in self.roster
            ],
            "by_speaker": {
                sid: [
                    {
                        "display_name": o.display_name,
                        "basis": o.basis,
                        "confidence": o.confidence,
                        "quote": o.quote,
                        "label": _option_label(o),
                    }
                    for o in options
                ]
                for sid, options in self.per_speaker.items()
            },
        }


def _option_label(option: NameOption) -> str:
    basis_labels = {
        "self_intro": "Self-introduction",
        "moderator_list": "Listed by moderator",
        "vocative": "Addressed in dialogue",
        "roster": "Mentioned in transcript",
        "moderator_intro": "Moderator introduction (LLM)",
        "peer_reference": "Referenced by another speaker (LLM)",
    }
    bit = basis_labels.get(option.basis, option.basis)
    return f"{option.display_name} — {bit}"
