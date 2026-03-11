"""
SourceAdapter protocol and UnsupportedFormatError.

All source adapters must implement this protocol.  Defined in one place so
transcript_importer.py, AdapterRegistry, and test helpers share the same type.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Protocol, runtime_checkable

from transcriptx.io.intermediate_transcript import IntermediateTranscript


class UnsupportedFormatError(ValueError):
    """Raised when no adapter can handle the input file."""


@runtime_checkable
class SourceAdapter(Protocol):
    source_id: ClassVar[str]
    """Stable identifier written into source.type in the JSON artifact."""

    supported_extensions: ClassVar[tuple[str, ...]]
    """File extensions this adapter may handle (lower-case, with dot)."""

    priority: ClassVar[int]
    """Lower value = evaluated first.  Controls evaluation order and breaks ties
    between equal-confidence matches.  Is not the primary selection criterion —
    that is always the confidence score."""

    def detect_confidence(self, path: Path, content: bytes) -> float:
        """Return a confidence score in [0.0, 1.0].

        May inspect the first 4 KB of file content (the registry controls what
        is passed).  0.0 = definitely cannot handle; 1.0 = definitive match.
        Only adapters whose extension matches supported_extensions are called
        by the registry for extension-specific detection.  Generic fallback
        adapters (priority=1000) are evaluated separately if no specific
        adapter matches.
        """
        ...

    def parse(self, path: Path, content: bytes) -> IntermediateTranscript:
        """Parse already-read bytes into IntermediateTranscript.

        Must not raise on recoverable issues — append them to
        IntermediateTranscript.warnings instead.  The adapter is responsible
        for all vendor-specific preamble/metadata stripping before producing
        turns.
        """
        ...
