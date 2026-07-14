"""Import adapter for SRT subtitle files."""

from __future__ import annotations

from transcriptx.io.import_adapters.base import EngineBackedImportAdapter
from transcriptx.io.import_adapters.subtitle.srt_engine import SRTAdapter
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class SRTImportAdapter(EngineBackedImportAdapter):
    def __init__(self) -> None:
        super().__init__(
            engine=SRTAdapter(),
            adapter_id="srt",
            display_name="SRT",
            adapter_kind=AdapterKind.FAMILY,
            supported_extensions=frozenset({".srt"}),
            format_family="subtitle",
            detection_priority=10,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
