"""Import adapter for Fireflies plain-text transcripts."""

from __future__ import annotations

from transcriptx.io.import_adapters.base import EngineBackedImportAdapter
from transcriptx.io.import_adapters.plain_text.fireflies_engine import FirefliesAdapter
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class FirefliesImportAdapter(EngineBackedImportAdapter):
    def __init__(self) -> None:
        super().__init__(
            engine=FirefliesAdapter(),
            adapter_id="fireflies",
            display_name="Fireflies",
            adapter_kind=AdapterKind.VENDOR,
            supported_extensions=frozenset({".txt"}),
            format_family="plain_text",
            detection_priority=20,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
