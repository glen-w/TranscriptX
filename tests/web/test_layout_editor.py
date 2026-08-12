"""Unit tests for Dashboard Builder layout editor helpers."""

from __future__ import annotations

from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.layouts.store import LayoutProfileStore
from transcriptx.web.ui.dashboard_builder.layout_editor import (
    EditedPlacement,
    apply_page_placements,
    layout_to_edited_pages,
    move_placement,
    move_placement_in_view,
    new_placement_id,
    placements_for_view,
)


def test_layout_to_edited_pages_and_apply_roundtrip() -> None:
    register_builtin_blocks()
    layout = LayoutProfileStore.load_layout("minimal")
    edited = layout_to_edited_pages(layout)
    assert "overview" in edited
    assert "insights" in edited
    assert edited["overview"]
    rebuilt = apply_page_placements(layout, edited)
    assert [
        (b.placement_id, b.block_id, b.visible)
        for b in rebuilt.pages["overview"].blocks
    ] == [
        (b.placement_id, b.block_id, b.visible)
        for b in layout.pages["overview"].blocks
    ]


def test_new_placement_id_avoids_collisions() -> None:
    existing = [
        EditedPlacement(placement_id="overview_at_a_glance", block_id="at_a_glance"),
    ]
    assert new_placement_id("overview", "hero", existing) == "overview_hero"
    assert (
        new_placement_id("overview", "at_a_glance", existing)
        == "overview_at_a_glance_2"
    )


def test_move_placement_swaps_neighbors() -> None:
    rows = [
        EditedPlacement(placement_id="a", block_id="a"),
        EditedPlacement(placement_id="b", block_id="b"),
        EditedPlacement(placement_id="c", block_id="c"),
    ]
    moved = move_placement(rows, 1, -1)
    assert [r.placement_id for r in moved] == ["b", "a", "c"]
    unchanged = move_placement(rows, 0, -1)
    assert [r.placement_id for r in unchanged] == ["a", "b", "c"]


def test_move_placement_in_view_respects_insights_section() -> None:
    rows = [
        EditedPlacement(placement_id="s1", block_id="a", section="summary"),
        EditedPlacement(placement_id="sp1", block_id="b", section="speakers"),
        EditedPlacement(placement_id="s2", block_id="c", section="summary"),
    ]
    view = placements_for_view(rows, page_id="insights", section="summary")
    assert [r.placement_id for _, r in view] == ["s1", "s2"]
    moved = move_placement_in_view(
        rows, page_id="insights", section="summary", view_index=0, delta=1
    )
    assert [r.placement_id for r in moved] == ["s2", "sp1", "s1"]
    summary_order = [
        r.placement_id for r in moved if (r.section or "summary") == "summary"
    ]
    assert summary_order == ["s2", "s1"]
