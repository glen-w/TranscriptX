"""Import adapter for generic plain-text transcripts."""

from __future__ import annotations

from transcriptx.io.import_adapters.base import EngineBackedImportAdapter
from transcriptx.io.import_adapters.plain_text.generic_text_engine import (
    GenericDiarisedTextAdapter,
)
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class GenericTextImportAdapter(EngineBackedImportAdapter):
    def __init__(self) -> None:
        super().__init__(
            engine=GenericDiarisedTextAdapter(),
            adapter_id="generic_text",
            display_name="Generic Diarized Text",
            adapter_kind=AdapterKind.GENERIC,
            supported_extensions=frozenset({".txt", ".md", ".log"}),
            format_family="plain_text",
            detection_priority=1000,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
