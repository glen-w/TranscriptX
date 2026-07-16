"""Shared run-scoped page guard and context for TranscriptX Studio pages."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import streamlit as st

from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.services import RunIndex, SubjectService
from transcriptx.web.services.subject_service import ResolvedSubject


@dataclass(frozen=True)
class RunScopedPageContext:
    subject: ResolvedSubject
    run_id: str
    run_root: Path


@dataclass(frozen=True)
class RunScopedPageConfig:
    title: str
    description: str
    empty_headline: str
    empty_detail: str
    primary_action: tuple[str, str]
    secondary_action: tuple[str, str]


def render_run_scoped_page(
    config: RunScopedPageConfig,
    *,
    render_body: Callable[[RunScopedPageContext], None],
    on_missing_run_dir: Literal["info", "error", "empty_state"] | None = None,
) -> bool:
    """
    Render run-scoped page guards and invoke ``render_body`` when context is ready.

    Returns True when ``render_body`` was called; False when a guard shell was shown.

    When ``on_missing_run_dir`` is None, missing run directories are not blocked
    (legacy Overview/Charts/Data behaviour). Pass ``"info"``, ``"error"``, or
    ``"empty_state"`` to enforce an existing run folder before calling ``render_body``.

    Structure on every path: title → description → content or empty/prereq state.
    """
    subject = SubjectService.resolve_current_subject(st.session_state)
    run_id = st.session_state.get("run_id")
    if not subject or not run_id:
        render_page_shell(
            config.title,
            config.description,
            badges=None,
            actions=None,
        )
        render_empty_state(
            "missing_prerequisite",
            config.empty_headline,
            config.empty_detail,
            primary_action=config.primary_action,
            secondary_action=config.secondary_action,
        )
        return False

    run_root = RunIndex.get_run_root(
        subject.scope,
        run_id,
        subject_id=subject.subject_id,
    )
    if on_missing_run_dir is not None and not run_root.exists():
        render_page_shell(
            config.title,
            config.description,
            badges=None,
            actions=None,
        )
        if on_missing_run_dir == "info":
            st.info("Run folder not found.")
        elif on_missing_run_dir == "error":
            st.error("Run directory not found.")
        else:
            render_empty_state(
                "error_degraded",
                "Run folder not found",
                "The selected run directory is missing or was removed.",
                primary_action=config.primary_action,
                secondary_action=config.secondary_action,
            )
        return False

    ctx = RunScopedPageContext(subject=subject, run_id=run_id, run_root=run_root)
    render_body(ctx)
    return True
