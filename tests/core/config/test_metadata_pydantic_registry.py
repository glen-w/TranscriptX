"""Registry parity tests for Pydantic-backed metadata.* settings."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from transcriptx.core.config.models.metadata import MetadataSettingsModel
from transcriptx.core.config.pydantic_registry import serialize_field_metadata
from transcriptx.core.config.registry import build_registry, get_default_config_dict
from transcriptx.core.utils.config.workflow import MetadataConfig

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PREFIX = "metadata."


def test_build_registry_metadata_matches_golden() -> None:
    golden = json.loads((FIXTURES / "metadata_registry_golden.json").read_text())
    reg = build_registry()
    for key, expected in golden.items():
        assert key in reg, key
        assert serialize_field_metadata(reg[key]) == expected


def test_pydantic_defaults_match_dataclass_defaults() -> None:
    assert MetadataSettingsModel().model_dump() == asdict(MetadataConfig())


def test_default_metadata_subtree_matches_golden() -> None:
    golden = json.loads((FIXTURES / "metadata_defaults_golden.json").read_text())
    assert get_default_config_dict()["metadata"] == golden
