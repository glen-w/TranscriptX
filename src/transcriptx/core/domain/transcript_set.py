"""
TranscriptSet data carrier for group analysis.

TranscriptSet is intentionally minimal: it stores ordered transcript IDs,
optional metadata, and provides deterministic key computation plus path
resolution through a caller-provided resolver.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class TranscriptSet:
    """Immutable data carrier for grouped transcript analysis."""

    key: str
    name: Optional[str]
    transcript_ids: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def resolve_transcripts(
        self, resolver: Optional[Callable[[str], str]] = None
    ) -> List[str]:
        """
        Resolve transcript IDs to file paths using the provided resolver.

        If no resolver is provided, returns transcript_ids unchanged.
        """
        if resolver is None:
            return list(self.transcript_ids)
        return [resolver(transcript_id) for transcript_id in self.transcript_ids]

    @staticmethod
    def compute_key(transcript_ids: List[str]) -> str:
        """
        Compute a stable hash for the ordered transcript IDs.
        """
        payload = json.dumps(
            transcript_ids,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def create(
        cls,
        transcript_ids: List[str],
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        key: Optional[str] = None,
    ) -> "TranscriptSet":
        """
        Create a TranscriptSet with a computed key when not provided.
        """
        resolved_key = key or cls.compute_key(transcript_ids)
        return cls(
            key=resolved_key,
            name=name,
            transcript_ids=list(transcript_ids),
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize TranscriptSet for persistence."""
        return {
            "key": self.key,
            "name": self.name,
            "transcript_ids": list(self.transcript_ids),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptSet":
        """Deserialize TranscriptSet from persisted data."""
        return cls(
            key=data["key"],
            name=data.get("name"),
            transcript_ids=list(data.get("transcript_ids", [])),
            metadata=dict(data.get("metadata", {})),
        )
