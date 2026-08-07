"""Insights block for llm_custom_qa citation cards."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import streamlit as st

from transcriptx.core.analysis.llm_custom_qa.readers import (
    find_committed_custom_qa_artifact,
    load_committed_custom_qa_payload,
)
from transcriptx.core.llm_feedback.models import (
    FeedbackProvenance,
    FeedbackSurface,
    FeedbackTarget,
)
from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.llm_presentation import (
    AI_OUTPUT_BADGE,
    feedback_subject_type,
    render_badge_row,
)
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.components.llm_feedback import render_llm_feedback_controls
from transcriptx.web.services.llm_feedback_service import get_llm_feedback_service


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _csv_safe(text: str) -> str:
    """Neutralize CSV formula injection for exported-looking text."""
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def _valid_segment_indexes(segs: Any) -> list[int]:
    if not isinstance(segs, list) or not segs:
        return []
    out: list[int] = []
    for item in segs:
        if isinstance(item, bool) or not isinstance(item, int):
            return []
        if item < 0:
            return []
        out.append(item)
    # Contiguous ascending required for jump safety
    if out != list(range(out[0], out[0] + len(out))):
        return []
    return out


def _artifact_rel_for_run(run_root: Path) -> str | None:
    path = find_committed_custom_qa_artifact(run_root)
    if path is None:
        return None
    try:
        return path.resolve().relative_to(Path(run_root).resolve()).as_posix()
    except ValueError:
        # Alias may live under run_root already as relative-looking path
        try:
            return Path(path).relative_to(run_root).as_posix()
        except ValueError:
            name = path.name
            return f"llm_custom_qa/{name}" if name else None


def _render_answer_card(
    row: dict[str, Any],
    *,
    key_prefix: str,
    allow_jump: bool = True,
    show_evidence: bool = True,
    ctx: BlockContext | None = None,
    placement: BlockPlacement | None = None,
    artifact_rel_path: str | None = None,
    questions_hash: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> None:
    q = _csv_safe(str(row.get("question") or ""))
    status = str(row.get("status") or "")
    raw_idx = row.get("question_index")
    display_n = raw_idx + 1 if isinstance(raw_idx, int) else (raw_idx if raw_idx is not None else "?")
    st.markdown(
        f"**Q{display_n}:** {_escape(q)}",
        unsafe_allow_html=True,
    )
    if status == "unavailable":
        reason = row.get("system_reason")
        label = f"{status} ({reason})" if reason else status
        st.markdown(
            f'Status: <span style="color:#c62828">{_escape(label)}</span>',
            unsafe_allow_html=True,
        )
    elif status and status != "answered":
        st.caption(f"Status: `{_escape(status)}`")
    if status == "answered":
        answer = _csv_safe(str(row.get("answer") or ""))
        st.markdown(_escape(answer), unsafe_allow_html=True)
        question_id = str(row.get("question_id") or "").strip()
        qhash = str(
            questions_hash or (provenance or {}).get("questions_hash") or ""
        ).strip()
        if (
            ctx is not None
            and placement is not None
            and artifact_rel_path
            and question_id
            and qhash
            and answer.strip()
            and ctx.run_id
            and ctx.subject_id
        ):
            target = FeedbackTarget(
                surface=FeedbackSurface.CUSTOM_QA_ANSWER.value,
                block_id=placement.block_id,
                placement_id=placement.placement_id,
                module="llm_custom_qa",
                run_id=str(ctx.run_id),
                subject_type=feedback_subject_type(ctx),
                subject_id=str(ctx.subject_id),
                artifact_rel_path=artifact_rel_path,
                question_id=question_id,
                questions_hash=qhash.lower(),
                logical_chart_id=None,
            )
            render_llm_feedback_controls(
                store=get_llm_feedback_service(),
                target=target,
                output_text=answer,
                provenance=FeedbackProvenance.from_artifact_provenance(provenance),
                widget_key=f"fb_qa_{key_prefix}_{question_id}",
            )
        if show_evidence:
            reasoning = row.get("reasoning")
            if reasoning:
                st.caption("Evidence explanation")
                st.markdown(
                    _escape(_csv_safe(str(reasoning))),
                    unsafe_allow_html=True,
                )
            evidence_used = row.get("evidence_used") or {}
            if isinstance(evidence_used, dict) and evidence_used.get(
                "pack_ids_rendered"
            ):
                st.caption(
                    f"Evidence: packs={evidence_used.get('pack_ids_rendered')} "
                    f"transcript={evidence_used.get('use_transcript')}"
                )
            citations = row.get("citations") or []
            if isinstance(citations, list):
                for i, cite in enumerate(citations):
                    if not isinstance(cite, dict):
                        continue
                    quote = _csv_safe(str(cite.get("quote") or ""))
                    segs = _valid_segment_indexes(cite.get("segment_indexes"))
                    st.code(quote, language=None)
                    st.caption(
                        f"segments={_escape(segs)} "
                        f"start={_escape(cite.get('start_time'))} "
                        f"end={_escape(cite.get('end_time'))}"
                    )
                    if (
                        allow_jump
                        and segs
                        and st.button(
                            f"Jump to segment {segs[0]}",
                            key=f"{key_prefix}_jump_{row.get('question_index')}_{i}",
                        )
                    ):
                        st.session_state["transcript_jump_segment_index"] = segs[0]
                        st.toast(f"Jump requested to segment {segs[0]}")
                    elif allow_jump and cite.get("segment_indexes") and not segs:
                        st.caption("Jump blocked: invalid segment_indexes")
    elif status == "abstained":
        st.info(f"Abstained: `{_escape(row.get('abstain_reason'))}`")
    st.divider()


def render_llm_custom_qa_block(ctx: BlockContext, placement: BlockPlacement) -> None:
    title = placement.title_override or str(
        placement.params.get("title", "Custom Questions")
    )
    empty_hint = str(
        placement.params.get(
            "empty_hint",
            "Run the `llm_custom_qa` module to populate this view.",
        )
    )
    st.subheader(title)
    run_root = ctx.run_root
    if run_root is None:
        st.info(empty_hint)
        return

    render_badge_row([AI_OUTPUT_BADGE])

    from transcriptx.web.blocks.group_content import (
        group_rollup_empty_hint,
        is_group_run,
        list_group_members,
        load_group_content_rows,
    )

    if is_group_run(run_root):
        rows = load_group_content_rows(run_root, "llm_custom_qa", "qa_answer_rows")
        from transcriptx.core.analysis.llm_custom_qa.readers import (
            load_group_member_failures,
        )

        failures = load_group_member_failures(Path(run_root))
        if failures:
            st.caption(f"{len(failures)} member failure(s) recorded")
        members = list_group_members(run_root)
        member_keys = {m.transcript_key for m in members if m.transcript_key}
        member_paths = {m.transcript_path for m in members if m.transcript_path}
        member_runs = {m.run_id for m in members if m.run_id}
        if rows:
            for i, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                sid = str(row.get("source_transcript_id") or "")
                st.caption(f"Session: {_escape(sid)}")
                owned = not member_keys or sid in member_keys or sid in member_paths
                run_rel = str(row.get("source_run_relpath") or "")
                run_ok = True
                if member_runs and run_rel:
                    # artifact ownership: member run id must appear in path
                    run_ok = any(rid and rid in run_rel for rid in member_runs)
                allow_jump = bool(owned and run_ok)
                if not owned:
                    st.warning("Citation jump blocked: member subject mismatch")
                elif member_runs and run_rel and not run_ok:
                    st.warning("Citation jump blocked: member run ownership mismatch")
                _render_answer_card(
                    row,
                    key_prefix=f"group_qa_{i}",
                    allow_jump=allow_jump,
                    ctx=ctx,
                    placement=placement,
                    artifact_rel_path=str(row.get("source_artifact_relpath") or "")
                    or None,
                    questions_hash=str(row.get("questions_hash") or "") or None,
                    provenance=(
                        row.get("provenance")
                        if isinstance(row.get("provenance"), dict)
                        else None
                    ),
                )
        else:
            st.info(
                group_rollup_empty_hint("llm_custom_qa", content_name="qa_answer_rows")
            )
        return

    payload = load_committed_custom_qa_payload(Path(run_root))
    if not payload:
        st.info(empty_hint)
        return
    st.caption(
        f"outcome=`{_escape(payload.get('outcome'))}` "
        f"hash=`{_escape(str(payload.get('questions_hash') or '')[:12])}` "
        f"from=`{_escape((payload.get('provenance') or {}).get('resolved_from'))}`"
    )
    answers = payload.get("answers") or []
    if not answers:
        st.write("No questions for this run.")
        return
    artifact_rel = _artifact_rel_for_run(Path(run_root))
    qhash = str(payload.get("questions_hash") or "").strip() or None
    prov = (
        payload.get("provenance")
        if isinstance(payload.get("provenance"), dict)
        else None
    )
    if not qhash and isinstance(prov, dict):
        qhash = str(prov.get("questions_hash") or "").strip() or None
    for i, row in enumerate(answers):
        if isinstance(row, dict):
            _render_answer_card(
                row,
                key_prefix=f"qa_{i}",
                ctx=ctx,
                placement=placement,
                artifact_rel_path=artifact_rel,
                questions_hash=qhash,
                provenance=prov,
            )
