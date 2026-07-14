"""Tests for import detection matrix."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.io.import_adapters.registry_builtins import build_default_registry
from transcriptx.io.import_core.errors import UnsupportedImportError


def test_detection_collision_fixture_resolves_to_non_generic() -> None:
    fixture = Path("tests/fixtures/transcripts/whisperx/standard.json")
    registry = build_default_registry()
    selected = registry.detect(path=fixture, content=fixture.read_bytes())
    assert selected.adapter.adapter_kind.value in {"vendor", "family"}


def test_detection_rejects_binary_blob_fixture() -> None:
    fixture = Path("tests/fixtures/import_detection/hard_rejects/binary_blob.bin")
    registry = build_default_registry()
    with pytest.raises(UnsupportedImportError):
        registry.detect(path=fixture, content=fixture.read_bytes())
