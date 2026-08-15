"""Tests for layout profile store and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.blocks.registry import clear_registry_for_tests
from transcriptx.web.layouts.store import (
    BUILTIN_LAYOUT_IDS,
    LayoutProfileStore,
    LayoutValidationError,
    slugify_layout_id,
)

_CURATED_PRESETS = (
    "default",
    "executive",
    "meeting_followup",
    "speaker_focus",
    "minimal",
    "developer_debug",
)


@pytest.fixture(autouse=True)
def _registry():
    clear_registry_for_tests()
    register_builtin_blocks()
    yield
    clear_registry_for_tests()


def test_preset_layout_yaml_loads() -> None:
    for layout_id in (*_CURATED_PRESETS, "all"):
        spec = LayoutProfileStore.load_layout(layout_id)
        assert spec.id == layout_id
        assert spec.schema_version == 1
        assert LayoutProfileStore.is_builtin(layout_id)
    default = LayoutProfileStore.load_layout("default")
    assert default.title == "Standard"
    overview_ids = [b.block_id for b in default.pages["overview"].blocks]
    assert overview_ids[0] == "transcript_summary_hero"
    assert "export_panel" not in overview_ids


def test_builtin_layout_ids_match_presets() -> None:
    assert BUILTIN_LAYOUT_IDS == frozenset(
        {
            "default",
            "executive",
            "meeting_followup",
            "speaker_focus",
            "minimal",
            "developer_debug",
            "all",
        }
    )
    listed = LayoutProfileStore.list_layouts()
    for layout_id in BUILTIN_LAYOUT_IDS:
        assert layout_id in listed


def test_curated_presets_insights_sections_are_set() -> None:
    """Shipped YAML presets (except developer_debug / all) tag Insights sections."""
    for layout_id in (
        "default",
        "executive",
        "meeting_followup",
        "speaker_focus",
        "minimal",
    ):
        layout = LayoutProfileStore.load_layout(layout_id)
        insights = layout.pages["insights"].blocks
        assert insights, layout_id
        assert all(b.section for b in insights), layout_id
        assert "charts" in layout.pages


def test_meeting_followup_preset_structure() -> None:
    layout = LayoutProfileStore.load_layout("meeting_followup")
    assert layout.title == "Meeting follow-up"
    overview = [b.block_id for b in layout.pages["overview"].blocks]
    assert overview == [
        "transcript_summary_hero",
        "action_items_compact",
        "highlights_compact",
        "at_a_glance",
        "run_status_compact",
    ]
    insights = layout.pages["insights"].blocks
    assert [b.block_id for b in insights if b.section == "actions"] == [
        "llm_action_items_block",
        "commitments_table",
    ]


def test_speaker_focus_preset_structure() -> None:
    layout = LayoutProfileStore.load_layout("speaker_focus")
    assert layout.title == "Speakers"
    overview = [b.block_id for b in layout.pages["overview"].blocks]
    assert overview[0] == "transcript_summary_hero"
    assert "speaker_summary_cards" in overview
    assert "action_items_compact" not in overview
    speaker_ids = [
        b.block_id for b in layout.pages["insights"].blocks if b.section == "speakers"
    ]
    assert speaker_ids == [
        "llm_speaker_summary_block",
        "lexical_diversity_block",
        "epistemic_markers_block",
        "politeness_block",
        "insights_contract",
    ]


def test_minimal_preset_structure() -> None:
    layout = LayoutProfileStore.load_layout("minimal")
    assert layout.title == "Minimal"
    overview = [b.block_id for b in layout.pages["overview"].blocks]
    assert overview == [
        "transcript_summary_hero",
        "at_a_glance",
        "run_status_compact",
    ]
    insights = [b.block_id for b in layout.pages["insights"].blocks]
    assert insights == ["insights_summary_panel", "highlights"]
    charts = [b.block_id for b in layout.pages["charts"].blocks]
    assert charts == ["chart_overview_slots"]


def test_executive_insights_have_sections() -> None:
    layout = LayoutProfileStore.load_layout("executive")
    by_id = {b.placement_id: b for b in layout.pages["insights"].blocks}
    assert by_id["exec_summary"].section == "summary"
    assert by_id["exec_commitments"].section == "actions"
    assert by_id["exec_action_items"].section == "actions"
    assert by_id["exec_highlights"].section == "highlights"
    assert "charts" in layout.pages


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


def test_param_type_mismatch_fails() -> None:
    bad = {
        "schema_version": 1,
        "id": "param_types",
        "title": "Param types",
        "pages": {
            "insights": {
                "page_id": "insights",
                "blocks": [
                    {
                        "placement_id": "llm1",
                        "block_id": "llm_summary_block",
                        "visible": True,
                        "params": {"title": 42},
                    }
                ],
            }
        },
    }
    with pytest.raises(LayoutValidationError, match="must be type 'string'"):
        LayoutProfileStore.validate_layout_dict(bad)


def test_slugify_layout_id() -> None:
    assert slugify_layout_id("My Layout!") == "My_Layout"
    assert slugify_layout_id("  ok-id_1  ") == "ok-id_1"
    with pytest.raises(LayoutValidationError, match="non-empty"):
        slugify_layout_id("   ")
    with pytest.raises(LayoutValidationError, match="path separators"):
        slugify_layout_id("../escape")
    with pytest.raises(LayoutValidationError, match="path separators"):
        slugify_layout_id("a/b")


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    spec = LayoutProfileStore.load_layout("default")
    path = LayoutProfileStore.save_as_custom(
        spec, "my_custom", title="My Custom", base=tmp_path
    )
    assert path.exists()
    loaded = LayoutProfileStore.load_layout("my_custom", base=tmp_path)
    assert loaded.id == "my_custom"
    assert "overview" in loaded.pages


def test_save_as_custom_overwrite_guard(tmp_path: Path) -> None:
    spec = LayoutProfileStore.load_layout("minimal")
    LayoutProfileStore.save_as_custom(spec, "guarded", base=tmp_path)
    with pytest.raises(LayoutValidationError, match="already exists"):
        LayoutProfileStore.save_as_custom(
            spec, "guarded", base=tmp_path, overwrite=False
        )
    path = LayoutProfileStore.save_as_custom(
        spec, "guarded", title="Replaced", base=tmp_path, overwrite=True
    )
    assert path.exists()
    loaded = LayoutProfileStore.load_layout("guarded", base=tmp_path)
    assert loaded.title == "Replaced"


def test_delete_custom_layout(tmp_path: Path) -> None:
    spec = LayoutProfileStore.load_layout("default")
    LayoutProfileStore.save_as_custom(spec, "to_delete", base=tmp_path)
    path = LayoutProfileStore.delete_custom("to_delete", base=tmp_path)
    assert not path.exists()
    with pytest.raises(FileNotFoundError):
        LayoutProfileStore.delete_custom("to_delete", base=tmp_path)
    with pytest.raises(LayoutValidationError, match="cannot be deleted"):
        LayoutProfileStore.delete_custom("default", base=tmp_path)


def test_cannot_save_as_builtin_id(tmp_path: Path) -> None:
    spec = LayoutProfileStore.load_layout("default")
    with pytest.raises(LayoutValidationError, match="built-in id"):
        LayoutProfileStore.save_as_custom(spec, "meeting_followup", base=tmp_path)


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
