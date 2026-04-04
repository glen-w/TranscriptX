from __future__ import annotations

from transcriptx.io.adapters.otter_adapter import OtterAdapter as LegacyOtterAdapter
from transcriptx.io.import_adapters.base import LegacyAdapterBridge
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class OtterImportAdapter(LegacyAdapterBridge):
    def __init__(self) -> None:
        super().__init__(
            legacy=LegacyOtterAdapter(),
            adapter_id="otter",
            display_name="Otter",
            adapter_kind=AdapterKind.VENDOR,
            supported_extensions=frozenset({".txt"}),
            format_family="plain_text",
            detection_priority=20,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
