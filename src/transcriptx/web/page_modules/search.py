"""Global search page for TranscriptX web UI."""

from __future__ import annotations

import html
import time
from typing import Dict, Iterable, List, Tuple

import streamlit as st

from transcriptx.web.db_utils import get_all_speakers
from transcriptx.web.models.search import SearchFilters, SearchResponse, SearchResult
from transcriptx.web.services.search_service import SearchService
from transcriptx.web.services.subject_service import SubjectService


def _render_highlighted_text(text: str, spans: List[Tuple[int, int]]) -> str:
    if not spans:
        return html.escape(text)
    spans = sorted(spans, key=lambda item: item[0])
    output: List[str] = []
    cursor = 0
    for start, end in spans:
        if start < cursor:
            continue
        output.append(html.escape(text[cursor:start]))
        output.append(f"<mark>{html.escape(text[start:end])}</mark>")
        cursor = end
    output.append(html.escape(text[cursor:]))
    return "".join(output)


def _dedupe_by_segment(results: Iterable[SearchResult]) -> List[SearchResult]:
    seen = set()
    deduped: List[SearchResult] = []
    for result in results:
        key = (
            result.session_slug,
            result.run_id,
            result.segment_index,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def _group_by_transcript(
    results: Iterable[SearchResult],
) -> Dict[Tuple[str, str], List[SearchResult]]:
    grouped: Dict[Tuple[str, str], List[SearchResult]] = {}
    for result in results:
        transcript_slug = (
            result.segment_ref.transcript_ref.transcript_slug
            or result.transcript_title
            or "Unknown transcript"
        )
        key = (result.session_slug, transcript_slug)
        grouped.setdefault(key, []).append(result)
    return grouped


def _render_results_section(
    title: str,
    results: List[SearchResult],
    total_found: int,
    total_shown: int,
    show_first_match_only: bool,
    count_label: str,
    highlight_query: str,
) -> None:
    st.subheader(title)
    if show_first_match_only:
        results = _dedupe_by_segment(results)
    grouped = _group_by_transcript(results)
    st.caption(f"Showing {total_shown} of {total_found} {count_label}")
    for (session_slug, transcript_slug), items in grouped.items():
        st.markdown(f"**{transcript_slug}**")
        st.caption(f"{session_slug}")
        for result in items:
            breadcrumb = (
                f"{result.session_slug} › {transcript_slug} › "
                f"{result.speaker_name} · {result.start_time:.1f}–{result.end_time:.1f}"
            )
            st.caption(breadcrumb)
            st.markdown(
                _render_highlighted_text(result.segment_text, result.match_spans),
                unsafe_allow_html=True,
            )
            if st.button(
                "Jump to segment",
                key=f"jump_{result.session_slug}_{result.run_id}_{result.segment_index}_{title}",
                width='content',
            ):
                from transcriptx.web.app import navigate_to_segment

                navigate_to_segment(result.segment_ref, highlight_query=highlight_query)
            st.divider()


def render_search() -> None:
    st.markdown('<div class="main-header">🔎 Global Search</div>', unsafe_allow_html=True)

    # Initialize session state for debouncing and caching
    if "global_search_last_change" not in st.session_state:
        st.session_state["global_search_last_change"] = time.time()
    if "global_search_last_query" not in st.session_state:
        st.session_state["global_search_last_query"] = ""
    if "global_search_last_searched_query" not in st.session_state:
        st.session_state["global_search_last_searched_query"] = None
    if "global_search_cached_response" not in st.session_state:
        st.session_state["global_search_cached_response"] = None
    if "global_search_cached_filters" not in st.session_state:
        st.session_state["global_search_cached_filters"] = None

    query = st.text_input("Search transcripts", key="global_search_query", placeholder="Type to search…")

    # Track query changes for debouncing
    current_time = time.time()
    query_changed = query != st.session_state["global_search_last_query"]
    
    if query_changed:
        st.session_state["global_search_last_change"] = current_time
        st.session_state["global_search_last_query"] = query
        # Clear cache when query changes
        st.session_state["global_search_last_searched_query"] = None
        st.session_state["global_search_cached_response"] = None

    # Show options immediately (before debounce check)
    scope = st.radio(
        "Search in",
        ["All transcripts", "Current transcript"],
        horizontal=True,
        key="global_search_scope",
    )
    enable_fuzzy = st.checkbox(
        "Enable fuzzy matching",
        value=True,
        key="global_search_fuzzy",
    )
    show_first_match_only = st.checkbox(
        "Show only first match per segment",
        value=True,
        key="global_search_first_match_only",
    )

    speaker_keys: List[str] = []
    try:
        speakers = get_all_speakers()
        if speakers:
            speaker_options = ["All speakers"] + [
                s.get("name", "Unknown") for s in speakers
            ]
            selected = st.selectbox(
                "Speakers",
                speaker_options,
                index=0,
                key="global_search_speaker",
            )
            if selected != "All speakers":
                speaker_keys = [selected]
    except Exception:
        st.caption("Speaker filters unavailable.")

    # Build filters to check if they changed
    session_slugs = None
    if scope == "Current transcript":
        subject = SubjectService.resolve_current_subject(st.session_state)
        if subject and subject.subject_type == "transcript":
            session_slugs = [subject.subject_id]
    filters = SearchFilters(speaker_keys=speaker_keys, session_slugs=session_slugs)
    
    # Check if filters changed (by comparing relevant fields)
    cached_filters = st.session_state.get("global_search_cached_filters")
    filters_changed = (
        cached_filters is None
        or cached_filters.speaker_keys != filters.speaker_keys
        or cached_filters.session_slugs != filters.session_slugs
    )
    if filters_changed:
        st.session_state["global_search_cached_filters"] = filters
        # Invalidate cache if filters changed and clear debounce
        st.session_state["global_search_last_searched_query"] = None
        st.session_state["global_search_cached_response"] = None
        st.session_state["global_search_last_change"] = 0  # Clear debounce on filter change

    # Check debounce: run search only after user pauses typing
    debounce_ms = 300
    time_since_change_ms = (current_time - st.session_state["global_search_last_change"]) * 1000
    is_within_debounce = time_since_change_ms < debounce_ms

    # Determine if we need to search (after debounce period)
    needs_search = (
        len(query) >= 3
        and not is_within_debounce
        and (
            st.session_state["global_search_last_searched_query"] != query
            or st.session_state["global_search_cached_response"] is None
            or filters_changed
        )
    )

    # When user has typed but we're still in debounce: show cached results if any,
    # then schedule a rerun after the remainder of the debounce so search runs once
    # they've stopped typing (Streamlit only reruns on widget interaction, so without
    # this we'd never rerun after pause).
    if is_within_debounce and len(query) >= 3 and query != st.session_state.get("global_search_last_searched_query"):
        # Show cached results while waiting (if available)
        cached_response = st.session_state.get("global_search_cached_response")
        if cached_response is not None and (cached_response.substring_results or cached_response.fuzzy_results):
            _render_results_section(
                "Matches",
                cached_response.substring_results,
                cached_response.total_found,
                cached_response.total_shown,
                show_first_match_only,
                "matches",
                query,
            )
            if cached_response.fuzzy_results:
                if cached_response.fuzzy_reason:
                    st.caption(f"Fuzzy matches because: {cached_response.fuzzy_reason}")
                _render_results_section(
                    "Fuzzy matches",
                    cached_response.fuzzy_results,
                    len(cached_response.fuzzy_results),
                    len(cached_response.fuzzy_results),
                    show_first_match_only,
                    "fuzzy matches",
                    query,
                )
        sleep_ms = debounce_ms - time_since_change_ms
        if sleep_ms > 10:  # avoid tiny sleeps
            time.sleep(sleep_ms / 1000.0)
        st.rerun()

    if len(query) < 3:
        st.info("Enter at least 3 characters to search.")
        return

    # Perform search if needed
    if needs_search:
        service = SearchService()
        with st.spinner("Searching transcripts..."):
            response = service.search_all_transcripts(query, filters, enable_fuzzy=enable_fuzzy)
        # Cache the results
        st.session_state["global_search_last_searched_query"] = query
        st.session_state["global_search_cached_response"] = response
    else:
        # Use cached response
        response = st.session_state["global_search_cached_response"]
        if response is None:
            st.info("No matches found.")
            return

    if not response.substring_results and not response.fuzzy_results:
        st.info("No matches found.")
        return

    _render_results_section(
        "Matches",
        response.substring_results,
        response.total_found,
        response.total_shown,
        show_first_match_only,
        "matches",
        query,
    )

    if response.fuzzy_results:
        if response.fuzzy_reason:
            st.caption(f"Fuzzy matches because: {response.fuzzy_reason}")
        _render_results_section(
            "Fuzzy matches",
            response.fuzzy_results,
            len(response.fuzzy_results),
            len(response.fuzzy_results),
            show_first_match_only,
            "fuzzy matches",
            query,
        )
