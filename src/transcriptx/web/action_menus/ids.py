"""Typed identifiers for configurable action menus."""

from __future__ import annotations

from enum import Enum


class SectionId(str, Enum):
    HOME_RECENT_RUNS = "home_recent_runs"
    LIBRARY_SELECTED = "library_selected"
    IMPORT_SUCCESS = "import_success"
    SPEAKER_ID_COMPLETE = "speaker_id_complete"
    RUN_ANALYSIS_COMPLETE = "run_analysis_complete"


class ActionId(str, Enum):
    OPEN = "open"
    OPEN_LIBRARY = "open_library"
    OPEN_TRANSCRIPT = "open_transcript"
    CHARTS = "charts"
    ARTIFACTS = "artifacts"
    INSIGHTS = "insights"
    EXPORT_ZIP = "export_zip"
    RENAME = "rename"
    RUN_SPEAKER_ID = "run_speaker_id"
    RUN_ANALYSIS = "run_analysis"
    CORRECTIONS = "corrections"


class NavStyle(str, Enum):
    ON_CLICK = "on_click"
    CLICK_RERUN = "click_rerun"


class StandardMenuMode(str, Enum):
    BUILT_IN = "built_in"
    CUSTOM = "custom"


class SectionMenuMode(str, Enum):
    USE_STANDARD = "use_standard"
    SECTION_DEFAULT = "section_default"
    MANUAL = "manual"


SECTION_ORDER: tuple[SectionId, ...] = tuple(SectionId)
ACTION_ORDER: tuple[ActionId, ...] = tuple(ActionId)

SECTION_LABELS: dict[SectionId, str] = {
    SectionId.HOME_RECENT_RUNS: "Home — recent runs",
    SectionId.LIBRARY_SELECTED: "Library — selected transcript",
    SectionId.IMPORT_SUCCESS: "Import — after success",
    SectionId.SPEAKER_ID_COMPLETE: "Speaker ID — after completion",
    SectionId.RUN_ANALYSIS_COMPLETE: "Run Analysis — after completion",
}
