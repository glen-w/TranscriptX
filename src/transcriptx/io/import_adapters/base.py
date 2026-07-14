"""Shared helpers for ImportAdapter implementations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

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


class DetectParseEngine(Protocol):
    def detect_confidence(self, path: Path, content: bytes) -> float: ...

    def parse(self, path: Path, content: bytes) -> IntermediateTranscript: ...


def confidence_probe(path: Path, content: bytes, score: float) -> DetectionOutcome:
    """Map a 0..1 confidence score to DetectionOutcome (full-file probe semantics)."""
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
        signals=(f"confidence:{score:.2f}",) if score else (),
        hard_rejects=() if score else ("confidence_reject",),
        recognized_family=score > 0.0,
    )


def probe_with_engine(
    engine: DetectParseEngine, input_data: DetectionInput
) -> DetectionOutcome:
    """Probe using an engine; prefer full file bytes over truncated snippet."""
    content = input_data.snippet
    try:
        content = input_data.path.read_bytes()
    except Exception:
        pass
    score = float(engine.detect_confidence(input_data.path, content))
    return confidence_probe(input_data.path, content, score)


@dataclass
class EngineBackedImportAdapter:
    """ImportAdapter that delegates detect/parse to an engine object."""

    engine: Any
    adapter_id: str
    display_name: str
    adapter_kind: AdapterKind
    supported_extensions: frozenset[str]
    format_family: str
    detection_priority: int
    capabilities: AdapterCapabilities

    def probe(self, input_data: DetectionInput) -> DetectionOutcome:
        return probe_with_engine(self.engine, input_data)

    def parse(self, input_data: ParseInput) -> IntermediateTranscript:
        return self.engine.parse(Path(input_data.path), input_data.content)


def ensure_import_adapter(adapter: ImportAdapter) -> ImportAdapter:
    return adapter
