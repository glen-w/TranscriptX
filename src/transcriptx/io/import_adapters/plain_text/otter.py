"""Import adapter for Otter.ai plain-text transcripts."""

from __future__ import annotations

from transcriptx.io.import_adapters.base import EngineBackedImportAdapter
from transcriptx.io.import_adapters.plain_text.otter_engine import OtterAdapter
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class OtterImportAdapter(EngineBackedImportAdapter):
    def __init__(self) -> None:
        super().__init__(
            engine=OtterAdapter(),
            adapter_id="otter",
            display_name="Otter",
            adapter_kind=AdapterKind.VENDOR,
            supported_extensions=frozenset({".txt"}),
            format_family="plain_text",
            detection_priority=20,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
