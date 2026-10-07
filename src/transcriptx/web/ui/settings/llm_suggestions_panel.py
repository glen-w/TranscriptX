"""Settings batch warm for assistive LLM rename / speaker-name suggestion caches."""

from __future__ import annotations

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.web.components.info_tooltip import widget_help

_NAME_PREVIEW_KEY = "_llm_name_suggest_bulk_preview"
_NAME_RESULT_KEY = "_llm_name_suggest_bulk_last_result"
_RENAME_PREVIEW_KEY = "_llm_rename_suggest_bulk_preview"
_RENAME_RESULT_KEY = "_llm_rename_suggest_bulk_last_result"


def _render_warm_result(result, title: str) -> None:
    from transcriptx.app.models.results import WarmSuggestionsResult

    st.markdown(f"##### {title}")
    if isinstance(result, WarmSuggestionsResult):
        st.caption(
            f"Warmed: {result.ok_count} · "
            f"Already fresh: {result.skipped_fresh_count} · "
            f"Errors: {result.error_count}"
        )
        with st.expander("Details", expanded=result.error_count > 0):
            for line in result.log_lines:
                if "error" in line.split(":", 1)[-1]:
                    st.error(line)
                else:
                    st.text(line)
        return
    st.caption(
        f"Warmed: {result.ok_count} · "
        f"Already fresh: {result.skipped_fresh_count} · "
        f"Errors: {result.error_count}"
    )
    with st.expander("Details", expanded=result.error_count > 0):
        for row in result.targets:
            line = f"{row.transcript_label} [{row.kind.value}]: {row.status.value}"
            if row.message:
                line += f" — {row.message}"
            if row.status.value == "error":
                st.error(line)
            else:
                st.text(line)


def render_speaker_name_suggestion_bulk() -> None:
    """Library-wide warm for Speaker ID name suggestion dropdowns."""
    from transcriptx.app.models.requests import WarmSuggestionsRequest
    from transcriptx.app.workflows.warm_suggestions import run_warm_suggestions
    from transcriptx.services.llm_suggestions.bulk_warm import BulkLlmSuggestionsService

    st.markdown("##### Pre-load name suggestions (LLM)")
    st.caption(
        "Runs the same assistive pass as Speaker Identification → Suggest names "
        "for every managed transcript and writes caches under "
        "`speaker_profiles/.cache/identify/`. Opening Speaker ID then shows "
        "dropdown suggestions without clicking Suggest names. Nothing is saved "
        "until you confirm in the UI. Requires Ollama when LLM refinement is "
        "enabled in Settings → Models (`speaker_name_suggestions`). "
        "Host CLI: `transcriptx warm-suggestions --speaker-names`."
    )

    pending = st.session_state.pop(_NAME_RESULT_KEY, None)
    if pending is not None:
        _render_warm_result(pending, "Name suggestion pre-load result")

    if st.button(
        "Refresh name suggestion inventory",
        key="llm_name_bulk_preview_btn",
        icon=ic.REFRESH,
    ):
        try:
            preview = BulkLlmSuggestionsService().preview_speaker_names()
            st.session_state[_NAME_PREVIEW_KEY] = preview
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    preview = st.session_state.get(_NAME_PREVIEW_KEY)
    if preview is None:
        st.info("Refresh inventory to see how many managed transcripts will be warmed.")
        return

    c1, c2 = st.columns(2)
    c1.metric("Managed transcripts", preview.transcript_count)
    c2.metric("Actionable", preview.actionable_count)
    if preview.actionable_count == 0:
        st.info("No managed transcripts to warm for name suggestions.")
        return

    if st.button(
        "Pre-load name suggestions (LLM)",
        type="primary",
        icon=ic.REFRESH,
        key="llm_name_bulk_warm_btn",
        help=widget_help(
            "Warm assistive speaker name suggestion caches library-wide."
        ),
    ):
        try:
            progress = st.progress(0.0, text="Starting…")
            status = st.empty()

            def _on_progress(index: int, total: int, name: str) -> None:
                frac = index / total if total else 1.0
                progress.progress(min(frac, 1.0), text=f"{index}/{total}: {name}")
                status.caption(f"Warming {name}")

            result = run_warm_suggestions(
                WarmSuggestionsRequest(warm_speaker_names=True),
                progress=_on_progress,
            )
            progress.progress(1.0, text="Done")
            st.session_state.pop(_NAME_PREVIEW_KEY, None)
            st.session_state[_NAME_RESULT_KEY] = result
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def render_rename_suggestion_bulk() -> None:
    """Warm rename content suggestion caches when content mode is auto."""
    from transcriptx.core.utils.config import get_config
    from transcriptx.app.models.requests import WarmSuggestionsRequest
    from transcriptx.app.workflows.warm_suggestions import run_warm_suggestions
    from transcriptx.services.llm_suggestions.bulk_warm import BulkLlmSuggestionsService

    content_mode = str(
        getattr(get_config().input, "rename_content_suggestions", "off") or "off"
    )
    if content_mode != "auto":
        return

    st.markdown("##### Pre-load rename suggestions")
    st.caption(
        "Runs the same assistive pass as the Rename Transcript form (transcript "
        "cues, optional local LLM, optional web) for every managed transcript "
        "and writes caches under `data_dir/.cache/rename/`. Rename forms then "
        "open with prefilled stems without blocking on Ollama. Nothing is "
        "renamed until you submit Rename. "
        "Host CLI: `transcriptx warm-suggestions --rename`."
    )

    pending = st.session_state.pop(_RENAME_RESULT_KEY, None)
    if pending is not None:
        _render_warm_result(pending, "Rename suggestion pre-load result")

    if st.button(
        "Refresh rename suggestion inventory",
        key="llm_rename_bulk_preview_btn",
        icon=ic.REFRESH,
    ):
        try:
            preview = BulkLlmSuggestionsService().preview_rename()
            st.session_state[_RENAME_PREVIEW_KEY] = preview
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    preview = st.session_state.get(_RENAME_PREVIEW_KEY)
    if preview is None:
        st.info(
            "Refresh inventory to see how many transcripts will be warmed for rename."
        )
        return

    c1, c2 = st.columns(2)
    c1.metric("Managed transcripts", preview.transcript_count)
    c2.metric("Actionable", preview.actionable_count)
    if preview.actionable_count == 0:
        st.info("No managed transcripts to warm for rename suggestions.")
        return

    if st.button(
        "Pre-load rename suggestions",
        type="primary",
        icon=ic.REFRESH,
        key="llm_rename_bulk_warm_btn",
        help=widget_help("Warm assistive rename suggestion caches library-wide."),
    ):
        try:
            progress = st.progress(0.0, text="Starting…")
            status = st.empty()

            def _on_progress(index: int, total: int, name: str) -> None:
                frac = index / total if total else 1.0
                progress.progress(min(frac, 1.0), text=f"{index}/{total}: {name}")
                status.caption(f"Warming {name}")

            result = run_warm_suggestions(
                WarmSuggestionsRequest(warm_rename=True),
                progress=_on_progress,
            )
            progress.progress(1.0, text="Done")
            st.session_state.pop(_RENAME_PREVIEW_KEY, None)
            st.session_state[_RENAME_RESULT_KEY] = result
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
