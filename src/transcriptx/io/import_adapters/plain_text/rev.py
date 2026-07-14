"""Import adapter for Rev plain-text transcripts."""

from __future__ import annotations

from transcriptx.io.import_adapters.base import EngineBackedImportAdapter
from transcriptx.io.import_adapters.plain_text.rev_engine import RevAdapter
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class RevImportAdapter(EngineBackedImportAdapter):
    def __init__(self) -> None:
        super().__init__(
            engine=RevAdapter(),
            adapter_id="rev",
            display_name="Rev",
            adapter_kind=AdapterKind.VENDOR,
            supported_extensions=frozenset({".txt"}),
            format_family="plain_text",
            detection_priority=20,
            capabilities=AdapterCapabilities(supports_speaker_labels=True),
        )
