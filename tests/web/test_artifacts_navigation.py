"""Route migration and Artifacts navigation contracts."""

from __future__ import annotations

from transcriptx.web.navigation import (
    migrate_legacy_page_key,
    pages_in_section,
)
from transcriptx.web.state import (
    ARTIFACTS_KEY_PREVIEW_ID,
    ARTIFACTS_KEY_SELECTED_IDS,
    ARTIFACTS_KEY_SCOPE,
    ARTIFACTS_KEY_SHOW_MORE,
    DATA_KEY_ARTIFACT_PRESET,
    consume_artifact_preset,
    reconcile_artifact_selection,
)


def test_legacy_data_and_explorer_redirect_map() -> None:
    assert migrate_legacy_page_key("Data") == ("Artifacts", "Preview")
    assert migrate_legacy_page_key("Explorer") == ("Artifacts", "Browse")
    assert migrate_legacy_page_key("Overview") == ("Overview", None)


def test_view_section_excludes_legacy_and_includes_artifacts() -> None:
    keys = [s.key for s in pages_in_section("view")]
    assert "Artifacts" in keys
    assert "Data" not in keys
    assert "Explorer" not in keys
    # Order: ... Transcript, Overview, Insights, Charts, Artifacts
    assert keys.index("Transcript") < keys.index("Overview")
    assert keys.index("Overview") < keys.index("Insights")
    assert keys.index("Insights") < keys.index("Charts")
    assert keys.index("Charts") < keys.index("Artifacts")


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
