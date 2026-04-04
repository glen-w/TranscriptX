from __future__ import annotations

from transcriptx.io.adapters.srt_adapter import SRTAdapter as LegacySRTAdapter
from transcriptx.io.import_adapters.base import LegacyAdapterBridge
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class SRTImportAdapter(LegacyAdapterBridge):
    def __init__(self) -> None:
        super().__init__(
            legacy=LegacySRTAdapter(),
            adapter_id="srt",
            display_name="SRT",
            adapter_kind=AdapterKind.FAMILY,
            supported_extensions=frozenset({".srt"}),
            format_family="subtitle",
            detection_priority=10,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
