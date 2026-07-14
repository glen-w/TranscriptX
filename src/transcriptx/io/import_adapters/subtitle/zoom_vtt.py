"""Import adapter for Zoom WebVTT subtitle exports."""

from __future__ import annotations

from transcriptx.io.adapters.zoom_adapter import ZoomAdapter as LegacyZoomAdapter
from transcriptx.io.import_adapters.base import LegacyAdapterBridge
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class ZoomVTTImportAdapter(LegacyAdapterBridge):
    def __init__(self) -> None:
        super().__init__(
            legacy=LegacyZoomAdapter(),
            adapter_id="zoom",
            display_name="Zoom VTT",
            adapter_kind=AdapterKind.VENDOR,
            supported_extensions=frozenset({".vtt"}),
            format_family="subtitle",
            detection_priority=5,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
