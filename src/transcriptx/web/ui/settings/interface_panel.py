"""Settings Interface tab: draft-backed action menu customisation.

Widget interactions run in ``@st.fragment`` so checkbox / mode toggles do not
trigger a full-app rerun (avoids the dimming overlay on each click). Save,
Restore, and Reload still call ``st.rerun()`` for a full commit refresh.

Draft→widget hydrate runs only before keyed widgets instantiate (first load or
a deferred pending-sync flag). Mid-script writes after Save/Restore/Reload
would raise Streamlit's "cannot be modified after the widget is instantiated".
"""

from __future__ import annotations

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.web.action_menus.catalog import (
    ACTIONS,
    SECTION_ALLOWLISTS,
    section_default_actions,
)
from transcriptx.web.action_menus.ids import (
    SECTION_LABELS,
    SECTION_ORDER,
    ActionDisplay,
    ActionDisplaySetting,
    ActionId,
    SectionId,
)
from transcriptx.web.action_menus.prefs import (
    DRAFT_SESSION_KEY,
    get_or_hydrate_draft,
    reload_draft_from_disk,
    replace_with_built_in_defaults,
    reset_draft_to_built_ins,
    save_interface_prefs,
    validate_draft_for_save,
)
from transcriptx.web.components.info_tooltip import widget_help

_MODE_LABELS = {
    "use_standard": "Use standard menu",
    "section_default": "Use built-in section default",
    "manual": "Choose actions manually",
}
_MODE_OPTIONS = list(_MODE_LABELS.keys())
_DISPLAY_LABELS = {
    ActionDisplay.BOTH.value: "Icon and text",
    ActionDisplay.ICON.value: "Icon only",
    ActionDisplay.TEXT.value: "Text only",
}
_DISPLAY_OPTIONS = [
    ActionDisplay.BOTH.value,
    ActionDisplay.ICON.value,
    ActionDisplay.TEXT.value,
]
_SECTION_DISPLAY_LABELS = {
    ActionDisplaySetting.INHERIT.value: "Use global default",
    **_DISPLAY_LABELS,
}
_SECTION_DISPLAY_OPTIONS = [
    ActionDisplaySetting.INHERIT.value,
    *_DISPLAY_OPTIONS,
]
# Mid-script Save/Restore/Reload must not write keyed widget values after those
# widgets instantiate — defer hydrate to the start of the next run.
_PENDING_WIDGET_SYNC_KEY = "iface_pending_widget_sync"


def _sync_widgets_from_draft() -> None:
    """Push draft model into Streamlit widget keys (controlled hydrate)."""
    draft = st.session_state[DRAFT_SESSION_KEY]
    prefs = draft.prefs
    st.session_state["iface_show_info_tooltips"] = bool(prefs.show_info_tooltips)
    st.session_state["iface_action_display"] = (
        prefs.action_display
        if prefs.action_display in _DISPLAY_OPTIONS
        else ActionDisplay.BOTH.value
    )
    st.session_state["iface_std_mode"] = (
        "Built-in" if prefs.standard_menu_mode == "built_in" else "Custom"
    )
    for action in ACTIONS:
        st.session_state[f"iface_std_{action.id.value}"] = (
            action.id in prefs.standard_menu
        )
    for sid in SECTION_ORDER:
        sec = prefs.sections[sid]
        st.session_state[f"iface_show_{sid.value}"] = sec.show_menu
        st.session_state[f"iface_mode_{sid.value}"] = sec.mode
        st.session_state[f"iface_display_{sid.value}"] = (
            sec.action_display
            if sec.action_display in _SECTION_DISPLAY_OPTIONS
            else ActionDisplaySetting.INHERIT.value
        )
        allow = SECTION_ALLOWLISTS[sid]
        for action_id in allow:
            st.session_state[f"iface_sel_{sid.value}_{action_id.value}"] = (
                action_id in sec.selected
            )


def _request_widget_sync() -> None:
    """Schedule draft→widget hydrate before widgets exist on the next run."""
    st.session_state[_PENDING_WIDGET_SYNC_KEY] = True


def _pull_widgets_into_draft() -> None:
    draft = st.session_state[DRAFT_SESSION_KEY]
    prefs = draft.prefs
    prefs.show_info_tooltips = bool(
        st.session_state.get("iface_show_info_tooltips", True)
    )
    global_display = st.session_state.get(
        "iface_action_display", ActionDisplay.BOTH.value
    )
    if global_display not in _DISPLAY_OPTIONS:
        global_display = ActionDisplay.BOTH.value
    prefs.action_display = global_display  # type: ignore[assignment]
    std_mode = st.session_state.get("iface_std_mode", "Built-in")
    prefs.standard_menu_mode = "built_in" if std_mode == "Built-in" else "custom"
    selected_std: list[ActionId] = []
    for action in ACTIONS:
        if st.session_state.get(f"iface_std_{action.id.value}", False):
            selected_std.append(action.id)
    prefs.standard_menu = selected_std

    for sid in SECTION_ORDER:
        sec = prefs.sections[sid]
        sec.show_menu = bool(st.session_state.get(f"iface_show_{sid.value}", True))
        mode = st.session_state.get(f"iface_mode_{sid.value}", "section_default")
        if mode not in _MODE_OPTIONS:
            mode = "section_default"
        sec.mode = mode  # type: ignore[assignment]
        display = st.session_state.get(
            f"iface_display_{sid.value}", ActionDisplaySetting.INHERIT.value
        )
        if display not in _SECTION_DISPLAY_OPTIONS:
            display = ActionDisplaySetting.INHERIT.value
        sec.action_display = display  # type: ignore[assignment]
        selected: list[ActionId] = []
        for action_id in SECTION_ALLOWLISTS[sid]:
            if st.session_state.get(f"iface_sel_{sid.value}_{action_id.value}", False):
                selected.append(action_id)
        sec.selected = selected


@st.fragment
def render_interface_panel() -> None:
    """Render Interface menus settings (ordinary widgets + draft session state)."""
    first = DRAFT_SESSION_KEY not in st.session_state
    draft = get_or_hydrate_draft(st.session_state)
    pending_sync = bool(st.session_state.pop(_PENDING_WIDGET_SYNC_KEY, False))
    if first or pending_sync:
        _sync_widgets_from_draft()

    st.subheader("Help / info tips")
    st.caption(
        "Show or hide instructional ⓘ tips on widgets and Speakers methodology notes. "
        "Run-id identity ⓘ in the context bar stays available either way."
    )
    st.checkbox(
        "Show info tooltips",
        key="iface_show_info_tooltips",
        disabled=draft.recovery,
    )

    st.subheader("Action appearance")
    st.caption(
        "Choose whether action-menu links show an icon, a label, or both. "
        "Each section can keep the global default or override it."
    )
    st.radio(
        "Default appearance",
        options=_DISPLAY_OPTIONS,
        format_func=lambda m: _DISPLAY_LABELS[m],
        key="iface_action_display",
        horizontal=True,
        help=widget_help(
            "Applies to every action strip that is set to Use global default."
        ),
        disabled=draft.recovery,
    )

    st.subheader("Action menus")
    st.caption(
        "Customise the icon-link strips on Home, Library, Import, Speaker ID, "
        "and Run Analysis. Changes apply after Save."
    )

    if draft.recovery:
        st.warning(
            draft.recovery_message
            or "Interface menus file needs recovery. Normal Save is disabled."
        )
        if st.button(
            "Replace with built-in defaults",
            icon=ic.APPLY,
            key="iface_replace_defaults",
            type="primary",
        ):
            result = replace_with_built_in_defaults(draft)
            if result.ok:
                # Radio/checkboxes are instantiated below this branch — defer.
                _request_widget_sync()
                st.success(
                    "Replaced interface menus with built-in defaults (backup kept)."
                )
                st.rerun()
            else:
                st.error(result.error or "Replace failed.")

    st.markdown("##### Standard menu")
    st.radio(
        "Standard menu source",
        options=["Built-in", "Custom"],
        key="iface_std_mode",
        horizontal=True,
        help=widget_help(
            "Built-in is the Home-style Open · Charts · Artifacts · Export ZIP · Rename strip."
        ),
        disabled=draft.recovery,
    )
    if st.session_state.get("iface_std_mode") == "Custom":
        for action in ACTIONS:
            st.checkbox(
                action.label,
                key=f"iface_std_{action.id.value}",
                help=widget_help(action.help),
                disabled=draft.recovery,
            )

    st.markdown("##### Per-section menus")
    for sid in SECTION_ORDER:
        with st.expander(SECTION_LABELS[sid], expanded=False):
            show = st.checkbox(
                "Show menu",
                key=f"iface_show_{sid.value}",
                help=widget_help(
                    "When off, this section renders no action links. Mode and selections are kept."
                ),
                disabled=draft.recovery,
            )
            default_preview = " · ".join(
                a.value
                for a in section_default_actions(
                    sid, subject_type="transcript", has_run=True
                )
            )
            st.caption(
                f"Built-in section default (transcript + run): {default_preview}"
            )
            if sid == SectionId.SPEAKER_ID_COMPLETE:
                no_run = " · ".join(
                    a.value
                    for a in section_default_actions(
                        sid, subject_type="transcript", has_run=False
                    )
                )
                st.caption(f"Built-in when no run: {no_run}")
            if sid == SectionId.RUN_ANALYSIS_COMPLETE:
                group = " · ".join(
                    a.value
                    for a in section_default_actions(
                        sid, subject_type="group", has_run=True
                    )
                )
                st.caption(f"Built-in for group runs: {group}")

            st.radio(
                "Appearance",
                options=_SECTION_DISPLAY_OPTIONS,
                format_func=lambda m: _SECTION_DISPLAY_LABELS[m],
                key=f"iface_display_{sid.value}",
                horizontal=True,
                disabled=draft.recovery or not show,
                help=widget_help(
                    "Use global default follows Settings → Interface → Default appearance. "
                    "Icon-only buttons still show the action name on hover."
                ),
            )
            st.radio(
                "Menu mode",
                options=_MODE_OPTIONS,
                format_func=lambda m: _MODE_LABELS[m],
                key=f"iface_mode_{sid.value}",
                disabled=draft.recovery or not show,
                help=widget_help(
                    "Built-in: default actions for this section. "
                    "Manual: pick which actions appear."
                ),
            )
            mode = st.session_state.get(f"iface_mode_{sid.value}")
            if mode == "manual" and show and not draft.recovery:
                for action_id in SECTION_ALLOWLISTS[sid]:
                    action = next(a for a in ACTIONS if a.id == action_id)
                    st.checkbox(
                        action.label,
                        key=f"iface_sel_{sid.value}_{action_id.value}",
                        help=widget_help(action.help),
                    )
            elif not show:
                st.caption(
                    "Menu hidden. Mode and checkbox selections are retained for when you turn Show menu back on."
                )
            else:
                st.caption(
                    "Runtime context may temporarily hide unavailable actions "
                    "(for example Transcript, Charts, or Insights without a completed "
                    "run) without turning the menu off."
                )

    c1, c2, c3 = st.columns(3)
    with c1:
        save_clicked = st.button(
            "Save",
            icon=ic.SAVE,
            key="iface_save",
            type="primary",
            disabled=draft.recovery,
        )
    with c2:
        restore_clicked = st.button(
            "Restore built-in defaults", key="iface_restore", icon=ic.RESET
        )
    with c3:
        reload_clicked = st.button(
            "Reload saved settings", key="iface_reload", icon=ic.REFRESH
        )

    if save_clicked and not draft.recovery:
        _pull_widgets_into_draft()
        err = validate_draft_for_save(draft.prefs)
        if err:
            st.error(err)
        else:
            result = save_interface_prefs(draft)
            if result.ok:
                # Widgets already exist this run — hydrate on the next pass.
                _request_widget_sync()
                st.success("Interface menus saved.")
                st.rerun()
            elif result.conflict:
                st.error(result.error)
            else:
                st.error(result.error or "Save failed.")

    if restore_clicked:
        reset_draft_to_built_ins(st.session_state)
        _request_widget_sync()
        st.info("Draft reset to built-in defaults (not saved yet).")
        st.rerun()

    if reload_clicked:
        reload_draft_from_disk(st.session_state)
        _request_widget_sync()
        st.info("Reloaded saved interface menus.")
        st.rerun()
