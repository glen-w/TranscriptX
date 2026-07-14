"""Import adapter for generic plain-text transcripts."""

from __future__ import annotations

from transcriptx.io.adapters.generic_diarised_text_adapter import (
    GenericDiarisedTextAdapter as LegacyGenericDiarisedTextAdapter,
)
from transcriptx.io.import_adapters.base import LegacyAdapterBridge
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class GenericTextImportAdapter(LegacyAdapterBridge):
    def __init__(self) -> None:
        super().__init__(
            legacy=LegacyGenericDiarisedTextAdapter(),
            adapter_id="generic_text",
            display_name="Generic Diarized Text",
            adapter_kind=AdapterKind.GENERIC,
            supported_extensions=frozenset({".txt", ".md", ".log"}),
            format_family="plain_text",
            detection_priority=1000,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
