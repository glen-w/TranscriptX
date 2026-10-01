"""
Ask page: evidence-based Q&A over transcript segments via RAG.

Fragment-wrapped to prevent rerun on navigation. Cite chips jump via SegmentRef.
"""

import streamlit as st

from transcriptx.core.rag import RagAPI
from transcriptx.core.segments import get_segments
from transcriptx.web.models.search import SegmentRef
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

    # Scope selector (P0: current transcript only)
    current_subject = st.session_state.get("current_subject_id")
    if not current_subject:
        st.error("No transcript selected. Go to Transcript page first.")
        return

    # Index status
    status = api.index_status()
    if status.get("status") == "missing":
        st.info(
            "Index not built yet. Go to Settings → Build RAG Index, then ask a question here."
        )
        return

    # Ask interaction (wrapped in fragment)
    _ask_interaction()


@st.fragment
def _ask_interaction() -> None:
    """Q&A interaction (fragment-wrapped to preserve thread on navigate)."""
    api = RagAPI()

    # Parse session/run from current subject
    current_subject = st.session_state.get("current_subject_id")
    if "/" not in str(current_subject):
        st.error("Invalid subject format.")
        return

    session_slug, run_id = str(current_subject).split("/", 1)

    # Question input
    question = st.chat_input("Ask a question about this transcript...")
    if not question:
        return

    # Search and answer
    try:
        hits = api.search(question, session_slug=session_slug, run_id=run_id, k=5)

        if not hits:
            st.info("No relevant passages found.")
            return

        answer_stream = api.answer(question, session_slug=session_slug, run_id=run_id, k=5)

        # Stream answer text
        st.write_stream(answer_stream)

        # Show sources with cite chips
        st.subheader("Sources")
        cited_sources = answer_stream.cited()

        if not cited_sources:
            st.caption("(Retrieved, not cited)")
        else:
            for source in cited_sources:
                # Cite chip: speaker · MM:SS–MM:SS · title → navigate
                chip_text = f"{source.citation} [{source.marker}]"
                if st.button(
                    chip_text,
                    key=f"cite_{source.marker}",
                    use_container_width=False,
                ):
                    # Jump to segment
                    navigate_to_segment(
                        source.segment_ref,
                        highlight_query=question,
                    )

    except Exception as e:
        st.error(f"Error: {e}")
