"""Tests for layout profile store and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.blocks.registry import clear_registry_for_tests
from transcriptx.web.layouts.store import LayoutProfileStore, LayoutValidationError


@pytest.fixture(autouse=True)
def _registry():
    clear_registry_for_tests()
    register_builtin_blocks()
    yield
    clear_registry_for_tests()


def test_preset_layout_yaml_loads() -> None:
    for layout_id in ("default", "executive", "developer_debug"):
        spec = LayoutProfileStore.load_layout(layout_id)
        assert spec.id == layout_id
        assert spec.schema_version == 1


def test_unknown_block_id_fails_validation(tmp_path: Path) -> None:
    bad = {
        "schema_version": 1,
        "id": "bad",
        "title": "Bad",
        "pages": {
            "overview": {
                "page_id": "overview",
                "blocks": [
                    {
                        "placement_id": "x",
                        "block_id": "nonexistent_block",
                        "visible": True,
                    }
                ],
            }
        },
    }
    with pytest.raises(LayoutValidationError, match="Unknown block_id"):
        LayoutProfileStore.validate_layout_dict(bad)


def test_duplicate_placement_id_fails(tmp_path: Path) -> None:
    bad = {
        "schema_version": 1,
        "id": "dup",
        "title": "Dup",
        "pages": {
            "overview": {
                "page_id": "overview",
                "blocks": [
                    {
                        "placement_id": "same",
                        "block_id": "run_health",
                        "visible": True,
                    },
                    {
                        "placement_id": "same",
                        "block_id": "artifact_metrics",
                        "visible": True,
                    },
                ],
            }
        },
    }
    with pytest.raises(LayoutValidationError, match="Duplicate placement_id"):
        LayoutProfileStore.validate_layout_dict(bad)


def test_unsupported_param_fails() -> None:
    bad = {
        "schema_version": 1,
        "id": "params",
        "title": "Params",
        "pages": {
            "insights": {
                "page_id": "insights",
                "blocks": [
                    {
                        "placement_id": "llm1",
                        "block_id": "llm_summary_block",
                        "visible": True,
                        "params": {"not_a_real_param": "x"},
                    }
                ],
            }
        },
    }
    with pytest.raises(LayoutValidationError, match="unsupported param"):
        LayoutProfileStore.validate_layout_dict(bad)


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    spec = LayoutProfileStore.load_layout("default")
    LayoutProfileStore.save_layout(spec, base=tmp_path)
    loaded = LayoutProfileStore.load_layout("default", base=tmp_path)
    assert loaded.id == spec.id
    assert "overview" in loaded.pages


def test_default_layout_includes_module_metrics() -> None:
    layout = LayoutProfileStore.load_layout("default")
    block_ids = [b.block_id for b in layout.pages["overview"].blocks]
    assert "module_metrics" in block_ids
    nav_index = block_ids.index("module_navigator")
    metrics_index = block_ids.index("module_metrics")
    assert metrics_index == nav_index + 1
