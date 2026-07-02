"""
Streamlit-based web interface for TranscriptX.

To run:
    streamlit run src/transcriptx/web/app.py
"""

import time

_APP_IMPORT_STARTED_AT = time.perf_counter()

from transcriptx._bootstrap import bootstrap

bootstrap()

import streamlit as st

try:
    from transcriptx.web.page_modules.corrections_studio import (
        is_corrections_studio_enabled,
        render_corrections_studio,
    )

    _corrections_studio_available = is_corrections_studio_enabled()
except ImportError:
    _corrections_studio_available = False
    render_corrections_studio = None  # type: ignore[misc, assignment]

from transcriptx.core.utils.logger import get_logger
import transcriptx.web.blocks  # noqa: F401 — register built-in view blocks
from transcriptx.web.components.context_bar import render_context_bar
from transcriptx.web.navigation import (
    normalize_navigation_context_from_session,
    should_hydrate_workspace_context,
)
from transcriptx.web.page_flash import consume_page_flash
from transcriptx.web.page_modules.transcript import navigate_to_segment
from transcriptx.web.perf import (
    finish_run,
    instrument_cached_call,
    record_elapsed_section,
    start_run,
    section,
)
from transcriptx.web.router import PAGE_PREREQUISITES, route_current_page
from transcriptx.web.shell import configure_streamlit_page, inject_global_styles
from transcriptx.web.sidebar import render_sidebar
from transcriptx.web.sidebar_options import get_cached_session_data
from transcriptx.web.state import (
    PAGE_KEY,
    TX_NAV_EXPANDER_VIEW,
    TX_NAV_WORKSPACE_SELECTOR_REQUESTED,
)

logger = get_logger()

configure_streamlit_page()
inject_global_styles()


def _init_defaults() -> None:
    """Initialize app-level session defaults.

    Contract: when page is not yet set, canonical default is ``Home``.
    """
    if PAGE_KEY not in st.session_state:
        st.session_state[PAGE_KEY] = "Home"
    if st.session_state.get(PAGE_KEY) == "Configuration":
        st.session_state[PAGE_KEY] = "Settings"
        st.rerun()
    st.session_state.setdefault("analysis_artifacts_version", 0)
    st.session_state.setdefault("analysis_run_in_progress", False)


def main() -> None:
    """Main application entry point."""
    _init_defaults()
    current_page = st.session_state.get(PAGE_KEY, "Home")
    scenario = st.query_params.get("perf_scenario")
    run_id = start_run(page=current_page, scenario=str(scenario) if scenario else None)
    record_elapsed_section(
        "app.import_bootstrap",
        bucket="import_bootstrap",
        elapsed_ms=(time.perf_counter() - _APP_IMPORT_STARTED_AT) * 1000,
        extra={"current_page": current_page},
    )
    load_error = None
    # First paint contract: do not hydrate workspace/session data here unless the
    # current page needs run-scoped context or the user explicitly requested it.
    should_hydrate = should_hydrate_workspace_context(
        current_page,
        view_opened=bool(st.session_state.get(TX_NAV_EXPANDER_VIEW, False)),
        explicit_request=bool(
            st.session_state.get(TX_NAV_WORKSPACE_SELECTOR_REQUESTED, False)
        ),
    )
    if should_hydrate:
        try:
            instrument_cached_call(
                "cached_list_available_sessions",
                get_cached_session_data,
                bucket="deferred_workspace_hydration",
            )
        except Exception as exc:
            logger.warning(f"Failed to load session list: {exc}", exc_info=True)
            load_error = str(exc)

    if should_hydrate:
        normalize_navigation_context_from_session(st.session_state)
    current_page = st.session_state.get(PAGE_KEY, "Home")
    try:
        with section(
            "sidebar.render",
            bucket="render_routing",
            extra={"current_page": current_page, "run_id": run_id},
        ):
            with st.sidebar:
                render_sidebar(
                    current_page=current_page,
                    corrections_studio_available=_corrections_studio_available,
                    prerequisites=PAGE_PREREQUISITES,
                )

        if load_error:
            st.error(f"Could not load session list: {load_error}")

        consume_page_flash()
        render_context_bar(st.session_state)

        try:
            with section(
                "route_current_page",
                bucket="render_routing",
                extra={"current_page": current_page, "run_id": run_id},
            ):
                route_current_page(
                    st.session_state,
                    corrections_studio_available=_corrections_studio_available,
                    render_corrections_studio=render_corrections_studio,
                )
        except Exception as exc:
            logger.error(f"Error in main app: {exc}", exc_info=True)
            st.error(f"An unexpected error occurred: {exc}")
            st.exception(exc)
    finally:
        finish_run(notes=f"page={current_page}")


__all__ = ["main", "navigate_to_segment"]


if __name__ == "__main__":
    main()
