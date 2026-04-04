from __future__ import annotations

from transcriptx.io.import_adapters.html_export.sembly import SemblyImportAdapter
from transcriptx.io.import_adapters.json_vendor.whisperx import WhisperXImportAdapter
from transcriptx.io.import_adapters.plain_text.fireflies import FirefliesImportAdapter
from transcriptx.io.import_adapters.plain_text.generic_text import (
    GenericTextImportAdapter,
)
from transcriptx.io.import_adapters.plain_text.otter import OtterImportAdapter
from transcriptx.io.import_adapters.plain_text.rev import RevImportAdapter
from transcriptx.io.import_adapters.subtitle.srt import SRTImportAdapter
from transcriptx.io.import_adapters.subtitle.vtt import VTTImportAdapter
from transcriptx.io.import_adapters.subtitle.zoom_vtt import ZoomVTTImportAdapter
from transcriptx.io.import_core.registry import ImportAdapterRegistry


def build_default_registry() -> ImportAdapterRegistry:
    registry = ImportAdapterRegistry()
    for adapter in _bridged_adapters():
        registry.register(adapter)
    return registry


def _bridged_adapters():
    return [
        ZoomVTTImportAdapter(),
        VTTImportAdapter(),
        SRTImportAdapter(),
        WhisperXImportAdapter(),
        SemblyImportAdapter(),
        OtterImportAdapter(),
        FirefliesImportAdapter(),
        RevImportAdapter(),
        GenericTextImportAdapter(),
    ]
