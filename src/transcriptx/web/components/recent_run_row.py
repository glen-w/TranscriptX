"""Shared recent-run row: title/meta plus configured action strip."""

from __future__ import annotations

import hashlib
import html

import streamlit as st

from transcriptx.utils.text_utils import format_duration_display_from_config
from transcriptx.web.action_menus.context import ActionContext, build_canonical_identity
from transcriptx.web.action_menus.ids import NavStyle, SectionId
from transcriptx.web.action_menus.render import render_configured_actions
from transcriptx.web.action_menus.services import (
    prepare_run_export,
    transcript_path_for_run,
)
from transcriptx.web.components.run_id_info import build_run_id_info_html
from transcriptx.web.context_format import (
    format_run_display,
    friendly_subject_label,
)


def prepare_recent_run_export(run) -> None:
    """Compat wrapper: prepare export for a run object."""
    tp = transcript_path_for_run(run)
    identity = build_canonical_identity(
        subject_type="transcript",
        subject_id=run.run_dir.parent.name,
        transcript_path=tp,
        run_id=run.run_dir.name,
        run_dir=run.run_dir,
    )
    prepare_run_export(identity)


def _row_key_suffix(run_id: str, row_index: int) -> str:
    digest = hashlib.sha1(f"{row_index}:{run_id}".encode("utf-8")).hexdigest()[:12]
    return f"{row_index}_{digest}"


def _meta_parts(run) -> list[str]:
    parts: list[str] = []
    status = getattr(run, "status", None)
    if status and str(status).strip() and str(status).strip().lower() != "unknown":
        parts.append(str(status).strip())
    duration = getattr(run, "duration_seconds", None)
    if duration is not None:
        try:
            label = format_duration_display_from_config(duration)
            if label and label.strip() and label.strip() != "—":
                parts.append(label.strip())
        except Exception:
            pass
    modules = getattr(run, "selected_modules", None) or []
    if modules:
        parts.append(f"{len(modules)} modules")
    profile = getattr(run, "profile_name", None)
    if profile and str(profile).strip():
        parts.append(str(profile).strip())
    return parts


def _context_for_run(
    run,
    *,
    row_index: int,
    key_prefix: str,
    nav_style: NavStyle = NavStyle.ON_CLICK,
) -> ActionContext:
    subject_id = run.run_dir.parent.name
    run_id = run.run_dir.name
    tp = transcript_path_for_run(run)
    identity = build_canonical_identity(
        subject_type="transcript",
        subject_id=subject_id,
        transcript_path=tp,
        run_id=run_id,
        run_dir=run.run_dir,
    )
    status = str(getattr(run, "status", "") or "").lower()
    completed = status in ("completed", "success", "done")
    return ActionContext(
        identity=identity,
        widget_identity=_row_key_suffix(run_id, row_index),
        nav_style=nav_style,
        instance_prefix=key_prefix,
        run_completed=completed,
        export_supported=True,
        rename_supported=tp is not None,
    )


def render_recent_run_actions(
    run,
    *,
    row_index: int = 0,
    key_prefix: str = "home_run",
    section: SectionId = SectionId.HOME_RECENT_RUNS,
    nav_style: NavStyle = NavStyle.ON_CLICK,
) -> None:
    """Render the configured action strip for a recent / post-run row.

    Use ``NavStyle.CLICK_RERUN`` when the strip is painted inside ``@st.fragment``
    so page-changing actions (Rename, Open, …) trigger a full-app rerun.
    """
    ctx = _context_for_run(
        run, row_index=row_index, key_prefix=key_prefix, nav_style=nav_style
    )
    render_configured_actions(section, ctx)


def render_recent_run_row(
    run,
    *,
    row_index: int,
    slug_labels: dict[str, str],
    key_prefix: str = "home_run",
    tip_control_prefix: str = "tx-home-run-tip",
) -> None:
    """Render one recent-run row with the configured action link strip."""
    slug = run.run_dir.parent.name
    stem = (
        run.transcript_path.stem
        if run.transcript_path and run.transcript_path.name
        else None
    )
    title = friendly_subject_label(
        "transcript",
        subject_id=slug,
        slug_labels=slug_labels,
        stem=stem,
    )
    run_display = format_run_display(
        run.run_id,
        fallback_dt=getattr(run, "created_at", None),
        allow_raw_fallback=False,
    )
    meta_parts = _meta_parts(run)
    meta_line = " · ".join(meta_parts) if meta_parts else ""
    key_suffix = _row_key_suffix(run.run_id, row_index)
    info_html = ""
    if run.run_id:
        info_html = " " + build_run_id_info_html(
            run.run_id, control_id=f"{tip_control_prefix}-{key_suffix}"
        )

    secondary = ""
    tp = getattr(run, "transcript_path", None)
    if tp and str(tp) and not str(tp).startswith("sha256:"):
        secondary = f"Transcript: {html.escape(str(tp))}"

    st.markdown(
        f'<div class="tx-recent-run-row" data-testid="tx-recent-run-row-{key_suffix}">'
        f'<div class="tx-recent-run-title">{html.escape(title)}'
        f'<span class="tx-recent-run-when"> · {html.escape(run_display)}</span>'
        f"{info_html}</div>"
        + (
            f'<div class="tx-recent-run-meta">{html.escape(meta_line)}</div>'
            if meta_line
            else ""
        )
        + (
            f'<div class="tx-recent-run-secondary">{secondary}</div>'
            if secondary
            else ""
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    render_recent_run_actions(run, row_index=row_index, key_prefix=key_prefix)
