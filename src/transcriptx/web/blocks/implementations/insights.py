"""Insights page blocks — adapted from page_modules/insights.py.

Implementation lives in ``insights_support``, ``insights_contract``,
``insights_highlights``, ``insights_llm``, and ``insights_markers``.
This module re-exports the public (and test-imported private) names.
"""

from __future__ import annotations

import streamlit as st

from transcriptx.web.blocks.implementations.insights_support import (
    _load_analysis_json,
    _loader,
    _module_failure_hint,
    _render_open_in_transcript_button,
    _render_quiet_module_empty,
    _render_view_raw_file_link,
    _segment_index_from_refs,
)
from transcriptx.web.blocks.implementations.insights_contract import (
    _insights_contract_title,
    _insights_focus,
    _quote_text_by_id,
    _render_insight_rows_rollup,
    _render_insights_narrative,
    _render_insights_payload,
    _render_style_indicator_list,
    _render_theme_and_idea_lists,
    _style_detail_rows,
    render_insights_contract,
)
from transcriptx.web.blocks.implementations.insights_highlights import (
    _collect_highlight_cards,
    _highlights_audio_available,
    _highlights_browser_fragment,
    _highlights_theme_visible,
    _render_highlight_card,
    _render_highlight_rows_rollup,
    _section_display_label,
    render_highlights,
)
from transcriptx.web.blocks.implementations.insights_llm import (
    _render_action_item_rows_rollup,
    _render_action_items_payload,
    _render_commitments_from_summary,
    _render_executive_summary_body,
    _safe_speaker_artifact_token,
    render_commitments_table,
    render_executive_summary,
    render_llm_action_items_block,
    render_llm_speaker_summary_block,
    render_llm_summary_block,
)
from transcriptx.web.blocks.implementations.insights_markers import (
    _analysis_module_heading,
    _render_keyphrases_payload,
    _render_lexical_diversity_payload,
    _render_marker_module_block,
    _render_marker_module_payload,
    render_epistemic_markers_block,
    render_keyphrases_block,
    render_lexical_diversity_block,
    render_politeness_block,
)

__all__ = [
    "st",
    "_analysis_module_heading",
    "_collect_highlight_cards",
    "_highlights_audio_available",
    "_highlights_browser_fragment",
    "_highlights_theme_visible",
    "_insights_contract_title",
    "_insights_focus",
    "_load_analysis_json",
    "_loader",
    "_module_failure_hint",
    "_quote_text_by_id",
    "_render_action_item_rows_rollup",
    "_render_action_items_payload",
    "_render_commitments_from_summary",
    "_render_executive_summary_body",
    "_render_highlight_card",
    "_render_highlight_rows_rollup",
    "_render_insight_rows_rollup",
    "_render_insights_narrative",
    "_render_insights_payload",
    "_render_keyphrases_payload",
    "_render_lexical_diversity_payload",
    "_render_marker_module_block",
    "_render_marker_module_payload",
    "_render_open_in_transcript_button",
    "_render_quiet_module_empty",
    "_render_style_indicator_list",
    "_render_theme_and_idea_lists",
    "_render_view_raw_file_link",
    "_safe_speaker_artifact_token",
    "_section_display_label",
    "_segment_index_from_refs",
    "_style_detail_rows",
    "render_commitments_table",
    "render_epistemic_markers_block",
    "render_executive_summary",
    "render_highlights",
    "render_insights_contract",
    "render_keyphrases_block",
    "render_lexical_diversity_block",
    "render_llm_action_items_block",
    "render_llm_speaker_summary_block",
    "render_llm_summary_block",
    "render_politeness_block",
]
