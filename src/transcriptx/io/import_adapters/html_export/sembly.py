"""Import adapter for Sembly HTML exports."""

from __future__ import annotations

from transcriptx.io.import_adapters.base import EngineBackedImportAdapter
from transcriptx.io.import_adapters.html_export.sembly_engine import SemblyAdapter
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class SemblyImportAdapter(EngineBackedImportAdapter):
    def __init__(self) -> None:
        super().__init__(
            engine=SemblyAdapter(),
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
