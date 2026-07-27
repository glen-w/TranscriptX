"""Insights viewer — sectioned composition from layout profiles."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.blocks.rendering import render_block
from transcriptx.web.blocks.session_context import (
    build_context_from_session,
    load_active_layout,
)
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.components.run_scoped_page import (
    RunScopedPageConfig,
    RunScopedPageContext,
    render_run_scoped_page,
)
from transcriptx.web.insights_presentation import (
    GUIDED_ANALYSIS_SECTION_CAP,
    analysis_group_for_block,
    analysis_payload_has_user_content,
    clear_analysis_payload_cache,
    is_insights_guided,
    load_cached_analysis_json,
    order_analysis_placements,
)

INSIGHTS_SECTION_KEY = "insights_section"
INSIGHTS_SECTIONS = (
    ("summary", "Summary"),
    ("speakers", "Speakers"),
    ("actions", "Actions"),
    ("highlights", "Highlights"),
    ("analysis", "Analysis"),
)

_BLOCK_ARTIFACT = {
    "lexical_diversity_block": ("lexical_diversity", "_lexical_diversity.json"),
    "epistemic_markers_block": ("epistemic_markers", "_epistemic_markers.json"),
    "politeness_block": ("politeness", "_politeness.json"),
    "keyphrases_block": ("keyphrases", "_keyphrases.json"),
    "insights_contract": ("insights", "_insights.json"),
}

_INSIGHTS_CONFIG = RunScopedPageConfig(
    title="Insights",
    description=(
        "Structured analysis workspace for summaries, speakers, actions, "
        "highlights, and deeper analysis."
    ),
    empty_headline="Select a subject and run",
    empty_detail="Use the sidebar to choose a transcript or group, then pick a run.",
    primary_action=("Open Library", "Library"),
    secondary_action=("Run Analysis", "Run Analysis"),
)


def _render_section_nav() -> str:
    """Single coherent section control (segmented, radio fallback)."""
    labels = [label for _, label in INSIGHTS_SECTIONS]
    keys = [key for key, _ in INSIGHTS_SECTIONS]
    current = st.session_state.get(INSIGHTS_SECTION_KEY, "summary")
    if current not in keys:
        current = "summary"
        st.session_state[INSIGHTS_SECTION_KEY] = current
    try:
        choice = st.segmented_control(
            "Insights section",
            options=labels,
            default=dict(INSIGHTS_SECTIONS)[current],
            key="insights_section_control",
            label_visibility="collapsed",
        )
    except Exception:
        choice = st.radio(
            "Insights section",
            labels,
            index=keys.index(current),
            horizontal=True,
            key="insights_section_radio",
            label_visibility="collapsed",
        )
    selected_key = next(k for k, lab in INSIGHTS_SECTIONS if lab == choice)
    st.session_state[INSIGHTS_SECTION_KEY] = selected_key
    return selected_key


def _render_chrome() -> str:
    """Section nav only (Guided/Full presentation toggle removed)."""
    return _render_section_nav()


def _collect_analysis_provenance_targets(placements) -> list[tuple[str, str]]:
    """(module, json_suffix) for consolidated Data and provenance."""
    out: list[tuple[str, str]] = []
    for p in placements:
        hit = _BLOCK_ARTIFACT.get(getattr(p, "block_id", ""))
        if hit and hit not in out:
            out.append(hit)
    return out


def _placement_has_analysis_content(block_ctx, placement) -> bool:
    """Skip empty / missing optional analysis artifacts before counting Guided slots."""
    loader = getattr(getattr(block_ctx, "services", None), "content_loader", None)
    hit = _BLOCK_ARTIFACT.get(getattr(placement, "block_id", ""))
    if hit is None:
        return True
    module, suffix = hit
    payload = load_cached_analysis_json(loader, module, suffix)
    return analysis_payload_has_user_content(module, payload)


def _render_analysis_section(block_ctx, section_blocks) -> None:
    """Grouped analysis with Guided section cap and consolidated provenance."""
    from transcriptx.web.blocks.implementations.insights import (
        _render_view_raw_file_link,
    )

    clear_analysis_payload_cache()

    filtered = [
        p
        for p in section_blocks
        if getattr(p, "block_id", "") != "executive_summary"
    ]
    ordered = order_analysis_placements(filtered)
    guided = is_insights_guided()

    rendered_modules = 0
    last_group_key: str | None = None
    shown_placements: list = []

    def _emit(placement) -> None:
        nonlocal rendered_modules, last_group_key
        group = analysis_group_for_block(placement.block_id)
        group_key = group[0] if group else "other"
        group_title = group[1] if group else "Other analysis"
        if group_key != last_group_key:
            if last_group_key is not None or shown_placements:
                st.divider()
            st.markdown(f"### {group_title}")
            last_group_key = group_key
        elif shown_placements:
            st.divider()
        st.session_state["_insights_analysis_consolidating_provenance"] = True
        render_block(placement.block_id, block_ctx, placement)
        st.session_state["_insights_analysis_consolidating_provenance"] = False
        shown_placements.append(placement)
        rendered_modules += 1

    contentful = [
        p for p in ordered if _placement_has_analysis_content(block_ctx, p)
    ]
    emptyish = [p for p in ordered if p not in contentful]

    for placement in contentful:
        if guided and rendered_modules >= GUIDED_ANALYSIS_SECTION_CAP:
            break
        _emit(placement)

    if guided:
        remaining = max(0, len(contentful) - rendered_modules)
        if remaining:
            st.caption(
                f"{remaining} more analysis module"
                f"{'s' if remaining != 1 else ''} available in Full controls."
            )
    else:
        # Full controls: still show unavailable modules as quiet status (not Silent).
        for placement in emptyish:
            _emit(placement)

    targets = _collect_analysis_provenance_targets(shown_placements)
    if targets:
        with st.expander("Data and provenance", expanded=False):
            st.caption("Raw artifacts for the modules shown above.")
            for module, suffix in targets:
                _render_view_raw_file_link(
                    block_ctx,
                    module,
                    suffix,
                    link_key=f"insights_analysis_prov_{module}",
                )


@st.fragment
def _insights_sections_fragment(block_ctx, layout) -> None:
    """Section nav + block rendering; switching sections reruns only this fragment."""
    section = _render_chrome()

    if block_ctx is None:
        return

    page = layout.pages.get("insights") if layout is not None else None
    if page is None:
        st.warning("Active layout has no insights page.")
        return

    placements = [b.to_placement() for b in page.blocks]
    section_blocks = [
        p for p in placements if (p.section or "analysis") == section and p.visible
    ]
    # Layouts without section tags (v1 executive): show all on Summary only.
    if not any(p.section for p in placements):
        if section != "summary":
            st.info(
                "This layout does not define sections. Switch to Summary, or open Dashboard Builder."
            )
            return
        section_blocks = [p for p in placements if p.visible]

    if not section_blocks:
        st.info("No blocks for this section in the active layout.")
        return

    if section == "analysis":
        _render_analysis_section(block_ctx, section_blocks)
        return

    for index, placement in enumerate(section_blocks):
        if index > 0:
            st.divider()
        render_block(placement.block_id, block_ctx, placement)


def _render_insights_body(ctx: RunScopedPageContext) -> None:
    render_page_shell(
        "Insights",
        "Themes, summaries, speakers, actions, and deeper analysis.",
        badges=None,
        actions=None,
    )
    block_ctx = build_context_from_session(st.session_state)
    layout = load_active_layout(st.session_state) if block_ctx is not None else None
    _insights_sections_fragment(block_ctx, layout)


def render_insights() -> None:
    register_builtin_blocks()
    render_run_scoped_page(_INSIGHTS_CONFIG, render_body=_render_insights_body)
