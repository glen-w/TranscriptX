"""Tests for cross-page deep link helpers."""

from __future__ import annotations

from unittest.mock import patch

import streamlit as st

from transcriptx.web.navigation import (
    navigate_to_charts,
    navigate_to_data_artifact,
    navigate_to_speaker_profile,
)


@patch("streamlit.rerun")
def test_navigate_to_charts_sets_page_and_module(mock_rerun) -> None:
    st.session_state.clear()
    navigate_to_charts(module="sentiment")
    assert st.session_state["page"] == "Charts"
    assert st.session_state["filter_module"] == "sentiment"
    mock_rerun.assert_called_once()


@patch("streamlit.rerun")
def test_navigate_to_data_artifact_preset(mock_rerun) -> None:
    st.session_state.clear()
    navigate_to_data_artifact(artifact_id="art_123")
    assert st.session_state["page"] == "Artifacts"
    assert st.session_state["artifacts_section"] == "Preview"
    assert st.session_state["data_artifact_preset"] == "art_123"
    assert st.session_state["artifacts_preview_id"] == "art_123"
    # Widget keys must be synced so segmented_control/selectbox do not clobber.
    assert st.session_state["artifacts_section_control"] == "Preview"
    assert st.session_state["artifacts_section_radio"] == "Preview"
    assert st.session_state["artifacts_preview_selector"] == "art_123"
    mock_rerun.assert_called_once()


@patch("streamlit.rerun")
def test_navigate_to_speaker_profile_presets_speakers_page(mock_rerun) -> None:
    st.session_state.clear()
    navigate_to_speaker_profile("prof_abc")
    assert st.session_state["page"] == "Speakers"
    assert st.session_state["speakers_selected_profile"] == "prof_abc"
    mock_rerun.assert_called_once()
