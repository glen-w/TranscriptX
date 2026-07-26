"""Sidebar renderer for TranscriptX app."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.navigation import (
    NavSection,
    PageSpec,
    context_readiness,
    evaluate_page_access,
    pages_in_section,
)
from transcriptx.web.services import SubjectService
from transcriptx.web.sidebar_hydration import hydrate_sidebar_state
from transcriptx.web.sidebar_state import (
    SidebarSelectionResult,
    apply_sidebar_selection,
)
from transcriptx.web.sidebar_workspace import (
    build_group_labels,
    render_group_picker,
    render_no_runs_hint,
    render_run_picker,
    render_sidebar_stats,
    render_transcript_picker,
)
from transcriptx.web.state import (
    PAGE_KEY,
    RUN_ID_KEY,
    SUBJECT_ID_KEY,
    SUBJECT_TYPE_KEY,
    SUBJECT_TYPE_SELECTOR_KEY,
)

_SECTION_TITLES: dict[NavSection, str] = {
    "workflow": "Workflow",
    "view": "View",
    "tools": "Tools",
    "settings": "Settings",
}

_SUBJECT_TYPE_OPTIONS = ("Transcript", "Group")
_LABEL_TO_CANONICAL = {"Transcript": "transcript", "Group": "group"}
_CANONICAL_TO_LABEL = {"transcript": "Transcript", "group": "Group"}
_SUBJECT_TYPE_SELECTOR_KEY = SUBJECT_TYPE_SELECTOR_KEY


def _nav_section(title: str) -> None:
    """Non-interactive sidebar section label."""
    st.markdown(
        f'<div class="subject-section-header">{title}</div>',
        unsafe_allow_html=True,
    )


def _list_runs_for_subject(subject) -> list:
    """Cached run listing for a resolved subject (avoids a dir scan per rerun)."""
    from transcriptx.web.cache_helpers import cached_list_runs

    scope_type = getattr(subject.scope, "scope_type", None) or getattr(
        subject, "subject_type", "transcript"
    )
    if scope_type == "group":
        return cached_list_runs(
            "group", group_uuid=getattr(subject.scope, "uuid", None)
        )
    return cached_list_runs("transcript", subject_id=subject.subject_id)


def _normalise_subject_type_selector(session_state: dict) -> str:
    """Ensure ``subject_type_selector`` is a single valid non-empty UI label.

    Prefers an already-valid widget value so unrelated reruns do not reset to
    Transcript. Falls back to canonical ``subject_type``, then Transcript.
    """
    raw = session_state.get(_SUBJECT_TYPE_SELECTOR_KEY)
    if raw in _SUBJECT_TYPE_OPTIONS:
        return raw
    if isinstance(raw, (list, tuple)) and raw:
        first = raw[0]
        if first in _SUBJECT_TYPE_OPTIONS:
            session_state[_SUBJECT_TYPE_SELECTOR_KEY] = first
            return first
    canonical = session_state.get(SUBJECT_TYPE_KEY)
    label = _CANONICAL_TO_LABEL.get(canonical, "Transcript")
    session_state[_SUBJECT_TYPE_SELECTOR_KEY] = label
    return label


def _render_workspace_pickers(session_state: dict) -> None:
    """Render transcript/group/run selectors in the sidebar workspace panel."""
    _normalise_subject_type_selector(session_state)
    subject_type_label = st.segmented_control(
        "Type",
        options=list(_SUBJECT_TYPE_OPTIONS),
        key=_SUBJECT_TYPE_SELECTOR_KEY,
        label_visibility="collapsed",
    )
    if subject_type_label not in _SUBJECT_TYPE_OPTIONS:
        subject_type_label = _normalise_subject_type_selector(session_state)
    subject_type = _LABEL_TO_CANONICAL[subject_type_label]
    current_run_id = session_state.get(RUN_ID_KEY)

    if subject_type == "transcript":
        from transcriptx.web.sidebar_options import get_transcript_dropdown_options

        transcript_options, transcript_format = get_transcript_dropdown_options()
        groups: list = []
    else:
        transcript_options = []
        transcript_format = lambda x: x  # noqa: E731
        try:
            from transcriptx.web.cache_helpers import cached_list_groups

            groups = cached_list_groups()
        except Exception:
            groups = []

    pre_subject = SubjectService.resolve_current_subject(session_state)
    pre_runs = _list_runs_for_subject(pre_subject) if pre_subject else []
    pre_state = hydrate_sidebar_state(
        session_state,
        subject_type=subject_type,
        explicit_request=False,
        transcript_options=transcript_options,
        groups=groups,
        resolved_subject=pre_subject,
        runs=pre_runs,
    )

    if subject_type == "transcript":
        if not transcript_options:
            render_sidebar_stats(status=pre_state.status, subject_type=subject_type)
            apply_sidebar_selection(
                session_state,
                SidebarSelectionResult(
                    subject_type=subject_type, subject_id=None, run_id=None
                ),
            )
        else:
            selected = render_transcript_picker(
                options=transcript_options,
                format_func=transcript_format,
                default_subject_id=pre_state.subject_id,
            )
            apply_sidebar_selection(
                session_state,
                SidebarSelectionResult(
                    subject_type=subject_type,
                    subject_id=selected,
                    run_id=current_run_id,
                ),
            )
    elif not groups:
        render_sidebar_stats(status=pre_state.status, subject_type=subject_type)
        apply_sidebar_selection(
            session_state,
            SidebarSelectionResult(
                subject_type=subject_type, subject_id=None, run_id=None
            ),
        )
    else:
        group_labels = build_group_labels(groups)
        selected_group = render_group_picker(
            group_keys=pre_state.group_keys or [],
            group_labels=group_labels,
            default_subject_id=pre_state.subject_id,
        )
        apply_sidebar_selection(
            session_state,
            SidebarSelectionResult(
                subject_type=subject_type,
                subject_id=selected_group,
                run_id=current_run_id,
            ),
        )

    subject = SubjectService.resolve_current_subject(session_state)
    if subject:
        if (
            pre_subject is not None
            and pre_subject.subject_type == subject.subject_type
            and pre_subject.subject_id == subject.subject_id
        ):
            runs = pre_runs
        else:
            runs = _list_runs_for_subject(subject)
        run_options = [r.run_id for r in runs]
        post_state = hydrate_sidebar_state(
            session_state,
            subject_type=subject_type,
            explicit_request=False,
            transcript_options=transcript_options,
            groups=groups,
            resolved_subject=subject,
            runs=runs,
        )
        if run_options:
            selected_run_id = render_run_picker(
                run_options=run_options,
                default_run_id=post_state.run_id,
            )
            apply_sidebar_selection(
                session_state,
                SidebarSelectionResult(
                    subject_type=subject_type,
                    subject_id=session_state.get(SUBJECT_ID_KEY),
                    run_id=selected_run_id,
                ),
            )
        else:
            render_no_runs_hint(subject_type=subject_type)
            apply_sidebar_selection(
                session_state,
                SidebarSelectionResult(
                    subject_type=subject_type,
                    subject_id=session_state.get(SUBJECT_ID_KEY),
                    run_id=None,
                ),
            )
    else:
        apply_sidebar_selection(
            session_state,
            SidebarSelectionResult(
                subject_type=subject_type,
                subject_id=session_state.get(SUBJECT_ID_KEY),
                run_id=None,
            ),
        )


def render_sidebar(
    *,
    current_page: str,
    corrections_studio_available: bool,
    prerequisites: dict,
) -> None:
    """Sidebar: static grouped nav with always-visible workspace pickers."""
    session_state = st.session_state

    from transcriptx.web.shell import brand_logo_path

    logo = brand_logo_path()
    if logo is not None:
        st.image(str(logo), width=200)

    def _apply_navigation(page_key: str) -> None:
        session_state[PAGE_KEY] = page_key
        st.rerun()

    def _nav_button(
        spec: PageSpec,
        *,
        key_suffix: str = "",
        disabled: bool = False,
        help: str | None = None,
    ) -> None:
        page_key = spec.key
        label = spec.label
        is_active = current_page == page_key and not disabled
        text = f"**{label}**" if is_active else label
        btn_key = f"nav_{page_key}{key_suffix}"
        btn_type = "primary" if is_active else "secondary"
        if disabled:
            st.button(
                text,
                key=btn_key,
                width="stretch",
                type="secondary",
                disabled=True,
                help=help,
            )
        elif st.button(text, key=btn_key, width="stretch", type=btn_type, help=help):
            _apply_navigation(page_key)

    def _render_nav_spec(spec: PageSpec, *, key_suffix: str = "") -> None:
        if spec.key == "Corrections Studio" and not corrections_studio_available:
            return
        access = evaluate_page_access(
            spec.key, prerequisites, context_readiness(session_state)
        )
        _nav_button(
            spec,
            key_suffix=key_suffix,
            disabled=not access.allowed,
        )

    for spec in pages_in_section("primary"):
        _render_nav_spec(spec)

    # tx_sidebar_workflow_nav (order asserted in tests/web/test_upload_transcript_page.py)
    _nav_section(_SECTION_TITLES["workflow"])
    for spec in pages_in_section("workflow"):
        _render_nav_spec(spec)

    _nav_section(_SECTION_TITLES["view"])
    view_specs = pages_in_section("view")
    browse_specs = [s for s in view_specs if s.required_context == "none"]
    context_page_specs = [s for s in view_specs if s.required_context != "none"]
    for spec in browse_specs:
        _render_nav_spec(spec, key_suffix="_view")

    _render_workspace_pickers(session_state)

    for spec in context_page_specs:
        _render_nav_spec(spec, key_suffix="_subject")

    # tx_sidebar_tools_group (test anchor: workflow nav must appear above this)
    tools = pages_in_section("tools")
    if tools:
        _nav_section(_SECTION_TITLES["tools"])
        for spec in tools:
            _render_nav_spec(spec)

    _nav_section(_SECTION_TITLES["settings"])
    for spec in pages_in_section("settings"):
        _render_nav_spec(spec)
