"""Wordcloud data models for dynamic term explorers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class WordcloudTerm:
    term: str
    value: float
    rank: int
    pos: Optional[str] = None
    kind: Optional[str] = None
    token_count: Optional[int] = None


@dataclass
class WordcloudTerms:
    source: str
    variant: str
    variant_key: str
    speaker: Optional[str]
    ngram: Optional[int]
    metric: str
    terms: list[WordcloudTerm]
    min_count: Optional[int] = None
    min_bigram_count: Optional[int] = None
    run_id: Optional[str] = None
    transcript_key: Optional[str] = None
    created_at: Optional[str] = None
    method: Optional[str] = None
    upstream_schema_id: Optional[str] = None
    upstream_semantics_version: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.created_at:
            payload["created_at"] = datetime.now(timezone.utc).isoformat()
        payload["terms"] = [
            {**asdict(term), "value": float(term.value)} for term in self.terms
        ]
        return payload
