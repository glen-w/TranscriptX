"""Route migration and Artifacts navigation contracts."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.navigation import (
    migrate_legacy_page_key,
    pages_in_section,
)
from transcriptx.web.page_modules.artifacts import (
    _force_preview_section,
    _open_artifact_preview,
)
from transcriptx.web.state import (
    ARTIFACTS_KEY_PREVIEW_ID,
    ARTIFACTS_KEY_SECTION,
    ARTIFACTS_KEY_SELECTED_IDS,
    ARTIFACTS_KEY_SCOPE,
    ARTIFACTS_KEY_SHOW_MORE,
    DATA_KEY_ARTIFACT_PRESET,
    consume_artifact_preset,
    reconcile_artifact_selection,
)


def test_legacy_data_and_explorer_aliases_removed() -> None:
    # Data / Explorer no longer migrate (0.9.7); Statistics still maps to Home.
    assert migrate_legacy_page_key("Data") == ("Data", None)
    assert migrate_legacy_page_key("Explorer") == ("Explorer", None)
    assert migrate_legacy_page_key("Statistics") == ("Home", None)
    assert migrate_legacy_page_key("Overview") == ("Overview", None)
    # Batch Ops must NOT migrate here — router applies Batch target first.
    assert migrate_legacy_page_key("Batch Ops") == ("Batch Ops", None)


def test_workflow_section_excludes_legacy_batch_ops() -> None:
    keys = [s.key for s in pages_in_section("workflow")]
    assert "Run Analysis" in keys
    assert "Batch Ops" not in keys
    assert "Groups" not in keys
    assert "Speakers" not in keys


def test_primary_section_places_speakers_and_groups_under_search() -> None:
    keys = [s.key for s in pages_in_section("primary")]
    assert keys.index("Search") < keys.index("Speakers")
    assert keys.index("Speakers") < keys.index("Groups")


def test_view_section_excludes_legacy_and_includes_artifacts() -> None:
    keys = [s.key for s in pages_in_section("view")]
    assert "Artifacts" in keys
    assert "Data" not in keys
    assert "Explorer" not in keys
    # Order: ... Overview, Transcript, Insights, Charts, Artifacts, Performance
    assert keys.index("Overview") < keys.index("Transcript")
    assert keys.index("Transcript") < keys.index("Insights")
    assert keys.index("Insights") < keys.index("Charts")
    assert keys.index("Charts") < keys.index("Artifacts")
    assert keys.index("Artifacts") < keys.index("Performance")


def test_artifact_selection_cleared_on_run_change() -> None:
    ss: dict = {
        ARTIFACTS_KEY_SCOPE: ("transcript", "a", "run1"),
        ARTIFACTS_KEY_SELECTED_IDS: ["x", "y"],
    }
    reconcile_artifact_selection(
        ss, subject_type="transcript", subject_id="a", run_id="run2"
    )
    assert ss[ARTIFACTS_KEY_SELECTED_IDS] == []
    assert ss[ARTIFACTS_KEY_SCOPE] == ("transcript", "a", "run2")


def test_consume_artifact_preset_and_same_scope_keeps_selection() -> None:
    ss: dict = {
        ARTIFACTS_KEY_SCOPE: ("transcript", "a", "run1"),
        ARTIFACTS_KEY_SELECTED_IDS: ["keep"],
        ARTIFACTS_KEY_PREVIEW_ID: "keep",
        ARTIFACTS_KEY_SHOW_MORE: "stats",
        DATA_KEY_ARTIFACT_PRESET: "Preview",
    }
    reconcile_artifact_selection(
        ss, subject_type="transcript", subject_id="a", run_id="run1"
    )
    assert ss[ARTIFACTS_KEY_SELECTED_IDS] == ["keep"]
    assert ss[ARTIFACTS_KEY_PREVIEW_ID] == "keep"
    assert consume_artifact_preset(ss) == "Preview"
    assert DATA_KEY_ARTIFACT_PRESET not in ss
    assert consume_artifact_preset(ss) is None


def test_open_artifact_preview_syncs_widget_keys() -> None:
    """Direct open (pre-widget) must update keyed widgets or nav stays on Browse."""
    st.session_state.clear()
    st.session_state["artifacts_section_control"] = "Browse"
    st.session_state[ARTIFACTS_KEY_SECTION] = "Browse"

    _open_artifact_preview("art_abc")

    assert st.session_state[ARTIFACTS_KEY_SECTION] == "Preview"
    assert st.session_state[ARTIFACTS_KEY_PREVIEW_ID] == "art_abc"
    assert st.session_state["artifacts_section_control"] == "Preview"
    assert st.session_state["artifacts_section_radio"] == "Preview"
    assert st.session_state["artifacts_preview_selector"] == "art_abc"
    assert "_artifacts_force_preview" not in st.session_state


def test_open_artifact_preview_defers_widgets_after_nav_instantiated() -> None:
    """Browse→Preview cannot write widget keys mid-run; force flag defers sync."""
    st.session_state.clear()
    st.session_state["artifacts_section_control"] = "Browse"
    st.session_state[ARTIFACTS_KEY_SECTION] = "Browse"

    _open_artifact_preview("art_abc", defer_widgets=True)

    assert st.session_state[ARTIFACTS_KEY_SECTION] == "Preview"
    assert st.session_state[ARTIFACTS_KEY_PREVIEW_ID] == "art_abc"
    assert st.session_state["_artifacts_force_preview"] is True
    # Stale widget value left alone until _force_preview_section on next run.
    assert st.session_state["artifacts_section_control"] == "Browse"


def test_force_preview_section_overrides_stale_control() -> None:
    st.session_state.clear()
    st.session_state["artifacts_section_control"] = "Browse"
    st.session_state[ARTIFACTS_KEY_SECTION] = "Browse"
    st.session_state[DATA_KEY_ARTIFACT_PRESET] = "art_deep"
    st.session_state["_artifacts_force_preview"] = True

    _force_preview_section()

    assert st.session_state[ARTIFACTS_KEY_SECTION] == "Preview"
    assert st.session_state["artifacts_section_control"] == "Preview"
    assert st.session_state["artifacts_preview_selector"] == "art_deep"
    assert "_artifacts_force_preview" not in st.session_state


def test_force_preview_section_applies_deferred_browse_jump() -> None:
    st.session_state.clear()
    st.session_state["artifacts_section_control"] = "Browse"
    _open_artifact_preview("art_from_browse", defer_widgets=True)

    _force_preview_section()

    assert st.session_state[ARTIFACTS_KEY_SECTION] == "Preview"
    assert st.session_state["artifacts_section_control"] == "Preview"
    assert st.session_state["artifacts_preview_selector"] == "art_from_browse"
    assert "_artifacts_force_preview" not in st.session_state
