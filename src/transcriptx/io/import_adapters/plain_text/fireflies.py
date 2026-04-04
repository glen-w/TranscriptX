from __future__ import annotations

from transcriptx.io.adapters.fireflies_adapter import (
    FirefliesAdapter as LegacyFirefliesAdapter,
)
from transcriptx.io.import_adapters.base import LegacyAdapterBridge
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class FirefliesImportAdapter(LegacyAdapterBridge):
    def __init__(self) -> None:
        super().__init__(
            legacy=LegacyFirefliesAdapter(),
            adapter_id="fireflies",
            display_name="Fireflies",
            adapter_kind=AdapterKind.VENDOR,
            supported_extensions=frozenset({".txt"}),
            format_family="plain_text",
            detection_priority=20,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
