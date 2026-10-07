"""Typed models for assistive rename suggestions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

SuggestionBasis = Literal[
    "filename_datetime",
    "transcript_date",
    "transcript_title",
    "llm",
    "web",
    "file_mtime",
]
SuggestionConfidence = Literal["strong", "likely", "possible", "file"]

SCHEMA_VERSION = "transcriptx.rename_suggestions.v1"


@dataclass(frozen=True)
class RenameOption:
    """One pickable rename stem."""

    stem: str
    basis: SuggestionBasis
    confidence: SuggestionConfidence
    detail: str
    event_date: date | None = None
    title: str = ""


@dataclass
class RenameSuggestionsResult:
    """Per-transcript suggestion run (assistive; never auto-writes)."""

    transcript_path: str
    transcript_fingerprint: str
    pattern: str
    options: tuple[RenameOption, ...] = ()
    prefill: str = ""
    status: str = ""
    llm_model: str | None = None
    llm_model_source: str | None = None
    effort: str | None = None
    cache_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "transcript_path": self.transcript_path,
            "transcript_fingerprint": self.transcript_fingerprint,
            "pattern": self.pattern,
            "prefill": self.prefill,
            "status": self.status,
            "llm_model": self.llm_model,
            "llm_model_source": self.llm_model_source,
            "effort": self.effort,
            "cache_key": self.cache_key,
            "options": [
                {
                    "stem": o.stem,
                    "basis": o.basis,
                    "confidence": o.confidence,
                    "detail": o.detail,
                    "event_date": o.event_date.isoformat() if o.event_date else None,
                    "title": o.title,
                }
                for o in self.options
            ],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RenameSuggestionsResult:
        options_raw = raw.get("options") or []
        options: list[RenameOption] = []
        for row in options_raw:
            if not isinstance(row, dict):
                continue
            ed = row.get("event_date")
            event_date = date.fromisoformat(ed) if isinstance(ed, str) and ed else None
            options.append(
                RenameOption(
                    stem=str(row.get("stem") or ""),
                    basis=row.get("basis") or "transcript_title",  # type: ignore[arg-type]
                    confidence=row.get("confidence") or "possible",  # type: ignore[arg-type]
                    detail=str(row.get("detail") or ""),
                    event_date=event_date,
                    title=str(row.get("title") or ""),
                )
            )
        return cls(
            transcript_path=str(raw.get("transcript_path") or ""),
            transcript_fingerprint=str(raw.get("transcript_fingerprint") or ""),
            pattern=str(raw.get("pattern") or ""),
            options=tuple(options),
            prefill=str(raw.get("prefill") or ""),
            status=str(raw.get("status") or ""),
            llm_model=raw.get("llm_model"),
            llm_model_source=raw.get("llm_model_source"),
            effort=raw.get("effort"),
            cache_key=str(raw.get("cache_key") or ""),
        )


@dataclass
class RawRenameCue:
    """Intermediate cue before stem rendering."""

    basis: SuggestionBasis
    confidence: SuggestionConfidence
    detail: str
    event_date: date | None = None
    title: str = ""
    quote: str = ""

    # Populated by rank/render; not stored on RenameOption separately.
    _priority: int = field(default=0, compare=False)
