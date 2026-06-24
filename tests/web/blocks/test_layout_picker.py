"""Tests for layout profile picker."""

from __future__ import annotations

from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.blocks.layout_picker import _available_layout_ids
from transcriptx.web.blocks.registry import clear_registry_for_tests
from transcriptx.web.blocks.session_context import (
    active_layout_id,
    set_active_layout_id,
)
from transcriptx.web.layouts.store import LayoutProfileStore


def test_available_layout_ids_hides_debug_by_default() -> None:
    ids = _available_layout_ids(include_debug=False)
    assert "default" in ids
    assert "executive" in ids
    assert "developer_debug" not in ids


def test_executive_layout_insights_order() -> None:
    clear_registry_for_tests()
    register_builtin_blocks()
    layout = LayoutProfileStore.load_layout("executive")
    block_ids = [b.block_id for b in layout.pages["insights"].blocks]
    assert block_ids.index("executive_summary") < block_ids.index("highlights")
    assert "llm_summary_block" not in block_ids


def test_set_active_layout_id_updates_session() -> None:
    state: dict = {}
    set_active_layout_id("executive", state)
    assert active_layout_id(state) == "executive"
