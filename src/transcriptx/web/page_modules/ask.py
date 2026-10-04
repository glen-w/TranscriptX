"""
Ask page: evidence-based Q&A over transcript segments via RAG.

Fragment-wrapped to prevent rerun on navigation. Cite chips jump via SegmentRef.
"""

from pathlib import Path

import streamlit as st

from transcriptx.core.rag import RagAPI, RagScopeMissing, RagUnavailable
from transcriptx.core.segments import get_segments
from transcriptx.web import icons as ic
from transcriptx.web.components.ask_question_library import render_ask_global_library_picker
from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.state import RUN_ID_KEY, SUBJECT_ID_KEY
from transcriptx.web.transcript_navigation import navigate_to_segment


def render_ask_page() -> None:
    """Render the Ask page (full height Q&A + sources)."""
    st.set_page_config(layout="wide")
    st.title("Ask")

    api = RagAPI()

    if not api.is_enabled():
        st.warning(
            "RAG is not enabled. Enable TRANSCRIPTX_RAG_ENABLED and restart to use Ask."
        )
        return

    session_slug = st.session_state.get(SUBJECT_ID_KEY)
    run_id = st.session_state.get(RUN_ID_KEY)
    if not session_slug or not run_id:
        st.error("No transcript selected. Choose one transcript in the sidebar first.")
        return

    transcript_path = SubjectService.current_transcript_path(st.session_state)
    if not transcript_path:
        st.error("No transcript selected. Choose one transcript in the sidebar first.")
        return

    try:
        status = api.index_status()
    except RagUnavailable as exc:
        st.error(str(exc))
        return

    if status.get("status") == "unavailable":
        st.error("Ask is unavailable: install lancedb (pip install -e '.[rag]' from this checkout).")
        return

    title = Path(transcript_path).stem
    if st.button("Index this transcript", icon=ic.INVENTORY):
        try:
            segments = get_segments(transcript_path, cache=True)
            api.ingest(
                Path(transcript_path),
                str(session_slug),
                str(run_id),
                title,
                segments,
            )
            st.success("Indexed this transcript.")
        except Exception as exc:
            st.error(f"Indexing failed: {exc}")
            return

    if status.get("status") == "missing":
        st.info("Index this transcript, then ask a question here.")

    library_questions = render_ask_global_library_picker()
    for i, question in enumerate(library_questions):
        st.divider()
        st.markdown(f"**{question}**")
        _render_rag_answer(
            api,
            question,
            str(session_slug),
            str(run_id),
            key_suffix=f"lib_{i}",
        )

    _ask_interaction(str(session_slug), str(run_id))


def _render_rag_answer(
    api: RagAPI,
    question: str,
    session_slug: str,
    run_id: str,
    *,
    key_suffix: str = "chat",
) -> None:
    try:
        hits = api.search(question, session_slug=session_slug, run_id=run_id, k=5)

        if not hits:
            st.info("No relevant passages found.")
            return

        answer_stream = api.answer(question, session_slug=session_slug, run_id=run_id, k=5)

        st.write_stream(answer_stream)

        st.subheader("Sources")
        cited_sources = answer_stream.cited()

        if not cited_sources:
            st.caption("(Retrieved, not cited)")
        else:
            for source in cited_sources:
                chip_text = f"{source.citation} [{source.marker}]"
                if st.button(
                    chip_text,
                    key=f"cite_{key_suffix}_{source.marker}",
                    icon=ic.LINK,
                    use_container_width=False,
                ):
                    navigate_to_segment(
                        source.segment_ref,
                        highlight_query=question,
                    )

    except RagScopeMissing as exc:
        st.error(str(exc))
    except Exception as e:
        st.error(f"Error: {e}")


@st.fragment
def _ask_interaction(session_slug: str, run_id: str) -> None:
    """Q&A interaction (fragment-wrapped to preserve thread on navigate)."""
    api = RagAPI()

    question = st.chat_input("Ask a question about this transcript...")
    if not question:
        return

    _render_rag_answer(api, question, session_slug, run_id)
