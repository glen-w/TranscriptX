"""Tests for layout page composer."""

from __future__ import annotations

from pathlib import Path

from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.blocks.composer import render_layout_page
from transcriptx.web.blocks.context import build_block_context
from transcriptx.web.blocks.registry import clear_registry_for_tests
from transcriptx.web.layouts.store import LayoutProfileStore


def test_render_layout_page_invokes_blocks(monkeypatch) -> None:
    clear_registry_for_tests()
    register_builtin_blocks()
    rendered: list[str] = []

    import transcriptx.web.blocks.composer as composer_mod

    def _fake_render(block_id, ctx, placement):
        rendered.append(block_id)

    monkeypatch.setattr(composer_mod, "render_block", _fake_render)
    layout = LayoutProfileStore.load_layout("default")
    ctx = build_block_context(
        run_root=Path("/tmp/run"),
        subject_type="transcript",
        subject_id="slug",
        run_id="run1",
        session_name="slug/run1",
        artifacts=(),
        run_results=None,
        layout_profile_id="default",
        health={"status": "ok"},
    )
    render_layout_page("overview", ctx, layout)
    assert "run_health" in rendered
    assert "export_panel" in rendered
