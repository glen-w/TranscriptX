"""Insights facade re-exports slice implementations (split identity)."""

from __future__ import annotations

import pytest

from transcriptx.web.blocks.implementations import insights as facade
from transcriptx.web.blocks.implementations import insights_contract
from transcriptx.web.blocks.implementations import insights_highlights
from transcriptx.web.blocks.implementations import insights_llm
from transcriptx.web.blocks.implementations import insights_markers
from transcriptx.web.blocks.implementations import insights_support


@pytest.mark.unit
def test_insights_facade_reexports_slice_renderers() -> None:
    assert facade.render_insights_contract is insights_contract.render_insights_contract
    assert facade.render_highlights is insights_highlights.render_highlights
    assert facade.render_llm_summary_block is insights_llm.render_llm_summary_block
    assert facade.render_keyphrases_block is insights_markers.render_keyphrases_block
    assert facade._loader is insights_support._loader
    assert facade._render_highlight_card is insights_highlights._render_highlight_card


@pytest.mark.unit
def test_builtin_insights_blocks_bind_facade_renderers() -> None:
    from transcriptx.web.blocks.builtin import register_builtin_blocks
    from transcriptx.web.blocks.registry import get_block

    register_builtin_blocks()
    assert get_block("insights_contract").render is facade.render_insights_contract
    assert get_block("highlights").render is facade.render_highlights
    assert get_block("keyphrases_block").render is facade.render_keyphrases_block
