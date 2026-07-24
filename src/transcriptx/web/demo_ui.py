"""Home / Settings demo + onboarding UI helpers."""

from __future__ import annotations

import streamlit as st

from transcriptx.demo import (
    DemoStatusKind,
    install_demo_project,
    refresh_demo_project,
    remove_demo_project,
    status_demo_project,
)
from transcriptx.web.cache_helpers import get_cached_count_managed_transcripts
from transcriptx.web.onboarding.prefs import (
    ALL_ITEM_IDS,
    ITEM_LABELS,
    ITEM_PAGES,
    OPTIONAL_ITEM_IDS,
    derived_complete,
    get_cached_onboarding_prefs,
    set_dismissed,
    set_item_state,
)
from transcriptx.web.state import PAGE_KEY


def render_home_demo_and_onboarding() -> None:
    status = status_demo_project()
    library_empty = False
    try:
        library_empty = int(get_cached_count_managed_transcripts()) == 0
    except Exception:
        library_empty = status.kind == DemoStatusKind.MISSING

    if library_empty and status.kind == DemoStatusKind.MISSING:
        st.info(
            "Your library is empty. Load the demo project for a quick guided walkthrough, "
            "or import your own transcript."
        )
        cols = st.columns(2)
        with cols[0]:
            if st.button("Load demo project", type="primary", key="demo_load_primary"):
                with st.spinner("Installing demo…"):
                    result = install_demo_project()
                if result.ok:
                    st.success(result.detail)
                    st.rerun()
                else:
                    st.error(result.detail)
                    for err in result.errors[:8]:
                        st.caption(err)
        with cols[1]:
            if st.button("Import transcript", key="demo_import_primary"):
                st.session_state[PAGE_KEY] = "Import Transcript"
                st.rerun()

    with st.expander(
        "Explore examples",
        expanded=status.kind
        in {
            DemoStatusKind.MISSING,
            DemoStatusKind.STALE,
            DemoStatusKind.PARTIAL,
            DemoStatusKind.CORRUPT,
        },
    ):
        st.caption(
            "Load a small synthetic demo project (isolated ownership). "
            "Removal deletes demo transcripts, the owned demo group, and analysis "
            "runs still attached to those demo transcripts (including any you ran later on them)."
        )
        _render_demo_controls(status)

    prefs = get_cached_onboarding_prefs()
    if prefs.dismissed or derived_complete(prefs):
        return
    with st.expander("Getting started", expanded=True):
        st.caption(
            "Lightweight checklist — optional, skippable where marked, non-blocking."
        )
        hints = _workspace_hints()
        for item_id in ALL_ITEM_IDS:
            item = prefs.items.get(item_id)
            state = item.state if item else "pending"
            label = ITEM_LABELS.get(item_id, item_id)
            optional = item_id in OPTIONAL_ITEM_IDS
            hint = ""
            if state == "pending" and item_id in hints:
                hint = f" — suggested by workspace: {hints[item_id]}"
            cols = st.columns([4, 1, 1, 1])
            with cols[0]:
                suffix = " (optional)" if optional else ""
                mark = (
                    "✅"
                    if state == "completed"
                    else ("⏭" if state == "skipped" else "○")
                )
                st.write(f"{mark} {label}{suffix} — *{state}*{hint}")
            with cols[1]:
                if st.button("Go", key=f"onboard_go_{item_id}"):
                    st.session_state[PAGE_KEY] = ITEM_PAGES.get(item_id, "Home")
                    st.rerun()
            with cols[2]:
                if st.button("Done", key=f"onboard_done_{item_id}"):
                    set_item_state(item_id, "completed")
                    st.rerun()
            with cols[3]:
                if optional and st.button("Skip", key=f"onboard_skip_{item_id}"):
                    set_item_state(item_id, "skipped")
                    st.rerun()
        if st.button("Dismiss checklist", key="onboard_dismiss"):
            set_dismissed(True)
            st.rerun()


_DEMO_TOGGLE_KEY = "settings_demo_project_toggle"
_DEMO_TOGGLE_PENDING_KEY = "settings_demo_project_toggle_pending"
_DEMO_FLASH_ERROR_KEY = "settings_demo_project_flash_error"


def render_settings_demo_controls() -> None:
    """Settings backend: simple Demo project on/off plus checklist reopen."""
    status = status_demo_project()
    present = status.kind in {
        DemoStatusKind.INSTALLED,
        DemoStatusKind.STALE,
        DemoStatusKind.PARTIAL,
        DemoStatusKind.CORRUPT,
    }
    with st.expander("Demo project", expanded=False):
        st.caption(
            f"Status: **{status.kind.value}** — {status.detail or '—'}\n\n"
            "On installs the synthetic demo pack. Off removes demo transcripts, the "
            "owned demo group, and analysis runs still attached to those demo "
            "transcripts (including later user runs on them)."
        )
        flash = st.session_state.pop(_DEMO_FLASH_ERROR_KEY, None)
        if flash:
            st.error(flash.get("detail") or "Demo update failed.")
            for err in (flash.get("errors") or [])[:8]:
                st.caption(err)
        if st.session_state.pop(_DEMO_TOGGLE_PENDING_KEY, False) or (
            _DEMO_TOGGLE_KEY not in st.session_state
        ):
            st.session_state[_DEMO_TOGGLE_KEY] = present
        desired_on = st.toggle(
            "Demo project",
            key=_DEMO_TOGGLE_KEY,
            help="On: load demo. Off: remove demo.",
        )
        if desired_on and status.kind == DemoStatusKind.MISSING:
            with st.spinner("Installing demo…"):
                result = install_demo_project()
            st.session_state[_DEMO_TOGGLE_PENDING_KEY] = True
            if not result.ok:
                st.session_state[_DEMO_FLASH_ERROR_KEY] = {
                    "detail": result.detail,
                    "errors": list(result.errors or []),
                }
            st.rerun()
        elif (not desired_on) and present:
            with st.spinner("Removing demo…"):
                result = remove_demo_project()
            st.session_state[_DEMO_TOGGLE_PENDING_KEY] = True
            if not result.ok:
                st.session_state[_DEMO_FLASH_ERROR_KEY] = {
                    "detail": result.detail,
                    "errors": list(result.errors or []),
                }
            st.rerun()
        if status.kind in {
            DemoStatusKind.STALE,
            DemoStatusKind.PARTIAL,
            DemoStatusKind.CORRUPT,
        }:
            label = (
                "Refresh demo project"
                if status.kind != DemoStatusKind.CORRUPT
                else "Repair demo project"
            )
            if status.kind == DemoStatusKind.STALE:
                st.warning("Demo is stale vs pack/schema — refresh removes then reloads.")
            elif status.kind == DemoStatusKind.PARTIAL:
                st.warning("Demo install/remove was interrupted — refresh to recover.")
            else:
                st.warning("Demo looks corrupt — repair removes then reloads.")
            if st.button(label, key="demo_refresh_settings"):
                with st.spinner("Updating demo…"):
                    result = refresh_demo_project()
                st.session_state[_DEMO_TOGGLE_PENDING_KEY] = True
                if not result.ok:
                    st.session_state[_DEMO_FLASH_ERROR_KEY] = {
                        "detail": result.detail,
                        "errors": list(result.errors or []),
                    }
                st.rerun()
        if st.button("Reopen getting started checklist", key="onboard_reopen"):
            set_dismissed(False)
            st.rerun()


def _workspace_hints() -> dict[str, str]:
    """Display-only auto signals; never override explicit skipped/completed."""
    hints: dict[str, str] = {}
    try:
        if int(get_cached_count_managed_transcripts()) > 0:
            hints["import_or_demo"] = "library has transcripts"
            hints["open_library"] = "library reachable"
    except Exception:
        pass
    try:
        from transcriptx.demo import status_demo_project as _status

        if _status().kind == DemoStatusKind.INSTALLED:
            hints["import_or_demo"] = "demo installed"
    except Exception:
        pass
    return hints


def _render_demo_controls(status) -> None:
    cols = st.columns(3)
    with cols[0]:
        if status.kind in {
            DemoStatusKind.MISSING,
            DemoStatusKind.STALE,
            DemoStatusKind.PARTIAL,
            DemoStatusKind.CORRUPT,
        }:
            label = (
                "Refresh demo project"
                if status.kind
                in {
                    DemoStatusKind.STALE,
                    DemoStatusKind.PARTIAL,
                    DemoStatusKind.CORRUPT,
                }
                else "Load demo project"
            )
            if st.button(label, type="primary", key="demo_load"):
                with st.spinner("Updating demo…"):
                    result = (
                        refresh_demo_project()
                        if status.kind != DemoStatusKind.MISSING
                        else install_demo_project()
                    )
                if result.ok:
                    st.success(result.detail)
                    st.rerun()
                else:
                    st.error(result.detail)
                    for err in result.errors[:8]:
                        st.caption(err)
    with cols[1]:
        if status.kind in {
            DemoStatusKind.INSTALLED,
            DemoStatusKind.STALE,
            DemoStatusKind.PARTIAL,
        }:
            if st.button("Remove demo project", key="demo_remove"):
                with st.spinner("Removing demo…"):
                    result = remove_demo_project()
                if result.ok:
                    st.success(result.detail)
                    st.rerun()
                else:
                    st.error(result.detail)
                    for err in result.errors[:8]:
                        st.caption(err)
    with cols[2]:
        if status.kind == DemoStatusKind.STALE:
            st.warning("Demo is stale vs pack/schema — refresh removes then reloads.")
        elif status.kind == DemoStatusKind.PARTIAL:
            st.warning("Demo install/remove was interrupted — refresh to recover.")
