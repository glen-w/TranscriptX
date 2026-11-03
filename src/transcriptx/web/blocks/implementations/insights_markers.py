"""Lexical diversity, epistemic markers, politeness, and keyphrases Insights blocks."""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.group_content import (
    group_rollup_empty_hint,
    is_group_run,
    list_group_members,
    load_group_session_rows,
    load_group_speaker_rows,
    load_member_module_json,
    member_empty_hint,
    select_group_member,
)
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.components.module_run_prompt import render_module_required_hint

from transcriptx.web.blocks.implementations.insights_support import (
    _load_analysis_json,
    _loader,
    _module_failure_hint,
    _render_view_raw_file_link,
)


def _render_lexical_diversity_payload(payload: Dict[str, Any]) -> None:
    from transcriptx.web.insights_presentation import (
        GUIDED_RANKED_ROW_CAP,
        MODULE_PLAIN_DESCRIPTIONS,
        is_insights_guided,
    )

    guided = is_insights_guided()
    st.caption(MODULE_PLAIN_DESCRIPTIONS.get("lexical_diversity", ""))
    global_stats = payload.get("global_stats") or {}
    if isinstance(global_stats, dict) and global_stats:
        cols = st.columns(3)
        metrics = [
            ("TTR", global_stats.get("ttr")),
            ("MTLD", global_stats.get("mtld")),
            ("Hapax rate", global_stats.get("hapax_rate")),
        ]
        for col, (label, value) in zip(cols, metrics):
            if value is None:
                col.metric(label, "n/a")
            else:
                col.metric(label, f"{float(value):.3f}")
        st.caption("TTR is length-sensitive — compare speakers of similar talk time.")

    speaker_stats = payload.get("speaker_stats") or {}
    speaker_rows = []
    if isinstance(speaker_stats, dict) and speaker_stats:
        for speaker in sorted(speaker_stats):
            if not is_named_speaker(str(speaker)):
                continue
            stats = speaker_stats[speaker]
            if not isinstance(stats, dict):
                continue
            speaker_rows.append(
                {
                    "speaker": speaker,
                    "token_count": stats.get("token_count"),
                    "type_count": stats.get("type_count"),
                    "ttr": stats.get("ttr"),
                    "mtld": stats.get("mtld"),
                    "hapax_rate": stats.get("hapax_rate"),
                }
            )

    if speaker_rows and guided:
        st.caption("Top speakers by MTLD")
        ranked = sorted(
            speaker_rows,
            key=lambda r: float(r.get("mtld") or 0.0),
            reverse=True,
        )[:GUIDED_RANKED_ROW_CAP]
        for row in ranked:
            mtld = row.get("mtld")
            mtld_s = f"{float(mtld):.3f}" if mtld is not None else "n/a"
            st.write(f"- {row['speaker']}: MTLD {mtld_s}")
    elif speaker_rows and not guided:
        st.caption(
            "Per-speaker metrics (TTR is length-sensitive; interpret in context)."
        )
        st.dataframe(speaker_rows, width="stretch", hide_index=True)

    time_buckets = payload.get("time_buckets") or []
    bucket_rows = []
    if isinstance(time_buckets, list) and time_buckets:
        bucket_rows = [
            {
                "bucket_start": bucket.get("bucket_start"),
                "bucket_end": bucket.get("bucket_end"),
                "ttr": bucket.get("ttr"),
                "mtld": bucket.get("mtld"),
                "token_count": bucket.get("token_count"),
            }
            for bucket in time_buckets
            if isinstance(bucket, dict)
        ]

    detail_needed = bool(speaker_rows) or bool(bucket_rows)
    if detail_needed and (guided or bucket_rows):
        with st.expander("Explore details", expanded=False):
            if speaker_rows:
                st.caption("Per-speaker metrics")
                st.dataframe(speaker_rows, width="stretch", hide_index=True)
            if bucket_rows:
                st.caption("Time buckets")
                st.dataframe(bucket_rows, width="stretch", hide_index=True)


def _analysis_module_heading(title: str) -> None:
    if st.session_state.get("_insights_analysis_consolidating_provenance"):
        st.markdown(f"#### {title}")
    else:
        st.subheader(title)


def render_lexical_diversity_block(
    ctx: BlockContext, placement: BlockPlacement
) -> None:
    module = "lexical_diversity"
    title = placement.title_override or str(
        placement.params.get("title", "Lexical Diversity")
    )
    empty_hint = str(
        placement.params.get(
            "empty_hint",
            "Run the `lexical_diversity` module to populate this view.",
        )
    )

    _analysis_module_heading(title)
    loader = _loader(ctx)
    run_root = ctx.run_root
    if run_root is None:
        render_module_required_hint(
            empty_hint, key="lexical_diversity_no_loader", ctx=ctx
        )
        return

    if is_group_run(run_root):
        session_rows = load_group_session_rows(run_root, module)
        speaker_rows = load_group_speaker_rows(run_root, module)
        if session_rows:
            st.caption("Group rollup — per-session metrics")
            st.dataframe(session_rows, width="stretch", hide_index=True)
        if speaker_rows:
            st.caption("Group rollup — per-speaker metrics")
            st.dataframe(speaker_rows[:40], width="stretch", hide_index=True)
        if not session_rows and not speaker_rows:
            st.info(group_rollup_empty_hint(module, content_name="session_rows"))
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key="lexical_diversity_session_select")
        if member is None:
            return
        payload = load_member_module_json(
            loader, member, module, "_lexical_diversity.json"
        )
        if not payload:
            st.info(member_empty_hint(module))
            return
        _render_lexical_diversity_payload(payload)
        _render_view_raw_file_link(
            ctx,
            module,
            "_lexical_diversity.json",
            link_key="lexical_diversity_member_raw",
            storage_root=member.storage_root,
        )
        return

    if loader is None:
        render_module_required_hint(
            empty_hint, key="lexical_diversity_no_loader", ctx=ctx
        )
        return

    failure_hint = _module_failure_hint(run_root, module)
    payload = _load_analysis_json(loader, module, "_lexical_diversity.json")
    if not payload:
        if failure_hint:
            st.warning(failure_hint)
        else:
            render_module_required_hint(
                empty_hint, key="lexical_diversity_empty", ctx=ctx
            )
        return

    _render_lexical_diversity_payload(payload)
    _render_view_raw_file_link(
        ctx, module, "_lexical_diversity.json", link_key="lexical_diversity_raw"
    )


def _render_marker_module_payload(
    payload: Dict[str, Any],
    *,
    share_keys: tuple[str, ...],
    module: str = "",
) -> None:
    from transcriptx.web.insights_presentation import (
        GUIDED_RANKED_ROW_CAP,
        MODULE_PLAIN_DESCRIPTIONS,
        is_insights_guided,
    )

    guided = is_insights_guided()
    if module and MODULE_PLAIN_DESCRIPTIONS.get(module):
        st.caption(MODULE_PLAIN_DESCRIPTIONS[module])

    if payload.get("usable") is False:
        meta = payload.get("metadata") or {}
        st.info(
            "Markers unavailable for this transcript "
            f"(language_status={meta.get('language_status', 'unsupported')})."
        )
        return

    global_stats = payload.get("global_stats") or {}
    if isinstance(global_stats, dict) and global_stats:
        cols = st.columns(min(3, 1 + len(share_keys)))
        cols[0].metric(
            "Hits / 100 tokens",
            (
                "n/a"
                if global_stats.get("hits_per_100_tokens") is None
                else f"{float(global_stats['hits_per_100_tokens']):.2f}"
            ),
        )
        for col, key in zip(cols[1:], share_keys):
            value = global_stats.get(key)
            if key == "hedge_share":
                label = "Hedge share"
            elif key == "booster_share":
                label = "Booster share"
            elif key == "soft_request_ratio":
                label = "Soft-request ratio"
            else:
                label = key.replace("_", " ").title()
            if value is None:
                col.metric(label, "n/a")
            else:
                col.metric(label, f"{float(value):.3f}")

        if (
            guided
            and "hedge_share" in share_keys
            and "booster_share" in share_keys
            and global_stats.get("hedge_share") is not None
            and global_stats.get("booster_share") is not None
        ):
            h = float(global_stats["hedge_share"])
            b = float(global_stats["booster_share"])
            if h + b > 0:
                if h > b * 1.25:
                    st.caption("Hedges outweigh boosters — wording leans cautious.")
                elif b > h * 1.25:
                    st.caption("Boosters outweigh hedges — wording leans assertive.")
                else:
                    st.caption("Hedge and booster use looks roughly balanced.")

    counts = (
        (global_stats.get("category_counts") or {})
        if isinstance(global_stats, dict)
        else {}
    )
    speaker_stats = payload.get("speaker_stats") or {}
    speaker_rows = []
    if isinstance(speaker_stats, dict) and speaker_stats:
        for speaker in sorted(speaker_stats):
            stats = speaker_stats[speaker]
            if not isinstance(stats, dict):
                continue
            row = {
                "speaker": speaker,
                "token_count": stats.get("token_count"),
                "total_marker_hits": stats.get("total_marker_hits"),
                "hits_per_100_tokens": stats.get("hits_per_100_tokens"),
            }
            for key in share_keys:
                row[key] = stats.get(key)
            speaker_rows.append(row)

    hits = payload.get("hits") or []
    if not guided:
        if isinstance(counts, dict) and counts:
            st.caption("Global category counts")
            st.dataframe(
                [{"category": k, "count": v} for k, v in sorted(counts.items())],
                width="stretch",
                hide_index=True,
            )
        if speaker_rows:
            st.caption("Per-speaker marker rates")
            st.dataframe(speaker_rows, width="stretch", hide_index=True)
        if isinstance(hits, list) and hits:
            with st.expander(f"Marker hits ({len(hits)})"):
                preview = [
                    {
                        "speaker": h.get("speaker"),
                        "category": h.get("category"),
                        "surface": h.get("surface"),
                        "segment_index": h.get("segment_index"),
                    }
                    for h in hits[:80]
                    if isinstance(h, dict)
                ]
                if preview:
                    st.dataframe(preview, width="stretch", hide_index=True)
        return

    # Guided: top speakers only, details collapsed
    if speaker_rows:
        st.caption("Speakers with the highest marker rates")
        ranked = sorted(
            speaker_rows,
            key=lambda r: float(r.get("hits_per_100_tokens") or 0.0),
            reverse=True,
        )[:GUIDED_RANKED_ROW_CAP]
        for row in ranked:
            rate = row.get("hits_per_100_tokens")
            rate_s = f"{float(rate):.2f}" if rate is not None else "n/a"
            st.write(f"- {row['speaker']}: {rate_s} hits / 100 tokens")

    with st.expander("Explore details", expanded=False):
        if isinstance(counts, dict) and counts:
            st.caption("Category counts")
            st.dataframe(
                [{"category": k, "count": v} for k, v in sorted(counts.items())],
                width="stretch",
                hide_index=True,
            )
        if speaker_rows:
            st.caption("Per-speaker marker rates")
            st.dataframe(speaker_rows, width="stretch", hide_index=True)
        if isinstance(hits, list) and hits:
            st.caption(f"Marker hits ({len(hits)})")
            preview = [
                {
                    "speaker": h.get("speaker"),
                    "category": h.get("category"),
                    "surface": h.get("surface"),
                    "segment_index": h.get("segment_index"),
                }
                for h in hits[:80]
                if isinstance(h, dict)
            ]
            if preview:
                st.dataframe(preview, width="stretch", hide_index=True)


def _render_marker_module_block(
    ctx: BlockContext,
    placement: BlockPlacement,
    *,
    module: str,
    title_default: str,
    json_suffix: str,
    share_keys: tuple[str, ...],
) -> None:
    title = placement.title_override or str(
        placement.params.get("title", title_default)
    )
    empty_hint = str(
        placement.params.get(
            "empty_hint",
            f"Run the `{module}` module to populate this view.",
        )
    )
    _analysis_module_heading(title)
    loader = _loader(ctx)
    run_root = ctx.run_root
    if run_root is None:
        render_module_required_hint(empty_hint, key=f"{module}_no_loader", ctx=ctx)
        return

    if is_group_run(run_root):
        session_rows = load_group_session_rows(run_root, module)
        speaker_rows = load_group_speaker_rows(run_root, module)
        if session_rows:
            st.caption("Group rollup — per-session metrics")
            st.dataframe(session_rows, width="stretch", hide_index=True)
        if speaker_rows:
            st.caption("Group rollup — per-speaker metrics")
            st.dataframe(speaker_rows[:40], width="stretch", hide_index=True)
        if not session_rows and not speaker_rows:
            st.info(group_rollup_empty_hint(module, content_name="session_rows"))
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key=f"{module}_session_select")
        if member is None:
            return
        payload = load_member_module_json(loader, member, module, json_suffix)
        if not payload:
            st.info(member_empty_hint(module))
            return
        _render_marker_module_payload(payload, share_keys=share_keys, module=module)
        _render_view_raw_file_link(
            ctx,
            module,
            json_suffix,
            link_key=f"{module}_member_raw",
            storage_root=member.storage_root,
        )
        return

    if loader is None:
        render_module_required_hint(empty_hint, key=f"{module}_no_loader", ctx=ctx)
        return

    failure_hint = _module_failure_hint(run_root, module)
    payload = _load_analysis_json(loader, module, json_suffix)
    if not payload:
        if failure_hint:
            st.warning(failure_hint)
        else:
            render_module_required_hint(empty_hint, key=f"{module}_empty", ctx=ctx)
        return

    _render_marker_module_payload(payload, share_keys=share_keys, module=module)
    _render_view_raw_file_link(ctx, module, json_suffix, link_key=f"{module}_raw")


def render_epistemic_markers_block(
    ctx: BlockContext, placement: BlockPlacement
) -> None:
    _render_marker_module_block(
        ctx,
        placement,
        module="epistemic_markers",
        title_default="Epistemic Markers",
        json_suffix="_epistemic_markers.json",
        share_keys=("hedge_share", "booster_share"),
    )


def render_politeness_block(ctx: BlockContext, placement: BlockPlacement) -> None:
    _render_marker_module_block(
        ctx,
        placement,
        module="politeness",
        title_default="Politeness Markers",
        json_suffix="_politeness.json",
        share_keys=("soft_request_ratio",),
    )


def _render_keyphrases_payload(payload: dict[str, Any]) -> None:
    from transcriptx.web.insights_presentation import (
        GUIDED_RANKED_ROW_CAP,
        MODULE_PLAIN_DESCRIPTIONS,
        is_insights_guided,
    )

    guided = is_insights_guided()
    st.caption(MODULE_PLAIN_DESCRIPTIONS.get("keyphrases", ""))
    usable = payload.get("usable")
    state = payload.get("evaluation_state")
    methods_run = payload.get("methods_run") or []
    skipped = payload.get("skipped_methods") or []
    if usable is False:
        reasons = []
        for item in skipped:
            if isinstance(item, dict):
                reasons.append(
                    f"{item.get('method')}: {item.get('reason_code')}"
                    + (f" ({item.get('detail')})" if item.get("detail") else "")
                )
        st.warning(
            "Keyphrases abstained"
            + (f" — evaluation_state={state}" if state else "")
            + (("; " + "; ".join(reasons)) if reasons else ".")
        )
        return
    if not guided:
        if methods_run:
            st.caption("Methods run: " + ", ".join(str(m) for m in methods_run))
        if skipped:
            skip_bits = [
                f"{s.get('method')}:{s.get('reason_code')}"
                for s in skipped
                if isinstance(s, dict)
            ]
            if skip_bits:
                st.caption("Skipped methods: " + ", ".join(skip_bits))
    gbm = payload.get("global_by_method") or {}
    nc = gbm.get("noun_chunks") if isinstance(gbm, dict) else None
    phrases = (nc or {}).get("phrases") if isinstance(nc, dict) else None
    if not phrases:
        st.info("No noun-chunk keyphrases ranked for this transcript.")
        return
    rows = []
    for p in phrases:
        if not isinstance(p, dict):
            continue
        phrase = str(p.get("phrase") or "").strip()
        if not phrase:
            continue
        rows.append(
            {
                "rank": p.get("rank"),
                "phrase": phrase,
                "rank_weight": p.get("rank_weight"),
                "occurrence_count": p.get("occurrence_count"),
                "segment_support": p.get("segment_support"),
                "token_count": p.get("token_count"),
            }
        )
    if not rows:
        st.info("No noun-chunk keyphrases ranked for this transcript.")
        return

    if guided:
        for row in rows[:GUIDED_RANKED_ROW_CAP]:
            st.write(f"- {row['phrase']}")
        with st.expander("Explore details", expanded=False):
            st.caption(
                "Primary method: noun_chunks "
                "(method-separated; YAKE/KeyBERT not mixed)"
            )
            st.dataframe(rows[:40], width="stretch", hide_index=True)
        return

    st.caption("Primary method: noun_chunks (method-separated; YAKE/KeyBERT not mixed)")
    st.dataframe(rows[:40], width="stretch", hide_index=True)


def render_keyphrases_block(ctx: BlockContext, placement: BlockPlacement) -> None:
    title = placement.title_override or str(placement.params.get("title", "Keyphrases"))
    empty_hint = str(
        placement.params.get(
            "empty_hint",
            "Run the `keyphrases` module to populate this view.",
        )
    )
    _analysis_module_heading(title)
    loader = _loader(ctx)
    run_root = ctx.run_root
    module = "keyphrases"
    json_suffix = "_keyphrases.json"
    if run_root is None:
        render_module_required_hint(empty_hint, key=f"{module}_no_loader", ctx=ctx)
        return

    if is_group_run(run_root):
        session_rows = load_group_session_rows(run_root, module)
        if session_rows:
            st.caption("Group rollup — per-session noun_chunk counts")
            st.dataframe(session_rows, width="stretch", hide_index=True)
        else:
            st.info(group_rollup_empty_hint(module, content_name="session_rows"))
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session (noun_chunks primary)")
        member = select_group_member(members, key=f"{module}_session_select")
        if member is None:
            return
        payload = load_member_module_json(loader, member, module, json_suffix)
        if not payload:
            st.info(member_empty_hint(module))
            return
        _render_keyphrases_payload(payload)
        _render_view_raw_file_link(
            ctx,
            module,
            json_suffix,
            link_key=f"{module}_member_raw",
            storage_root=member.storage_root,
        )
        return

    if loader is None:
        render_module_required_hint(empty_hint, key=f"{module}_no_loader", ctx=ctx)
        return

    failure_hint = _module_failure_hint(run_root, module)
    payload = _load_analysis_json(loader, module, json_suffix)
    if not payload:
        if failure_hint:
            st.warning(failure_hint)
        else:
            render_module_required_hint(empty_hint, key=f"{module}_empty", ctx=ctx)
        return

    _render_keyphrases_payload(payload)
    _render_view_raw_file_link(ctx, module, json_suffix, link_key=f"{module}_raw")
