"""Base helpers bridging legacy adapters into the import registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from transcriptx.io.import_core.contracts import (
    AdapterCapabilities,
    AdapterKind,
    DetectionClass,
    DetectionInput,
    DetectionOutcome,
    ImportAdapter,
    ParseInput,
)
from transcriptx.io.intermediate_transcript import IntermediateTranscript


@dataclass
class LegacyAdapterBridge:
    """Bridge legacy adapters to new ImportAdapter contract."""

    legacy: Any
    adapter_id: str
    display_name: str
    adapter_kind: AdapterKind
    supported_extensions: frozenset[str]
    format_family: str
    detection_priority: int
    capabilities: AdapterCapabilities

    def probe(self, input_data: DetectionInput) -> DetectionOutcome:
        # Legacy adapters expect to see the full file content, not a truncated snippet.
        # For JSON/vendor formats (notably WhisperX), large files can exceed the
        # snippet window, and attempting to parse only the snippet leads to
        # JSONDecodeError and spurious UNKNOWN_INPUT outcomes.
        #
        # To keep the modern detection contract stable while preserving legacy
        # behaviour, prefer the full file content when available and fall back to
        # the snippet if a read fails.
        content = input_data.snippet
        try:
            # Re-read from disk so we don't have to plumb full content through
            # DetectionInput; this keeps the bridge self-contained.
            content = input_data.path.read_bytes()
        except Exception:
            pass

        score = float(self.legacy.detect_confidence(input_data.path, content))
        if score >= 0.95:
            cls = DetectionClass.DEFINITIVE
        elif score >= 0.6:
            cls = DetectionClass.LIKELY
        elif score > 0.0:
            cls = DetectionClass.POSSIBLE
        else:
            cls = DetectionClass.REJECT
        return DetectionOutcome(
            detection_class=cls,
            score=score,
            signals=(f"legacy_confidence:{score:.2f}",) if score else (),
            hard_rejects=() if score else ("legacy_reject",),
            recognized_family=score > 0.0,
        )

    def parse(self, input_data: ParseInput) -> IntermediateTranscript:
        return self.legacy.parse(Path(input_data.path), input_data.content)


def ensure_import_adapter(adapter: ImportAdapter) -> ImportAdapter:
    return adapter
