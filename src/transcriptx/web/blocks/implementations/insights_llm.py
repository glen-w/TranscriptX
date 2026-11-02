"""LLM summary, speaker summary, action items, and executive Insights blocks."""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.group_content import (
    group_rollup_empty_hint,
    is_group_run,
    list_group_members,
    load_group_blob,
    load_group_content_rows,
    load_member_module_json,
    load_member_module_text,
    member_empty_hint,
    select_group_member,
)
from transcriptx.core.llm_feedback.models import FeedbackSurface
from transcriptx.web.blocks.llm_presentation import (
    cleaned_llm_output_text,
    llm_surface_badges,
    render_badge_row,
    render_badge_row_with_feedback,
    render_markdown_without_heading_or_provenance,
    resolve_artifact_rel_path,
    strip_commitments_section,
)
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.components.module_run_prompt import render_module_required_hint

from transcriptx.web.blocks.implementations.insights_support import (
    _loader,
    _module_failure_hint,
    _render_quiet_module_empty,
    _render_view_raw_file_link,
)


def _render_executive_summary_body(
    summary: Dict[str, Any] | None, md: str | None
) -> bool:
    if md:
        st.markdown(strip_commitments_section(md))
        return True
    if summary:
        display = (
            {k: v for k, v in summary.items() if k != "commitments"}
            if isinstance(summary, dict)
            else summary
        )
        st.json(display)
        return True
    return False


def _render_commitments_from_summary(summary: Dict[str, Any]) -> bool:
    commitments = (summary.get("commitments") or {}).get("items", [])
    if not commitments:
        return False
    st.subheader("Commitments / Next steps")
    rows = [
        {
            "owner": item.get("owner_display", ""),
            "action": item.get("action", ""),
            "start": item.get("timestamp", {}).get("start", 0.0),
            "end": item.get("timestamp", {}).get("end", 0.0),
        }
        for item in commitments
        if isinstance(item, dict)
    ]
    if not rows:
        return False
    st.dataframe(rows, width="stretch")
    return True


def render_executive_summary(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("Executive Summary")
    loader = _loader(ctx)
    run_root = ctx.run_root
    if loader is None and run_root is None:
        render_module_required_hint(
            "Run the `summary` module to populate this view.",
            key="summary_no_loader",
            ctx=ctx,
        )
        return

    if run_root is not None and is_group_run(run_root):
        blob = load_group_blob(run_root, "summary", "summary")
        summaries = (blob or {}).get("summaries") if isinstance(blob, dict) else None
        if isinstance(summaries, list) and summaries:
            st.caption("Group rollup — collected session summaries")
            for entry in summaries:
                if not isinstance(entry, dict):
                    continue
                order = entry.get("order_index")
                label = f"Session {int(order) + 1}" if order is not None else "Session"
                with st.expander(label, expanded=len(summaries) == 1):
                    text = entry.get("summary") or entry.get("executive_summary")
                    if text:
                        st.markdown(str(text))
                    else:
                        display = {k: v for k, v in entry.items() if k != "commitments"}
                        st.json(display)
        else:
            st.info(group_rollup_empty_hint("summary", content_name="summary.json"))
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key="exec_summary_session_select")
        if member is None:
            return
        summary = load_member_module_json(loader, member, "summary", "_summary.json")
        md = load_member_module_text(loader, member, "summary", "_summary.md")
        if not _render_executive_summary_body(summary, md):
            st.info(member_empty_hint("summary"))
            return
        _render_view_raw_file_link(
            ctx,
            "summary",
            "_summary.json",
            link_key="exec_member_raw",
            storage_root=member.storage_root,
        )
        return

    if loader is None:
        render_module_required_hint(
            "Run the `summary` module to populate this view.",
            key="summary_no_loader",
            ctx=ctx,
        )
        return
    summary = loader.load_json("summary", "_summary.json")
    md = loader.load_text("summary", "_summary.md")
    if not _render_executive_summary_body(summary, md):
        render_module_required_hint(
            "Run the `summary` module to populate this view.",
            key="summary_empty",
            ctx=ctx,
        )
        return
    _render_view_raw_file_link(
        ctx, "summary", "_summary.json", link_key="exec_view_raw"
    )


def render_commitments_table(ctx: BlockContext, _placement: BlockPlacement) -> None:
    loader = _loader(ctx)
    run_root = ctx.run_root
    if loader is None and run_root is None:
        return

    if run_root is not None and is_group_run(run_root):
        blob = load_group_blob(run_root, "summary", "summary")
        summaries = (blob or {}).get("summaries") if isinstance(blob, dict) else None
        collected: list[Dict[str, Any]] = []
        if isinstance(summaries, list):
            for entry in summaries:
                if not isinstance(entry, dict):
                    continue
                items = (entry.get("commitments") or {}).get("items") or []
                order = entry.get("order_index")
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    collected.append(
                        {
                            "session": (
                                f"s{int(order) + 1}" if order is not None else ""
                            ),
                            "owner": item.get("owner_display", ""),
                            "action": item.get("action", ""),
                            "start": item.get("timestamp", {}).get("start", 0.0),
                            "end": item.get("timestamp", {}).get("end", 0.0),
                        }
                    )
        if collected:
            st.subheader("Commitments / Next steps")
            st.caption("Group rollup")
            st.dataframe(collected, width="stretch")
        members = list_group_members(run_root)
        member = select_group_member(members, key="commitments_session_select")
        if member is None:
            return
        summary = load_member_module_json(loader, member, "summary", "_summary.json")
        if summary:
            st.caption(f"Per session — {member.label}")
            _render_commitments_from_summary(summary)
        return

    if loader is None:
        return
    summary = loader.load_json("summary", "_summary.json")
    if not summary:
        return
    _render_commitments_from_summary(summary)


def render_llm_summary_block(ctx: BlockContext, placement: BlockPlacement) -> None:
    module = str(placement.params.get("module", "llm_summary"))
    title = placement.title_override or str(
        placement.params.get("title", "LLM Transcript Summary")
    )
    artifact_stem = str(placement.params.get("artifact_stem", "_llm_summary"))
    text_field = str(placement.params.get("text_field", "summary"))
    empty_hint = str(
        placement.params.get(
            "empty_hint",
            f"Run the `{module}` module (with LLM enabled) to populate this view.",
        )
    )
    instance_id = placement.params.get("instance_id")
    inst = str(instance_id) if instance_id else None

    st.subheader(title)
    loader = _loader(ctx)
    run_root = ctx.run_root
    if run_root is None:
        render_module_required_hint(empty_hint, key=f"llm_{module}_no_loader", ctx=ctx)
        return

    if is_group_run(run_root) and module in {"llm_summary", "narrative_summary"}:
        from transcriptx.web.summary_precedence import resolve_primary_summary

        result = resolve_primary_summary(
            loader, run_root=run_root, run_results=ctx.run_results
        )
        if result.primary and result.primary.available:
            st.caption("Group rollup — cross-session synthesis")
            if result.primary.markdown:
                st.markdown(result.primary.markdown)
            elif result.primary.payload and result.primary.payload.get(
                result.primary.text_field
            ):
                st.markdown(str(result.primary.payload[result.primary.text_field]))
            elif result.primary.payload:
                st.json(result.primary.payload)
        else:
            blob = load_group_blob(run_root, module, module)
            summaries = (
                (blob or {}).get("summaries") if isinstance(blob, dict) else None
            )
            if isinstance(summaries, list) and summaries:
                st.caption("Group rollup — collected member summaries")
                for entry in summaries:
                    if not isinstance(entry, dict):
                        continue
                    order = entry.get("order_index")
                    label = (
                        f"Session {int(order) + 1}" if order is not None else "Session"
                    )
                    with st.expander(label, expanded=False):
                        text = entry.get(text_field) or entry.get("summary")
                        if text:
                            st.markdown(str(text))
                        else:
                            st.json(entry)
            else:
                st.info(result.unavailable_message)
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key=f"llm_{module}_session_select")
        if member is None:
            return
        payload = load_member_module_json(
            loader, member, module, f"{artifact_stem}.json"
        )
        md = load_member_module_text(loader, member, module, f"{artifact_stem}.md")
        if md:
            st.markdown(md)
        elif payload and payload.get(text_field):
            st.markdown(str(payload[text_field]))
        elif payload:
            st.json(payload)
        else:
            st.info(member_empty_hint(module))
        return

    if loader is None:
        render_module_required_hint(empty_hint, key=f"llm_{module}_no_loader", ctx=ctx)
        return

    failure_hint = _module_failure_hint(run_root, module)
    payload = loader.load_json(module, f"{artifact_stem}.json", instance_id=inst)
    md = loader.load_text(module, f"{artifact_stem}.md", instance_id=inst)
    if not md and not (payload and (payload.get(text_field) or payload)):
        _render_quiet_module_empty(
            label=title,
            run_root=run_root,
            module=module,
            empty_hint=empty_hint if not failure_hint else empty_hint,
            ctx=ctx,
            key=f"llm_{module}_{inst or 'default'}",
        )
        return

    rated = (
        cleaned_llm_output_text(md)
        if md
        else str((payload or {}).get(text_field) or "")
    )
    rel = resolve_artifact_rel_path(
        loader, module, f"{artifact_stem}.md", instance_id=inst
    ) or resolve_artifact_rel_path(
        loader,
        module,
        f"{artifact_stem}.json",
        kind="data_json",
        instance_id=inst,
    )
    render_badge_row_with_feedback(
        llm_surface_badges((payload or {}).get("provenance") if payload else None),
        ctx=ctx,
        surface=FeedbackSurface.INSIGHTS_BLOCK,
        block_id=placement.block_id,
        module=module,
        artifact_rel_path=rel,
        output_text=rated,
        provenance=(payload or {}).get("provenance") if payload else None,
        placement_id=placement.placement_id,
        widget_key=f"fb_sum_{placement.placement_id}_{inst or 'default'}",
    )
    if md:
        st.markdown(md)
    elif payload and payload.get(text_field):
        st.markdown(str(payload[text_field]))
    elif payload:
        st.json(payload)
    suffix = f"{artifact_stem}.json"
    _render_view_raw_file_link(
        ctx, module, suffix, link_key=f"llm_raw_{module}_{inst or 'default'}"
    )
    prov = (payload or {}).get("provenance") or {}
    if not prov:
        return
    with st.expander("Generation details"):
        model = prov.get("model")
        provider = prov.get("provider")
        if model:
            st.write(f"Model: {model}")
        if provider:
            st.write(f"Provider: {provider}")
        if prov.get("truncated"):
            st.caption("Input was truncated to fit the model context window.")


def _safe_speaker_artifact_token(speaker: str) -> str:
    return str(speaker).replace(" ", "_").replace("/", "_")


def render_llm_speaker_summary_block(
    ctx: BlockContext, placement: BlockPlacement
) -> None:
    module = "llm_speaker_summary"
    title = placement.title_override or str(
        placement.params.get("title", "Per-Speaker LLM Summaries")
    )
    empty_hint = str(
        placement.params.get(
            "empty_hint",
            "Run the `llm_speaker_summary` module (with LLM enabled and named "
            "speakers) to populate this view.",
        )
    )

    st.subheader(title)
    loader = _loader(ctx)
    run_root = ctx.run_root
    if run_root is None:
        render_module_required_hint(
            empty_hint, key="llm_speaker_summary_no_loader", ctx=ctx
        )
        return

    # Group runs: committed cross-session speaker index via central resolver.
    from transcriptx.core.analysis.group_llm_synthesis.resolve import (
        ResolverCache,
        load_group_speaker_index,
        load_group_speaker_summary,
        load_text_under_generation,
    )

    if is_group_run(run_root):
        cache = ResolverCache()
        index_payload = load_group_speaker_index(run_root, cache=cache)
        if index_payload:
            speakers = index_payload.get("speakers") or []
            st.caption("Cross-session Per-Speaker Summaries")
            for entry in speakers:
                if not isinstance(entry, dict):
                    continue
                speaker = str(
                    entry.get("display_name") or entry.get("canonical_speaker_id") or ""
                )
                status = str(entry.get("status") or "")
                if not speaker:
                    continue
                with st.expander(speaker, expanded=len(speakers) == 1):
                    if status != "success":
                        code = entry.get("error_code")
                        message = (
                            entry.get("error_message_safe") or "Summary unavailable"
                        )
                        detail = f"[{code}] {message}" if code else message
                        st.warning(detail)
                        continue
                    rel_json = str(entry.get("rel_json") or "")
                    rel_md = str(entry.get("rel_md") or "")
                    md = (
                        load_text_under_generation(run_root, rel_md, cache=cache)
                        if rel_md
                        else None
                    )
                    payload = (
                        load_group_speaker_summary(run_root, rel_json, cache=cache)
                        if rel_json
                        else None
                    )
                    render_badge_row(
                        llm_surface_badges(
                            (payload or {}).get("provenance") if payload else None
                        )
                    )
                    if md:
                        render_markdown_without_heading_or_provenance(md)
                    elif payload and payload.get("summary"):
                        st.markdown(str(payload["summary"]))
                    elif payload:
                        st.json(payload)
                    else:
                        st.caption("Artifact missing for this speaker.")
        else:
            st.info(
                "Cross-session per-speaker summaries unavailable. "
                "Browse a member session below if member artifacts exist."
            )
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key="llm_speaker_summary_session_select")
        if member is None:
            return
        index_payload = load_member_module_json(
            loader, member, module, "_llm_speaker_summary_index.json"
        )
        if not index_payload:
            st.info(member_empty_hint(module))
            return
        speakers = index_payload.get("speakers") or []
        for entry in speakers:
            speaker = str(entry.get("speaker", "") or "")
            status = str(entry.get("status", "") or "")
            if not speaker:
                continue
            safe = _safe_speaker_artifact_token(speaker)
            suffix_json = f"_{safe}_llm_speaker_summary.json"
            suffix_md = f"_{safe}_llm_speaker_summary.md"
            with st.expander(speaker, expanded=len(speakers) == 1):
                if status != "success":
                    code = entry.get("error_code")
                    message = entry.get("error_message") or "Summary generation failed"
                    detail = f"[{code}] {message}" if code else message
                    st.warning(detail)
                    continue
                md = load_member_module_text(loader, member, module, suffix_md)
                payload = load_member_module_json(loader, member, module, suffix_json)
                render_badge_row(
                    llm_surface_badges(
                        (payload or {}).get("provenance") if payload else None
                    )
                )
                if md:
                    render_markdown_without_heading_or_provenance(md)
                elif payload and payload.get("summary"):
                    st.markdown(str(payload["summary"]))
                elif payload:
                    st.json(payload)
                else:
                    st.caption("Artifact missing for this speaker.")
        return

    if loader is None:
        render_module_required_hint(
            empty_hint, key="llm_speaker_summary_no_loader", ctx=ctx
        )
        return

    index_payload = loader.load_json(module, "_llm_speaker_summary_index.json")
    if not index_payload:
        _render_quiet_module_empty(
            label="Per-speaker summaries",
            run_root=run_root,
            module=module,
            empty_hint=empty_hint,
            ctx=ctx,
            key="llm_speaker_summary_index",
        )
        from transcriptx.web.blocks.implementations.custom_qa_presentation import (
            render_speaker_custom_qa_fallback,
        )

        render_speaker_custom_qa_fallback(run_root)
        return

    speakers = index_payload.get("speakers") or []
    if not speakers:
        _render_quiet_module_empty(
            label="Per-speaker summaries",
            run_root=run_root,
            module=module,
            empty_hint=empty_hint,
            ctx=ctx,
            key="llm_speaker_summary_speakers",
        )
        from transcriptx.web.blocks.implementations.custom_qa_presentation import (
            render_speaker_custom_qa_fallback,
        )

        render_speaker_custom_qa_fallback(run_root)
        return

    for entry in speakers:
        speaker = str(entry.get("speaker", "") or "")
        status = str(entry.get("status", "") or "")
        if not speaker:
            continue
        safe = _safe_speaker_artifact_token(speaker)
        suffix_json = f"_{safe}_llm_speaker_summary.json"
        suffix_md = f"_{safe}_llm_speaker_summary.md"
        with st.expander(speaker, expanded=len(speakers) == 1):
            if status != "success":
                code = entry.get("error_code")
                message = entry.get("error_message") or "Summary generation failed"
                detail = f"[{code}] {message}" if code else message
                st.warning(detail)
                continue
            md = loader.load_text(module, suffix_md)
            payload = loader.load_json(module, suffix_json)
            rated = (
                cleaned_llm_output_text(md)
                if md
                else str((payload or {}).get("summary") or "")
            )
            rel = resolve_artifact_rel_path(
                loader, module, suffix_md
            ) or resolve_artifact_rel_path(
                loader, module, suffix_json, kind="data_json"
            )
            render_badge_row_with_feedback(
                llm_surface_badges(
                    (payload or {}).get("provenance") if payload else None
                ),
                ctx=ctx,
                surface=FeedbackSurface.INSIGHTS_BLOCK,
                block_id=placement.block_id,
                module=module,
                artifact_rel_path=rel,
                output_text=rated,
                provenance=(payload or {}).get("provenance") if payload else None,
                placement_id=placement.placement_id,
                widget_key=f"fb_spk_{placement.placement_id}_{safe}",
            )
            if md:
                render_markdown_without_heading_or_provenance(md)
            elif payload and payload.get("summary"):
                st.markdown(str(payload["summary"]))
            elif payload:
                st.json(payload)
            else:
                st.caption("Artifact missing for this speaker.")
                continue
            speaker_key = str(
                (payload or {}).get("speaker_key")
                or entry.get("speaker_key")
                or speaker
            )
            from transcriptx.web.blocks.implementations.custom_qa_presentation import (
                render_speaker_custom_qa,
            )

            render_speaker_custom_qa(
                run_root,
                speaker_key=speaker_key,
                key_prefix=f"spk_{safe}",
            )
            _render_view_raw_file_link(
                ctx,
                module,
                suffix_json,
                link_key=f"llm_speaker_raw_{safe}",
            )
            prov = (payload or {}).get("provenance") or {}
            if prov.get("truncated"):
                st.caption("Input was truncated to fit the model context window.")

    _render_view_raw_file_link(
        ctx,
        module,
        "_llm_speaker_summary_index.json",
        link_key="llm_speaker_index_raw",
    )


def _render_action_items_payload(
    payload: Dict[str, Any] | None, md: str | None
) -> bool:
    from transcriptx.core.analysis.llm_support.action_items_contract import (
        EMPTY_EXTRACTS_MESSAGE,
        HUMAN_REVIEW_BANNER,
        RECORD_TYPE_LABELS,
        is_v1_action_items_payload,
    )
    from transcriptx.core.analysis.llm_support.action_items_guidance import (
        empty_extracts_user_warning,
        truncated_output_user_warning,
    )

    if payload is not None and is_v1_action_items_payload(payload):
        st.caption(
            "Unstamped legacy action items (epoch-1 live path uses stamped schema)."
        )
        st.caption(HUMAN_REVIEW_BANNER)
    else:
        st.caption(HUMAN_REVIEW_BANNER)

    diagnostics = (
        (payload or {}).get("diagnostics") if isinstance(payload, dict) else None
    )
    trunc_warn = truncated_output_user_warning(diagnostics)
    if trunc_warn:
        st.warning(trunc_warn)
    empty_warn = empty_extracts_user_warning(diagnostics)
    if empty_warn:
        st.warning(empty_warn)

    if md:
        render_markdown_without_heading_or_provenance(md)
        return True
    if payload and isinstance(payload.get("items"), list):
        items = payload["items"]
        if not items:
            if not empty_warn:
                st.caption(EMPTY_EXTRACTS_MESSAGE)
            return True
        rows = [
            {
                "type": RECORD_TYPE_LABELS.get(
                    str(item.get("record_type") or "action_item"),
                    str(item.get("record_type") or "action_item"),
                ),
                "text": item.get("text", ""),
                "status": item.get("status", ""),
                "owner": item.get("owner") or "—",
                "deadline": item.get("deadline") or "—",
                "quote": item.get("quote") or "",
                "confidence": item.get("confidence"),
            }
            for item in items
            if isinstance(item, dict)
        ]
        st.dataframe(rows, width="stretch", hide_index=True)
        return True
    if payload:
        st.json(payload)
        return True
    return False


def _render_action_item_rows_rollup(rows: list[Dict[str, Any]]) -> None:
    from transcriptx.core.analysis.llm_support.action_items_contract import (
        HUMAN_REVIEW_BANNER,
        RECORD_TYPE_LABELS,
    )

    st.caption("Group rollup — meeting extracts across sessions")
    st.caption(HUMAN_REVIEW_BANNER)
    display = [
        {
            "session": (
                f"s{int(row['order_index']) + 1}"
                if row.get("order_index") is not None
                else ""
            ),
            "type": RECORD_TYPE_LABELS.get(
                str(row.get("record_type") or "action_item"),
                str(row.get("record_type") or "action_item"),
            ),
            "text": row.get("text") or "",
            "owner": row.get("owner") or "—",
            "deadline": row.get("deadline") or "—",
            "status": row.get("status") or "",
            "confidence": row.get("confidence"),
        }
        for row in rows
        if str(row.get("text") or "").strip()
    ]
    if not display:
        st.write("No meeting extracts.")
        return
    st.dataframe(display[:40], width="stretch", hide_index=True)
    if len(display) > 40:
        st.caption(f"+{len(display) - 40} more in Data")


def render_llm_action_items_block(ctx: BlockContext, placement: BlockPlacement) -> None:
    from transcriptx.core.analysis.llm_support.action_items_contract import (
        TITLE_MEETING_EXTRACTS,
    )

    module = "llm_action_items"
    title = placement.title_override or str(
        placement.params.get("title", TITLE_MEETING_EXTRACTS)
    )
    empty_hint = str(
        placement.params.get(
            "empty_hint",
            "Run the `llm_action_items` module (with LLM enabled) to populate this view.",
        )
    )
    artifact_stem = str(placement.params.get("artifact_stem", "_llm_action_items"))

    st.subheader(title)
    loader = _loader(ctx)
    run_root = ctx.run_root
    if run_root is None:
        render_module_required_hint(
            empty_hint, key="llm_action_items_no_loader", ctx=ctx
        )
        return

    if is_group_run(run_root):
        rows = load_group_content_rows(run_root, module, "action_item_rows")
        if rows:
            _render_action_item_rows_rollup(rows)
        else:
            st.info(group_rollup_empty_hint(module, content_name="action_item_rows"))
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key="llm_action_items_session_select")
        if member is None:
            return
        payload = load_member_module_json(
            loader, member, module, f"{artifact_stem}.json"
        )
        md = load_member_module_text(loader, member, module, f"{artifact_stem}.md")
        render_badge_row(
            llm_surface_badges((payload or {}).get("provenance") if payload else None)
        )
        if not _render_action_items_payload(payload, md):
            st.info(member_empty_hint(module))
            return
        _render_view_raw_file_link(
            ctx,
            module,
            f"{artifact_stem}.json",
            link_key="llm_action_items_member_raw",
            storage_root=member.storage_root,
        )
        return

    if loader is None:
        render_module_required_hint(
            empty_hint, key="llm_action_items_no_loader", ctx=ctx
        )
        return

    payload = loader.load_json(module, f"{artifact_stem}.json")
    md = loader.load_text(module, f"{artifact_stem}.md")
    rated = cleaned_llm_output_text(md) if md else ""
    if not rated and isinstance(payload, dict):
        items = payload.get("items") or []
        if isinstance(items, list):
            rated = "\n".join(
                str(it.get("text") or "")
                for it in items
                if isinstance(it, dict) and it.get("text")
            )
    rel = resolve_artifact_rel_path(
        loader, module, f"{artifact_stem}.md"
    ) or resolve_artifact_rel_path(
        loader, module, f"{artifact_stem}.json", kind="data_json"
    )
    render_badge_row_with_feedback(
        llm_surface_badges((payload or {}).get("provenance") if payload else None),
        ctx=ctx,
        surface=FeedbackSurface.INSIGHTS_BLOCK,
        block_id=placement.block_id,
        module=module,
        artifact_rel_path=rel,
        output_text=rated,
        provenance=(payload or {}).get("provenance") if payload else None,
        placement_id=placement.placement_id,
        widget_key=f"fb_ai_{placement.placement_id}",
    )
    if not _render_action_items_payload(payload, md):
        _render_quiet_module_empty(
            label=TITLE_MEETING_EXTRACTS,
            run_root=run_root,
            module=module,
            empty_hint=empty_hint,
            ctx=ctx,
            key="llm_action_items_empty",
        )
        return

    _render_view_raw_file_link(
        ctx, module, f"{artifact_stem}.json", link_key="llm_action_items_raw"
    )
    diagnostics = (payload or {}).get("diagnostics") or {}
    if diagnostics:
        with st.expander("Generation details"):
            st.json(diagnostics)
