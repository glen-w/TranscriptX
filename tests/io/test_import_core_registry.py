from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from transcriptx.io.import_core.contracts import (
    AdapterCapabilities,
    AdapterKind,
    DetectionClass,
    DetectionInput,
    DetectionOutcome,
    ParseInput,
)
from transcriptx.io.import_core.errors import AmbiguousImportError
from transcriptx.io.import_core.registry import ImportAdapterRegistry
from transcriptx.io.intermediate_transcript import IntermediateTranscript


@dataclass
class _StubAdapter:
    adapter_id: str
    adapter_kind: AdapterKind
    score: float
    detection_priority: int = 10
    supported_extensions = frozenset({".txt"})
    display_name = "stub"
    format_family = "plain_text"
    capabilities = AdapterCapabilities()

    def probe(self, input_data: DetectionInput) -> DetectionOutcome:
        return DetectionOutcome(
            detection_class=DetectionClass.LIKELY,
            score=self.score,
            signals=(self.adapter_id,),
        )

    def parse(self, input_data: ParseInput) -> IntermediateTranscript:
        return IntermediateTranscript(
            source_tool=self.adapter_id,
            source_format="txt",
            turns=[],
            source_metadata={},
            warnings=[],
        )


def test_registry_prefers_vendor_over_generic() -> None:
    registry = ImportAdapterRegistry()
    registry.register(_StubAdapter("generic", AdapterKind.GENERIC, 0.99))
    registry.register(_StubAdapter("vendor", AdapterKind.VENDOR, 0.80))

    selected = registry.detect(path=Path("x.txt"), content=b"hello")
    assert selected.adapter.adapter_id == "vendor"


def test_registry_raises_on_ambiguous_scores() -> None:
    registry = ImportAdapterRegistry()
    registry.register(_StubAdapter("a", AdapterKind.VENDOR, 0.80))
    registry.register(_StubAdapter("b", AdapterKind.VENDOR, 0.78))

    with pytest.raises(AmbiguousImportError):
        registry.detect(path=Path("x.txt"), content=b"hello")
