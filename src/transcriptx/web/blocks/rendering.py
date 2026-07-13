"""Block rendering orchestration."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.blocks.availability import check_block_availability
from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.blocks.registry import get_block


def render_unavailable_placeholder(title: str, reason: str | None) -> None:
    st.caption(title)
    st.info(reason or "This block is not available for the current run.")


def render_block(
    block_id: str,
    ctx: BlockContext,
    placement: BlockPlacement,
) -> None:
    if not placement.visible:
        return
    spec = get_block(block_id)
    if spec is None:
        render_unavailable_placeholder(block_id, f"Unknown block: {block_id}")
        return
    availability = check_block_availability(
        spec, ctx, placement_params=placement.params
    )
    if not availability.available:
        title = placement.title_override or spec.title
        render_unavailable_placeholder(title, availability.reason)
        return
    if spec.render is None:
        return
    spec.render(ctx, placement)
