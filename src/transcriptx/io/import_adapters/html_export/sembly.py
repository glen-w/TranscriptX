from __future__ import annotations

from transcriptx.io.adapters.sembly_adapter import SemblyAdapter as LegacySemblyAdapter
from transcriptx.io.import_adapters.base import LegacyAdapterBridge
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class SemblyImportAdapter(LegacyAdapterBridge):
    def __init__(self) -> None:
        super().__init__(
            legacy=LegacySemblyAdapter(),
            adapter_id="sembly",
            display_name="Sembly",
            adapter_kind=AdapterKind.VENDOR,
            supported_extensions=frozenset({".json", ".html"}),
            format_family="html_export",
            detection_priority=20,
            capabilities=AdapterCapabilities(
                supports_speaker_labels=True, produces_html_markup=True
            ),
        )
