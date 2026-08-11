"""Action catalogue: labels, icons, help, allowlists, and built-in defaults."""

from __future__ import annotations

from dataclasses import dataclass

from transcriptx.web.action_menus.ids import ActionId, SectionId


@dataclass(frozen=True)
class ActionDef:
    id: ActionId
    label: str
    icon: str
    help: str


# Catalogue order is the canonical render / checkbox order.
ACTIONS: tuple[ActionDef, ...] = (
    ActionDef(
        ActionId.OPEN,
        "Open",
        ":material/folder_open:",
        "Open Overview for the selected subject (works with a transcript even when no analysis run exists).",
    ),
    ActionDef(
        ActionId.OPEN_LIBRARY,
        "Open Library",
        ":material/folder_open:",
        "Open the Library focused on this transcript.",
    ),
    ActionDef(
        ActionId.OPEN_TRANSCRIPT,
        "Transcript",
        ":material/description:",
        "Open the Transcript viewer for the selected transcript.",
    ),
    ActionDef(
        ActionId.CHARTS,
        "Charts",
        ":material/bar_chart:",
        "Open Charts for a completed analysis run.",
    ),
    ActionDef(
        ActionId.ARTIFACTS,
        "Artifacts",
        ":material/inventory_2:",
        "Open Artifacts (data) for a completed analysis run.",
    ),
    ActionDef(
        ActionId.INSIGHTS,
        "Insights",
        ":material/lightbulb:",
        "Open Insights for a completed compatible analysis run.",
    ),
    ActionDef(
        ActionId.EXPORT_ZIP,
        "Export ZIP",
        ":material/folder_zip:",
        "Build and download a ZIP of run artifacts (requires a valid analysis run).",
    ),
    ActionDef(
        ActionId.RENAME,
        "Rename",
        ":material/drive_file_rename_outline:",
        "Rename the transcript (and linked audio) on the Rename Transcript page.",
    ),
    ActionDef(
        ActionId.RUN_SPEAKER_ID,
        "Run Speaker ID",
        ":material/record_voice_over:",
        "Go to Speaker Identification for this transcript.",
    ),
    ActionDef(
        ActionId.RUN_ANALYSIS,
        "Run Analysis",
        ":material/analytics:",
        "Go to Run Analysis for this subject.",
    ),
    ActionDef(
        ActionId.CORRECTIONS,
        "Corrections Studio",
        ":material/edit_note:",
        "Open Corrections Studio for this transcript (requires a usable corrections workspace).",
    ),
    ActionDef(
        ActionId.CORRECT_IN_VIEWER,
        "Correct in viewer",
        ":material/spellcheck:",
        "Open the Transcript viewer in Correct mode to propose word-level fixes while reading.",
    ),
)

ACTIONS_BY_ID: dict[ActionId, ActionDef] = {a.id: a for a in ACTIONS}

OPTIONAL_ACTIONS: frozenset[ActionId] = frozenset(
    {
        ActionId.OPEN_TRANSCRIPT,
        ActionId.INSIGHTS,
        ActionId.CORRECTIONS,
        ActionId.CORRECT_IN_VIEWER,
    }
)

SECTION_ALLOWLISTS: dict[SectionId, tuple[ActionId, ...]] = {
    SectionId.HOME_RECENT_RUNS: (
        ActionId.OPEN,
        ActionId.CHARTS,
        ActionId.ARTIFACTS,
        ActionId.EXPORT_ZIP,
        ActionId.RENAME,
        ActionId.OPEN_TRANSCRIPT,
        ActionId.INSIGHTS,
        ActionId.CORRECTIONS,
        ActionId.CORRECT_IN_VIEWER,
    ),
    SectionId.LIBRARY_SELECTED: (
        ActionId.RUN_SPEAKER_ID,
        ActionId.RUN_ANALYSIS,
        ActionId.OPEN_TRANSCRIPT,
        ActionId.CORRECTIONS,
        ActionId.CORRECT_IN_VIEWER,
        ActionId.RENAME,
    ),
    SectionId.IMPORT_SUCCESS: (
        ActionId.OPEN_LIBRARY,
        ActionId.RUN_ANALYSIS,
        ActionId.RUN_SPEAKER_ID,
        ActionId.OPEN_TRANSCRIPT,
        ActionId.CORRECTIONS,
        ActionId.CORRECT_IN_VIEWER,
    ),
    SectionId.SPEAKER_ID_COMPLETE: (
        ActionId.OPEN,
        ActionId.CHARTS,
        ActionId.ARTIFACTS,
        ActionId.EXPORT_ZIP,
        ActionId.RENAME,
        ActionId.RUN_ANALYSIS,
        ActionId.OPEN_TRANSCRIPT,
        ActionId.INSIGHTS,
        ActionId.CORRECTIONS,
        ActionId.CORRECT_IN_VIEWER,
    ),
    SectionId.RUN_ANALYSIS_COMPLETE: (
        ActionId.OPEN,
        ActionId.CHARTS,
        ActionId.ARTIFACTS,
        ActionId.EXPORT_ZIP,
        ActionId.RENAME,
        ActionId.OPEN_TRANSCRIPT,
        ActionId.INSIGHTS,
        ActionId.CORRECTIONS,
        ActionId.CORRECT_IN_VIEWER,
    ),
}

HOME_STRIP: tuple[ActionId, ...] = (
    ActionId.OPEN,
    ActionId.CHARTS,
    ActionId.ARTIFACTS,
    ActionId.EXPORT_ZIP,
    ActionId.RENAME,
)

BUILT_IN_STANDARD_MENU: tuple[ActionId, ...] = HOME_STRIP


@dataclass(frozen=True)
class SectionDefaultKey:
    """Documented context variant for a section's built-in default."""

    section: SectionId
    subject_type: str  # "transcript" | "group" | "any"
    has_run: bool | None  # None = either


SECTION_DEFAULTS: dict[SectionDefaultKey, tuple[ActionId, ...]] = {
    SectionDefaultKey(SectionId.HOME_RECENT_RUNS, "transcript", True): HOME_STRIP,
    SectionDefaultKey(SectionId.LIBRARY_SELECTED, "transcript", None): (
        ActionId.RUN_SPEAKER_ID,
        ActionId.RUN_ANALYSIS,
    ),
    SectionDefaultKey(SectionId.IMPORT_SUCCESS, "transcript", None): (
        ActionId.OPEN_LIBRARY,
        ActionId.RUN_ANALYSIS,
        ActionId.RUN_SPEAKER_ID,
    ),
    SectionDefaultKey(SectionId.SPEAKER_ID_COMPLETE, "transcript", True): HOME_STRIP,
    SectionDefaultKey(SectionId.SPEAKER_ID_COMPLETE, "transcript", False): (
        ActionId.OPEN,
        ActionId.RUN_ANALYSIS,
        ActionId.RENAME,
    ),
    SectionDefaultKey(SectionId.RUN_ANALYSIS_COMPLETE, "transcript", True): HOME_STRIP,
    SectionDefaultKey(SectionId.RUN_ANALYSIS_COMPLETE, "group", True): (
        ActionId.OPEN,
        ActionId.CHARTS,
        ActionId.ARTIFACTS,
    ),
}


def section_default_actions(
    section: SectionId, *, subject_type: str, has_run: bool
) -> tuple[ActionId, ...]:
    """Return the built-in default strip for a section context variant."""
    exact = SectionDefaultKey(section, subject_type, has_run)
    if exact in SECTION_DEFAULTS:
        return SECTION_DEFAULTS[exact]
    either = SectionDefaultKey(section, subject_type, None)
    if either in SECTION_DEFAULTS:
        return SECTION_DEFAULTS[either]
    any_key = SectionDefaultKey(section, "any", has_run)
    if any_key in SECTION_DEFAULTS:
        return SECTION_DEFAULTS[any_key]
    # Fallback should never hit if catalogue invariants hold.
    return SECTION_ALLOWLISTS[section][:1]


def label_for(action: ActionId, section: SectionId | None = None) -> str:
    """Resolve display label (section overrides reserved for future use)."""
    _ = section
    return ACTIONS_BY_ID[action].label


def icon_for(action: ActionId) -> str:
    return ACTIONS_BY_ID[action].icon


def help_for(action: ActionId) -> str:
    return ACTIONS_BY_ID[action].help
