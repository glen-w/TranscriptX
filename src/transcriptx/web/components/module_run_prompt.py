"""Fixed Run Analysis CTA under "run the module" empty-state messages.

Not part of configurable interface action menus — always shown when a block
tells the user a module must be run to populate the view.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.web.action_menus.catalog import help_for, icon_for, label_for
from transcriptx.web.action_menus.context import (
    CanonicalIdentity,
    IdentityError,
    build_canonical_identity,
)
from transcriptx.web.action_menus.ids import ActionId
from transcriptx.web.action_menus.services import (
    PAGE_RUN_ANALYSIS,
    navigate_with_identity,
)
from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.components.action_links import render_action_link
from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.state import PAGE_KEY


def identity_for_run_analysis(
    ctx: BlockContext | None = None,
    *,
    session_state: dict | None = None,
) -> CanonicalIdentity | None:
    """Build subject identity for Run Analysis from block context and/or session."""
    ss = session_state if session_state is not None else st.session_state
    subject_type = (ctx.subject_type if ctx is not None else None) or ss.get(
        "subject_type"
    )
    subject_id = (ctx.subject_id if ctx is not None else None) or ss.get("subject_id")
    if subject_type not in ("transcript", "group") or not subject_id:
        return None

    transcript_path: Path | None = None
    if subject_type == "transcript":
        path_str = SubjectService.current_transcript_path(ss)
        if path_str:
            transcript_path = Path(path_str)

    run_id = (ctx.run_id if ctx is not None else None) or ss.get("run_id")
    run_dir = ctx.run_root if ctx is not None else None
    if run_id and run_dir is None:
        run_id = None
    if run_dir is not None and not run_id:
        run_dir = None

    try:
        return build_canonical_identity(
            subject_type=subject_type,
            subject_id=str(subject_id),
            transcript_path=transcript_path,
            run_id=run_id,
            run_dir=run_dir,
        )
    except IdentityError:
        try:
            return build_canonical_identity(
                subject_type=subject_type,
                subject_id=str(subject_id),
                transcript_path=transcript_path,
            )
        except IdentityError:
            return None


def render_module_required_hint(
    message: str,
    *,
    key: str,
    ctx: BlockContext | None = None,
) -> None:
    """Show an info message plus a fixed Run Analysis action link underneath."""
    st.info(message)
    action = ActionId.RUN_ANALYSIS
    label = label_for(action)
    icon = icon_for(action)
    help_text = help_for(action)

    if render_action_link(
        label,
        key=f"mod_req_{key}",
        icon=icon,
        help=help_text,
    ):
        identity = identity_for_run_analysis(ctx)
        if identity is not None:
            navigate_with_identity(identity, PAGE_RUN_ANALYSIS)
        else:
            st.session_state[PAGE_KEY] = PAGE_RUN_ANALYSIS
        st.rerun()
