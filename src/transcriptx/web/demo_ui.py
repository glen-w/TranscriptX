"""Home / Settings demo + onboarding UI helpers."""

from __future__ import annotations

import streamlit as st

from transcriptx.demo import (
    DemoStatusKind,
    install_demo_project,
    remove_demo_project,
    status_demo_project,
)
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
    with st.expander("Explore examples", expanded=status.kind == DemoStatusKind.MISSING):
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
        st.caption("Lightweight checklist — optional, skippable where marked, non-blocking.")
        for item_id in ALL_ITEM_IDS:
            item = prefs.items.get(item_id)
            state = item.state if item else "pending"
            label = ITEM_LABELS.get(item_id, item_id)
            optional = item_id in OPTIONAL_ITEM_IDS
            cols = st.columns([4, 1, 1, 1])
            with cols[0]:
                suffix = " (optional)" if optional else ""
                st.write(f"{'✅' if state == 'completed' else '○'} {label}{suffix} — *{state}*")
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


def render_settings_demo_controls() -> None:
    status = status_demo_project()
    with st.expander("Demo project", expanded=False):
        st.caption(
            f"Status: **{status.kind.value}** — {status.detail or '—'}\n\n"
            "Removes demo transcripts, the owned demo group, and analysis runs still "
            "attached to those demo transcripts (including later user runs on them)."
        )
        _render_demo_controls(status)
        if st.button("Reopen getting started checklist", key="onboard_reopen"):
            set_dismissed(False)
            st.rerun()


def _render_demo_controls(status) -> None:
    cols = st.columns(3)
    with cols[0]:
        if status.kind in {
            DemoStatusKind.MISSING,
            DemoStatusKind.STALE,
            DemoStatusKind.PARTIAL,
            DemoStatusKind.CORRUPT,
        }:
            if st.button("Load demo project", type="primary", key="demo_load"):
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
            st.warning("Demo is stale vs pack/schema — remove and reload.")
