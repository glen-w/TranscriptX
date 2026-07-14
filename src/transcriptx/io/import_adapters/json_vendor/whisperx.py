"""Import adapter for WhisperX JSON transcripts."""

from __future__ import annotations

from transcriptx.io.adapters.whisperx_adapter import (
    WhisperXAdapter as LegacyWhisperXAdapter,
)
from transcriptx.io.import_adapters.base import LegacyAdapterBridge
from transcriptx.io.import_core.contracts import AdapterCapabilities, AdapterKind


class WhisperXImportAdapter(LegacyAdapterBridge):
    def __init__(self) -> None:
        super().__init__(
            legacy=LegacyWhisperXAdapter(),
            adapter_id="whisperx",
            display_name="WhisperX JSON",
            adapter_kind=AdapterKind.VENDOR,
            supported_extensions=frozenset({".json"}),
            format_family="json_vendor",
            detection_priority=20,
            capabilities=AdapterCapabilities(
                supports_word_timestamps=True,
                supports_confidence_scores=True,
                supports_speaker_labels=True,
            ),
        )
