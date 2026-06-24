"""Layout page composer — order-based rendering (Phase 1)."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.rendering import render_block
from transcriptx.web.layouts.specs import LayoutPageSpec, LayoutSpec


def render_layout_page(
    page_id: str,
    ctx: BlockContext,
    layout: LayoutSpec,
) -> None:
    page = layout.pages.get(page_id)
    if page is None:
        st.warning(f"Layout '{layout.id}' has no page '{page_id}'.")
        return
    _render_page_placements(page, ctx)


def _render_page_placements(page: LayoutPageSpec, ctx: BlockContext) -> None:
    for placement in page.blocks:
        if not placement.visible:
            continue
        render_block(placement.block_id, ctx, placement)
