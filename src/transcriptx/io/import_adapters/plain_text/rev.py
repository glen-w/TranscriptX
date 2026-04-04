from __future__ import annotations

from transcriptx.io.adapters.rev_adapter import RevAdapter as LegacyRevAdapter
from transcriptx.io.import_adapters.base import LegacyAdapterBridge
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class RevImportAdapter(LegacyAdapterBridge):
    def __init__(self) -> None:
        super().__init__(
            legacy=LegacyRevAdapter(),
            adapter_id="rev",
            display_name="Rev",
            adapter_kind=AdapterKind.VENDOR,
            supported_extensions=frozenset({".txt"}),
            format_family="plain_text",
            detection_priority=20,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
