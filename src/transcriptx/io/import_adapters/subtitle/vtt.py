"""Import adapter for WebVTT subtitle files."""

from __future__ import annotations

from transcriptx.io.import_adapters.base import EngineBackedImportAdapter
from transcriptx.io.import_adapters.subtitle.vtt_engine import VTTAdapter
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class VTTImportAdapter(EngineBackedImportAdapter):
    def __init__(self) -> None:
        super().__init__(
            engine=VTTAdapter(),
            adapter_id="vtt",
            display_name="WebVTT",
            adapter_kind=AdapterKind.FAMILY,
            supported_extensions=frozenset({".vtt"}),
            format_family="subtitle",
            detection_priority=10,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
