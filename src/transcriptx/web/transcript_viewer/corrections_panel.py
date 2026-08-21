"""Transcript viewer Correct-mode propose / apply panel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.core.corrections.detect import resolve_segment_id
from transcriptx.core.corrections.word_spans import (
    AmbiguousFindError,
    find_unique_char_span,
    iter_segment_word_spans,
    span_from_word_range,
)
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.services.corrections_studio.controller import (
    CorrectionsStudioController,
)
from transcriptx.services.corrections_studio.manual_propose_service import (
    ManualProposeConflict,
    ManualProposeValidationError,
)
from transcriptx.web.action_menus.context import build_canonical_identity
from transcriptx.web.action_menus.services import (
    PAGE_CORRECTIONS,
    navigate_with_identity,
)
from transcriptx.web.state import PAGE_KEY, apply_subject_context
from transcriptx.web.components.info_tooltip import widget_help


@dataclass(frozen=True)
class ViewerCorrectionContext:
    transcript_path: str
    transcript_identity_hash: str
    segments: list[dict[str, Any]]


def correction_widget_key(
    identity_hash: str,
    segment_id: str,
    suffix: str,
) -> str:
    """Stable widget key: transcript identity + segment_id + suffix (H14)."""
    safe_id = segment_id.replace("|", "_")[:80]
    return f"tx_corr|{identity_hash[:16]}|{safe_id}|{suffix}"


def _controller() -> CorrectionsStudioController:
    return CorrectionsStudioController()


def ensure_session(transcript_path: str) -> str:
    ctrl = _controller()
    doc = ctrl.start_or_resume(transcript_path)
    st.session_state["transcript_viewer_corrections_session_id"] = doc.session_id
    return doc.session_id


def render_correct_mode_toggle() -> bool:
    return bool(
        st.checkbox(
            "Correct mode",
            key="transcript_viewer_correct_mode",
            help=widget_help(
                "Select a word or span and propose a correction while reading."
            ),
        )
    )


def render_pending_strip(session_id: Optional[str]) -> None:
    if not session_id:
        return
    ctrl = _controller()
    pending = ctrl.list_candidates(
        session_id, status_filter="pending", kind_filter=["manual"], limit=20
    )
    manuals = ctrl.list_candidates(session_id, kind_filter=["manual"], limit=50)
    if not manuals:
        st.caption("No viewer proposals yet for this transcript.")
        return
    st.caption(
        f"**{len(pending)}** pending manual · **{len(manuals)}** viewer proposals "
        "(current generation). Open **Corrections Studio** for batch review."
    )
    for c in pending[:5]:
        st.write(f"- `{c.wrong_text}` → `{c.right_text}`")


def _resolve_span_from_ui(
    segment: dict[str, Any],
    *,
    identity_hash: str,
    segment_id: str,
) -> Tuple[Optional[Tuple[int, int]], Optional[str], Optional[str]]:
    """Return (span, wrong_text, error_message)."""
    spans, aligned = iter_segment_word_spans(segment)
    use_words = bool(spans) and (
        aligned or isinstance(segment.get("words"), list) and segment.get("words")
    )
    if use_words and spans:
        # Phase 3: surface low-confidence words as labelled affordances (not auto-candidates).
        low_conf = []
        for s in spans:
            if s.score is not None and float(s.score) < 0.5:
                low_conf.append(f"{s.word_index}:{s.text} ({s.score:.2f})")
        if low_conf:
            st.caption(
                "Low ASR confidence (assist only — enter replacement yourself): "
                + ", ".join(low_conf[:8])
            )
        labels = [f"{i}: {s.text}" for i, s in enumerate(spans)]
        start_lab = st.selectbox(
            "From word",
            labels,
            key=correction_widget_key(identity_hash, segment_id, "w0"),
            help=widget_help(
                "First word of the span to replace (word-timed segments only)."
            ),
        )
        end_lab = st.selectbox(
            "To word",
            labels,
            key=correction_widget_key(identity_hash, segment_id, "w1"),
            help=widget_help(
                "Last word of the span (inclusive). Must be at or after From word."
            ),
        )
        i0 = int(start_lab.split(":", 1)[0])
        i1 = int(end_lab.split(":", 1)[0])
        if i1 < i0:
            return None, None, "End word must be at or after start word."
        try:
            start, end, wrong = span_from_word_range(segment, i0, i1)
        except (IndexError, ValueError) as exc:
            return None, None, str(exc)
        return (start, end), wrong, None

    needle = st.text_input(
        "Find exact text in segment",
        key=correction_widget_key(identity_hash, segment_id, "find"),
        help=widget_help("Must match exactly once; ambiguous matches are rejected."),
    )
    if not needle:
        return None, None, None
    try:
        start, end = find_unique_char_span(str(segment.get("text") or ""), needle)
    except AmbiguousFindError as exc:
        return None, None, str(exc)
    except ValueError as exc:
        return None, None, str(exc)
    return (start, end), needle, None


def render_segment_propose_panel(
    *,
    ctx: ViewerCorrectionContext,
    source_index: int,
    segment: dict[str, Any],
) -> None:
    sid = resolve_segment_id(
        segment, ctx.transcript_identity_hash, segment_index=source_index
    )
    with st.expander("Propose correction", expanded=False):
        span, wrong, err = _resolve_span_from_ui(
            segment,
            identity_hash=ctx.transcript_identity_hash,
            segment_id=sid,
        )
        if err:
            st.warning(err)
        right = st.text_input(
            "Replacement",
            key=correction_widget_key(ctx.transcript_identity_hash, sid, "right"),
            help=widget_help(
                "Text that should replace the selected span or exact find match."
            ),
        )
        c1, c2, c3 = st.columns(3)
        propose = c1.button(
            "Propose",
            icon=ic.SPELLCHECK,
            key=correction_widget_key(ctx.transcript_identity_hash, sid, "propose"),
        )
        accept_apply = c2.button(
            "Accept & apply this",
            icon=ic.CHECK,
            key=correction_widget_key(ctx.transcript_identity_hash, sid, "apply"),
            type="primary",
        )
        open_studio = c3.button(
            "Open Studio",
            icon=ic.CORRECTIONS,
            key=correction_widget_key(ctx.transcript_identity_hash, sid, "studio"),
        )
        if open_studio:
            # Clear picker key + bind subject via identity nav so the studio
            # selectbox can use index= without a Session State conflict.
            path = Path(ctx.transcript_path)
            navigate_with_identity(
                build_canonical_identity(
                    subject_type="transcript",
                    subject_id=path.stem,
                    transcript_path=path,
                ),
                PAGE_CORRECTIONS,
            )
            st.rerun()

        if not (propose or accept_apply):
            return
        if span is None or not wrong:
            st.error("Select a unique span before proposing.")
            return
        if not right or not right.strip():
            st.error("Enter a replacement.")
            return
        try:
            session_id = ensure_session(ctx.transcript_path)
            ctrl = _controller()
            result = ctrl.propose_manual_correction(
                session_id,
                segment_id=sid,
                segment_index=source_index,
                span=span,
                wrong_text=wrong,
                right_text=right.strip(),
                auto_accept=bool(accept_apply),
            )
            if accept_apply:
                export = ctrl.apply_and_export_scoped(
                    session_id,
                    candidate_ids=[result.candidate.candidate_id],
                )
                st.success(
                    f"Applied to sidecar `{Path(export.export_path).name}` "
                    "(original unchanged)."
                )
                st.session_state["transcript_viewer_last_corrected_path"] = (
                    export.export_path
                )
                if st.button(
                    "Open corrected transcript",
            icon=ic.ARTICLE,
                    key=correction_widget_key(
                        ctx.transcript_identity_hash, sid, "open_corrected"
                    ),
                ):
                    open_corrected_as_subject(export.export_path)
            else:
                st.success(
                    f"Proposed `{wrong}` → `{right.strip()}`"
                    + (" (upserted)" if result.upserted else "")
                )
        except ManualProposeConflict as exc:
            st.error(str(exc))
        except ManualProposeValidationError as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001 — surface to UI
            st.error(f"Correction failed: {exc}")


def open_corrected_as_subject(corrected_path: str) -> None:
    """H12: open sidecar as new subject with its own corrections session."""
    path = str(Path(corrected_path).expanduser().resolve())
    # Start a fresh corrections session bound to the sidecar (new identity).
    ctrl = _controller()
    child = ctrl.start_or_resume(path)
    st.session_state["transcript_viewer_corrections_session_id"] = child.session_id
    st.session_state["transcript_viewer_lineage_note"] = (
        f"Viewing corrected artifact derived from a prior export "
        f"(session `{child.session_id}`)."
    )
    # Prefer path-based subject switch when available.
    try:
        from transcriptx.web.navigation import make_session_path_resolver
        from transcriptx.web.services import SubjectService

        SubjectService.set_transcript_context_from_path(
            st.session_state,
            path,
            session_resolver=make_session_path_resolver(),
        )
    except Exception:
        apply_subject_context(
            st.session_state,
            subject_type="transcript",
            subject_id=Path(path).stem,
            run_id=None,
        )
    st.session_state[PAGE_KEY] = "Transcript"
    st.session_state["transcript_override_path"] = path
    st.rerun()


def build_viewer_correction_context(
    transcript_path: str, segments: list[dict[str, Any]]
) -> ViewerCorrectionContext:
    identity = compute_transcript_identity_hash(segments)
    return ViewerCorrectionContext(
        transcript_path=str(Path(transcript_path).expanduser().resolve()),
        transcript_identity_hash=identity,
        segments=segments,
    )
