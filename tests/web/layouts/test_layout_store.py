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
    for layout_id in ("default", "executive", "developer_debug", "all"):
        spec = LayoutProfileStore.load_layout(layout_id)
        assert spec.id == layout_id
        assert spec.schema_version in (1, 2)
    default = LayoutProfileStore.load_layout("default")
    assert default.title == "Standard"
    assert default.schema_version == 1
    overview_ids = [b.block_id for b in default.pages["overview"].blocks]
    assert overview_ids[0] == "transcript_summary_hero"
    assert "export_panel" not in overview_ids


def test_all_layout_includes_every_block_alphabetically() -> None:
    from transcriptx.web.blocks.registry import list_blocks

    expected = sorted(spec.id for spec in list_blocks())
    assert expected  # registry must be populated
    layout = LayoutProfileStore.load_layout("all")
    assert layout.title == "All"
    assert LayoutProfileStore.is_builtin("all")
    assert "all" in LayoutProfileStore.list_layouts()
    for page_id in ("overview", "insights"):
        block_ids = [b.block_id for b in layout.pages[page_id].blocks]
        assert block_ids == expected
    with pytest.raises(LayoutValidationError, match="immutable"):
        LayoutProfileStore.save_layout(layout)


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
    path = LayoutProfileStore.save_as_custom(
        spec, "my_custom", title="My Custom", base=tmp_path
    )
    assert path.exists()
    loaded = LayoutProfileStore.load_layout("my_custom", base=tmp_path)
    assert loaded.id == "my_custom"
    assert "overview" in loaded.pages


def test_builtin_layout_cannot_be_overwritten(tmp_path: Path) -> None:
    spec = LayoutProfileStore.load_layout("default")
    with pytest.raises(LayoutValidationError, match="immutable"):
        LayoutProfileStore.save_layout(spec, base=tmp_path)


def test_default_layout_is_standard_curated() -> None:
    layout = LayoutProfileStore.load_layout("default")
    assert layout.title == "Standard"
    block_ids = [b.block_id for b in layout.pages["overview"].blocks]
    assert block_ids[0] == "transcript_summary_hero"
    assert "module_metrics" not in block_ids
    assert "export_panel" not in block_ids
    assert "run_status_compact" in block_ids


def test_default_insights_commitments_live_in_actions() -> None:
    layout = LayoutProfileStore.load_layout("default")
    insights = layout.pages["insights"].blocks
    by_id = {b.placement_id: b for b in insights}
    assert by_id["insights_commitments"].section == "actions"
    assert by_id["insights_llm_action_items"].section == "actions"
    assert by_id["insights_primary_summary"].section == "summary"
    assert by_id["insights_primary_summary"].block_id == "insights_summary_panel"
    assert by_id["insights_keyphrases"].section == "summary"
    assert by_id["insights_themes"].section == "summary"
    assert by_id["insights_themes"].params.get("focus") == "content"
    assert by_id["insights_style_markers"].section == "speakers"
    assert by_id["insights_style_markers"].params.get("focus") == "style"
    summary_ids = [b.block_id for b in insights if b.section == "summary"]
    assert summary_ids == [
        "insights_summary_panel",
        "keyphrases_block",
        "insights_contract",
    ]
    speaker_ids = [b.block_id for b in insights if b.section == "speakers"]
    assert speaker_ids == [
        "llm_speaker_summary_block",
        "lexical_diversity_block",
        "epistemic_markers_block",
        "politeness_block",
        "insights_contract",
    ]
    assert not any(b.section == "analysis" for b in insights)
    assert "executive_summary" not in {b.block_id for b in insights}
    assert "commitments_table" not in {
        b.block_id for b in insights if b.section == "summary"
    }
