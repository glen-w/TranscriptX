"""Insights contract (themes, style markers, narrative) block."""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.group_content import (
    group_rollup_empty_hint,
    is_group_run,
    list_group_members,
    load_member_module_json,
    member_empty_hint,
    select_group_member,
)
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.components.module_run_prompt import render_module_required_hint

from transcriptx.web.blocks.implementations.insights_support import (
    _load_analysis_json,
    _loader,
    _render_view_raw_file_link,
)


def _insights_focus(placement: BlockPlacement | None) -> str:
    raw = "all"
    if placement is not None:
        raw = str(placement.params.get("focus", "all")).strip().lower()
    return raw if raw in {"all", "content", "style"} else "all"


def _insights_contract_title(placement: BlockPlacement | None, focus: str) -> str:
    defaults = {
        "all": "Content vs Style",
        "content": "Themes and ideas",
        "style": "Style markers",
    }
    if placement is None:
        return defaults[focus]
    if placement.title_override:
        return placement.title_override
    return str(placement.params.get("title", defaults[focus]))


def _quote_text_by_id(highlights: Dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(highlights, dict):
        return {}
    from transcriptx.core.analysis.highlights.post_process import (
        highlight_quote_text_by_id,
    )

    return highlight_quote_text_by_id(highlights)


def _render_theme_and_idea_lists(
    *,
    key_themes: list,
    recurring_ideas: list,
    theme_cap: int,
    idea_cap: int,
    guided: bool,
    quote_text_by_id: dict[str, str] | None = None,
) -> None:
    st.markdown("**Content terms**")
    shown = 0
    for row in key_themes:
        if not isinstance(row, dict):
            continue
        phrase = str(row.get("phrase") or "").strip()
        if not phrase:
            continue
        if guided:
            st.write(f"- {phrase}")
        else:
            total = float((row.get("score") or {}).get("total", 0.0))
            confidence = str(row.get("confidence") or "").strip()
            if confidence:
                st.write(f"- {phrase} ({total:.3f}, {confidence})")
            else:
                st.write(f"- {phrase} ({total:.3f})")
            if quote_text_by_id:
                evidence_ids = row.get("evidence_quote_ids") or []
                snippets: list[str] = []
                for qid in evidence_ids:
                    snippet = quote_text_by_id.get(str(qid), "").strip()
                    if snippet:
                        snippets.append(snippet)
                if snippets:
                    preview = snippets[0]
                    if len(preview) > 160:
                        preview = preview[:157].rstrip() + "…"
                    st.caption(f"Evidence: “{preview}”")
        shown += 1
        if shown >= theme_cap:
            break
    if shown == 0:
        st.caption("No key themes.")
    has_ideas = any(
        isinstance(row, dict) and str(row.get("phrase") or "").strip()
        for row in recurring_ideas
    )
    if has_ideas:
        st.markdown("**Recurring ideas**")
        shown_i = 0
        for row in recurring_ideas:
            if not isinstance(row, dict):
                continue
            phrase = str(row.get("phrase") or "").strip()
            if not phrase:
                continue
            if guided:
                st.write(f"- {phrase}")
            else:
                recurrence = float((row.get("score") or {}).get("recurrence", 0.0))
                st.write(f"- {phrase} (recurrence {recurrence:.3f})")
            shown_i += 1
            if shown_i >= idea_cap:
                break


def _render_style_indicator_list(
    style_rows: list[tuple[str, str]], *, guided: bool
) -> None:
    from transcriptx.web.insights_presentation import GUIDED_RANKED_ROW_CAP

    st.markdown("**Style indicators**")
    if style_rows:
        for label, value in style_rows[: GUIDED_RANKED_ROW_CAP if guided else 12]:
            st.write(f"- {label}: {value}")
    else:
        st.caption("No style indicators.")


def _style_detail_rows(style_markers: dict) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for key, value in style_markers.items():
        if isinstance(value, (int, float, str)):
            flat.append({"marker": key, "value": value})
        elif isinstance(value, dict):
            for sk, sv in value.items():
                flat.append({"marker": f"{key}.{sk}", "value": sv})
    return flat


def _render_insights_narrative(narrative_payload: Dict[str, Any] | None) -> None:
    if not isinstance(narrative_payload, dict):
        return
    text = str(narrative_payload.get("narrative") or "").strip()
    if not text:
        return
    from transcriptx.web.blocks.llm_presentation import (
        llm_surface_badges,
        render_badge_row,
    )

    st.markdown("**Theme narrative**")
    render_badge_row(llm_surface_badges())
    st.write(text)


def _render_insights_payload(
    insights: Dict[str, Any],
    *,
    focus: str = "all",
    display_cap: int | None = None,
    highlights: Dict[str, Any] | None = None,
    narrative_payload: Dict[str, Any] | None = None,
) -> None:
    from transcriptx.web.insights_presentation import (
        FULL_THEME_ROW_CAP,
        GUIDED_RANKED_ROW_CAP,
        MODULE_PLAIN_DESCRIPTIONS,
        is_insights_guided,
    )
    from transcriptx.core.utils.config import get_config

    guided = is_insights_guided()
    captions = {
        "all": MODULE_PLAIN_DESCRIPTIONS.get("insights", ""),
        "content": ("Content themes and recurring ideas from the transcript wording."),
        "style": ("Style-of-speech markers kept separate from content themes."),
    }
    st.caption(captions.get(focus, captions["all"]))
    key_themes = insights.get("key_themes") or []
    recurring_ideas = insights.get("recurring_ideas") or []
    style_markers = insights.get("style_markers") or {}
    if not isinstance(key_themes, list):
        key_themes = []
    if not isinstance(recurring_ideas, list):
        recurring_ideas = []
    if not isinstance(style_markers, dict):
        style_markers = {}

    status = str(insights.get("status") or "ok")
    try:
        insights_cfg = get_config().analysis.insights
        overview_cap = int(insights_cfg.counts.overview_theme_cap)
        full_cap = int(insights_cfg.counts.top_themes)
    except Exception:
        overview_cap = 5
        full_cap = FULL_THEME_ROW_CAP
    if display_cap is not None:
        theme_cap = int(display_cap)
    elif guided:
        theme_cap = GUIDED_RANKED_ROW_CAP
    else:
        # Insights Full default; Overview callers should pass overview_theme_cap.
        theme_cap = full_cap if full_cap > 0 else overview_cap
    idea_cap = theme_cap
    show_content = focus in {"all", "content"}
    show_style = focus in {"all", "style"}
    quote_text_by_id = _quote_text_by_id(highlights) if show_content else {}

    content_abstained = show_content and status == "insufficient_signal"
    if content_abstained:
        st.info("Not enough clear content themes in this transcript.")
        key_themes = []
        recurring_ideas = []

    has_themes = any(
        str(row.get("phrase") or "").strip()
        for row in key_themes
        if isinstance(row, dict)
    )
    has_ideas = any(
        str(row.get("phrase") or "").strip()
        for row in recurring_ideas
        if isinstance(row, dict)
    )
    style_rows: list[tuple[str, str]] = []
    if isinstance(style_markers, dict):
        for key, value in style_markers.items():
            if value is None or value == "" or value == {} or value == []:
                continue
            if isinstance(value, (int, float)):
                style_rows.append(
                    (str(key).replace("_", " ").title(), f"{float(value):.3f}")
                )
            elif isinstance(value, str) and value.strip():
                style_rows.append((str(key).replace("_", " ").title(), value.strip()))
            elif isinstance(value, dict):
                # Flatten one level of labelled counts — never dump raw dict text.
                for sub_k, sub_v in list(value.items())[:5]:
                    if isinstance(sub_v, (int, float)):
                        style_rows.append(
                            (
                                f"{str(key).replace('_', ' ').title()}: "
                                f"{str(sub_k).replace('_', ' ')}",
                                f"{float(sub_v):.3f}",
                            )
                        )
            if len(style_rows) >= (GUIDED_RANKED_ROW_CAP if guided else 12):
                break

    content_empty = show_content and not has_themes and not has_ideas
    style_empty = show_style and not style_rows
    if (show_content or show_style) and content_empty and style_empty:
        if focus == "content":
            if status != "insufficient_signal":
                st.info("No meaningful themes or recurring ideas for this transcript.")
        elif focus == "style":
            st.info("No style indicators.")
        else:
            st.info("No meaningful content-vs-style rows for this transcript.")
        return

    if content_abstained and focus == "content":
        return
    if content_abstained and focus == "all" and style_empty:
        return

    if show_content and show_style:
        col_a, col_b = st.columns(2)
        with col_a:
            if not content_abstained:
                _render_theme_and_idea_lists(
                    key_themes=key_themes,
                    recurring_ideas=recurring_ideas,
                    theme_cap=theme_cap,
                    idea_cap=idea_cap,
                    guided=guided,
                    quote_text_by_id=quote_text_by_id,
                )
        with col_b:
            _render_style_indicator_list(style_rows, guided=guided)
    elif show_content:
        if not content_abstained:
            _render_theme_and_idea_lists(
                key_themes=key_themes,
                recurring_ideas=recurring_ideas,
                theme_cap=theme_cap,
                idea_cap=idea_cap,
                guided=guided,
                quote_text_by_id=quote_text_by_id,
            )
    elif show_style:
        _render_style_indicator_list(style_rows, guided=guided)

    if show_content and not content_abstained and quote_text_by_id:
        st.caption("More notable passages are listed under **Insights → Highlights**.")
    if show_content and not content_abstained:
        _render_insights_narrative(narrative_payload)

    details_needed = False
    if show_content and (
        len(key_themes) > theme_cap or len(recurring_ideas) > idea_cap
    ):
        details_needed = True
    if show_style and isinstance(style_markers, dict) and style_markers:
        details_needed = True
    if not details_needed:
        return

    with st.expander("Explore details", expanded=False):
        if show_content and key_themes:
            st.caption("All key themes")
            rows = []
            for row in key_themes[:40]:
                if not isinstance(row, dict):
                    continue
                rows.append(
                    {
                        "phrase": row.get("phrase"),
                        "score": (row.get("score") or {}).get("total"),
                    }
                )
            if rows:
                st.dataframe(rows, width="stretch", hide_index=True)
        if show_content and recurring_ideas:
            st.caption("All recurring ideas")
            rows = []
            for row in recurring_ideas[:40]:
                if not isinstance(row, dict):
                    continue
                rows.append(
                    {
                        "phrase": row.get("phrase"),
                        "recurrence": (row.get("score") or {}).get("recurrence"),
                    }
                )
            if rows:
                st.dataframe(rows, width="stretch", hide_index=True)
        if show_style and isinstance(style_markers, dict) and style_markers:
            st.caption("Style markers" if guided else "Style markers (full)")
            flat = _style_detail_rows(style_markers)
            if flat:
                st.dataframe(flat, width="stretch", hide_index=True)


def _render_insight_rows_rollup(
    rows: list[Dict[str, Any]], *, focus: str = "all"
) -> None:
    show_content = focus in {"all", "content"}
    show_moments = focus in {"all", "content"}
    if focus == "style":
        st.caption("Style markers are shown per session below.")
        return
    themes = [r for r in rows if r.get("kind") == "key_theme"]
    ideas = [r for r in rows if r.get("kind") == "recurring_idea"]
    moments = [r for r in rows if r.get("kind") == "notable_moment"]
    if show_content:
        st.caption("Group rollup — key themes")
        if not themes:
            st.write("No key themes across sessions.")
        for row in themes[:12]:
            text = str(row.get("text") or "").strip()
            score = row.get("score")
            suffix = f" ({float(score):.3f})" if isinstance(score, (int, float)) else ""
            session = row.get("order_index")
            prefix = f"[s{int(session) + 1}] " if session is not None else ""
            if text:
                st.write(f"- {prefix}{text}{suffix}")
        st.caption("Group rollup — recurring ideas")
        if ideas:
            for row in ideas[:12]:
                text = str(row.get("text") or "").strip()
                if text:
                    st.write(f"- {text}")
    if show_moments and moments:
        st.caption("Group rollup — notable moments")
        for row in moments[:8]:
            text = str(row.get("text") or "").strip()
            if text:
                st.write(f"- {text[:200]}")


def render_insights_contract(ctx: BlockContext, placement: BlockPlacement) -> None:
    focus = _insights_focus(placement)
    title = _insights_contract_title(placement, focus)
    if st.session_state.get("_insights_analysis_consolidating_provenance"):
        st.markdown(f"#### {title}")
    else:
        st.subheader(title)
    loader = _loader(ctx)
    run_root = ctx.run_root
    focus_key = focus.replace("-", "_")
    if loader is None and run_root is None:
        render_module_required_hint(
            "Run the `insights` module to populate this view.",
            key=f"insights_no_loader_{focus_key}",
            ctx=ctx,
        )
        return

    if run_root is not None and is_group_run(run_root):
        from transcriptx.web.blocks.group_content import load_group_row_bundle

        bundle = load_group_row_bundle(run_root, "insights", "insight_rows")
        rows = bundle["content_rows"]
        session_rows = bundle["session_rows"]
        if focus != "style" and session_rows:
            st.caption("Group rollup — per-session insight counts")
            st.dataframe(session_rows, width="stretch", hide_index=True)
        if rows:
            _render_insight_rows_rollup(rows, focus=focus)
        elif focus != "style" and not session_rows:
            st.info(group_rollup_empty_hint("insights", content_name="insight_rows"))
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(
            members, key=f"insights_session_select_{focus_key}"
        )
        if member is None:
            st.caption(member_empty_hint("insights"))
            return
        insights = load_member_module_json(loader, member, "insights", "_insights.json")
        if not insights:
            st.info(member_empty_hint("insights"))
            return
        from transcriptx.web.insights_presentation import resolve_insights_display_cap

        _render_insights_payload(
            insights,
            focus=focus,
            display_cap=resolve_insights_display_cap(placement),
        )
        _render_view_raw_file_link(
            ctx,
            "insights",
            "_insights.json",
            link_key=f"insights_member_raw_{focus_key}",
            storage_root=member.storage_root,
        )
        return

    if loader is None:
        render_module_required_hint(
            "Run the `insights` module to populate this view.",
            key=f"insights_no_loader_{focus_key}",
            ctx=ctx,
        )
        return
    insights = _load_analysis_json(loader, "insights", "_insights.json")
    if not insights:
        render_module_required_hint(
            "Run the `insights` module to populate this view.",
            key=f"insights_empty_{focus_key}",
            ctx=ctx,
        )
        return
    if focus in {"all", "content"}:
        eligibility = _load_analysis_json(
            loader, "insight_eligibility", "_insight_eligibility.json"
        )
        highlights = _load_analysis_json(loader, "highlights", "_highlights.json")
        if eligibility is None or highlights is None:
            themes = insights.get("key_themes") or []
            ideas = insights.get("recurring_ideas") or []
            has_content = any(
                isinstance(row, dict) and str(row.get("phrase") or "").strip()
                for row in list(themes) + list(ideas)
            )
            if not has_content:
                st.info(
                    "Content themes need Insight eligibility and Highlights in this run."
                )
                if focus == "content":
                    _render_view_raw_file_link(
                        ctx,
                        "insights",
                        "_insights.json",
                        link_key=f"insights_partial_raw_{focus_key}",
                    )
                    return
    from transcriptx.web.insights_presentation import resolve_insights_display_cap

    highlights_payload = _load_analysis_json(loader, "highlights", "_highlights.json")
    narrative_payload = _load_analysis_json(
        loader, "insights_narrative", "_insights_narrative.json"
    )
    _render_insights_payload(
        insights,
        focus=focus,
        display_cap=resolve_insights_display_cap(placement),
        highlights=highlights_payload,
        narrative_payload=narrative_payload,
    )
