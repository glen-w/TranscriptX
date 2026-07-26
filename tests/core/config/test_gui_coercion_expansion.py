"""Config lifecycle / GUI common-settings coercion helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.config.coercion import coerce
from transcriptx.core.config.gui_support import COMMON_SETTINGS_SCHEMA
from transcriptx.core.config.registry import FieldMetadata
from transcriptx.core.config.validation import validate_config


@pytest.mark.unit
def test_coerce_bool_and_int_via_field_metadata() -> None:
    bool_meta = FieldMetadata(
        key="test.flag",
        path="test.flag",
        type=bool,
        default=False,
        description="flag",
        category="test",
    )
    int_meta = FieldMetadata(
        key="test.count",
        path="test.count",
        type=int,
        default=0,
        description="count",
        category="test",
    )
    assert coerce("true", bool_meta) is True
    assert coerce("0", bool_meta) is False
    assert coerce("12", int_meta) == 12


@pytest.mark.unit
def test_common_settings_schema_nonempty() -> None:
    assert {f.key for f in COMMON_SETTINGS_SCHEMA}


@pytest.mark.unit
def test_validate_config_empty_returns_mapping() -> None:
    result = validate_config({})
    assert isinstance(result, dict)


@pytest.mark.unit
def test_persistence_roundtrip_tmp(tmp_path: Path, monkeypatch) -> None:
    import transcriptx.core.config.persistence as persistence

    cfg_dir = tmp_path / ".transcriptx"
    drafts_dir = cfg_dir / "drafts"
    monkeypatch.setattr(persistence, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(persistence, "CONFIG_DRAFTS_DIR", drafts_dir)
    payload = {"analysis": {"sentiment_window_size": 12}}
    persistence.save_project_config(payload)
    loaded = persistence.load_project_config()
    assert loaded == payload
