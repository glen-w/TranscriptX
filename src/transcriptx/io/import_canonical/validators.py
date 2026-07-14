"""Validate canonical transcript documents before admission."""

from __future__ import annotations

from typing import Mapping, Any

from transcriptx.io.transcript_schema import validate_transcript_document


def validate_canonical_document(document: Mapping[str, Any]) -> None:
    validate_transcript_document(dict(document))
