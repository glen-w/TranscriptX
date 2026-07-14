"""Import adapter for Zoom WebVTT subtitle exports."""

from __future__ import annotations

from transcriptx.io.import_adapters.base import EngineBackedImportAdapter
from transcriptx.io.import_adapters.subtitle.zoom_engine import ZoomAdapter
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class ZoomVTTImportAdapter(EngineBackedImportAdapter):
    def __init__(self) -> None:
        super().__init__(
            engine=ZoomAdapter(),
            adapter_id="zoom",
            display_name="Zoom VTT",
            adapter_kind=AdapterKind.VENDOR,
            supported_extensions=frozenset({".vtt"}),
            format_family="subtitle",
            detection_priority=5,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
