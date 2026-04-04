from __future__ import annotations

from transcriptx.io.adapters.vtt_adapter import VTTAdapter as LegacyVTTAdapter
from transcriptx.io.import_adapters.base import LegacyAdapterBridge
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class VTTImportAdapter(LegacyAdapterBridge):
    def __init__(self) -> None:
        super().__init__(
            legacy=LegacyVTTAdapter(),
            adapter_id="vtt",
            display_name="WebVTT",
            adapter_kind=AdapterKind.FAMILY,
            supported_extensions=frozenset({".vtt"}),
            format_family="subtitle",
            detection_priority=10,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
