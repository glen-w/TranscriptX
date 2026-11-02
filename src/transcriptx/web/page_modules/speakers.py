"""Speakers directory + detail for longitudinal speaker profiles.

Implementation lives in ``transcriptx.web.ui.speakers``. This module re-exports
the page entry point and names tests patch.
"""

from __future__ import annotations

import streamlit as st

from transcriptx.core.speaker_profiles.layout import (
    links_dir,
    profiles_dir,
    speaker_profiles_dir,
)
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.snapshot import build_aggregation_snapshot
from transcriptx.core.speaker_profiles.store_io import ensure_layout
from transcriptx.core.utils.paths import PATHS
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.ui.speakers.charts import (
    _build_locations_folium_html,
    _mention_label,
    _render_detail_charts,
    _render_interactions_equity,
    _render_locations_map,
    _render_sentiment_trends,
    _series_points_frame,
)
from transcriptx.web.ui.speakers.detail import (
    _render_profile_detail,
    _render_voice_controls,
)
from transcriptx.web.ui.speakers.directory import (
    _render_directory_overview,
    _render_merged_readonly,
    _speakers_browser_fragment,
    render_speakers_page,
)
from transcriptx.web.ui.speakers.forms import (
    _open_transcript,
    _render_appearances_table,
    _render_edit_form,
    _render_lifecycle,
    _render_link_another,
)
from transcriptx.web.ui.speakers.support import (
    _SPEAKERS_DESCRIPTION,
    _appearance_samples,
    _clear_idempotency,
    _directory_chart_frame,
    _evidence_caption,
    _gallery_meta,
    _get_speakers_aggregation_snapshot,
    _idempotency_key,
    _info_tooltip_html,
    _item_matches_search,
    _methodology_info_html,
    _methodology_lines,
    _payload_digest,
    _profiles_store_fingerprint,
    _render_recovery_banners,
    _rerun_ui,
    _section_heading_with_info_html,
    _service,
    _surname_sort_key,
)

__all__ = [
    "PATHS",
    "ManagedTranscriptResolver",
    "build_aggregation_snapshot",
    "ensure_layout",
    "links_dir",
    "profiles_dir",
    "render_page_shell",
    "render_speakers_page",
    "speaker_profiles_dir",
    "st",
    "_SPEAKERS_DESCRIPTION",
    "_appearance_samples",
    "_build_locations_folium_html",
    "_clear_idempotency",
    "_directory_chart_frame",
    "_evidence_caption",
    "_gallery_meta",
    "_get_speakers_aggregation_snapshot",
    "_idempotency_key",
    "_info_tooltip_html",
    "_item_matches_search",
    "_mention_label",
    "_methodology_info_html",
    "_methodology_lines",
    "_open_transcript",
    "_payload_digest",
    "_profiles_store_fingerprint",
    "_render_appearances_table",
    "_render_detail_charts",
    "_render_directory_overview",
    "_render_edit_form",
    "_render_interactions_equity",
    "_render_lifecycle",
    "_render_link_another",
    "_render_locations_map",
    "_render_merged_readonly",
    "_render_profile_detail",
    "_render_recovery_banners",
    "_render_sentiment_trends",
    "_render_voice_controls",
    "_rerun_ui",
    "_section_heading_with_info_html",
    "_series_points_frame",
    "_service",
    "_speakers_browser_fragment",
    "_surname_sort_key",
]
