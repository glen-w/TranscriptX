"""Quiet thumbs-up/down feedback controls for LLM outputs (Streamlit)."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from transcriptx.core.llm_feedback.errors import (
    LlmFeedbackError,
    LlmFeedbackPersistenceError,
    LlmFeedbackValidationError,
)
from transcriptx.core.llm_feedback.models import (
    REASON_LABELS,
    FeedbackProvenance,
    FeedbackRating,
    FeedbackReason,
    FeedbackTarget,
    compute_output_sha256,
    compute_target_instance_id,
    new_uuid4,
    reasons_for_rating,
)
from transcriptx.core.llm_feedback.service import LlmFeedbackService

_NOTE_HELP = (
    "Optional. Do not include sensitive information (names, secrets, private details)."
)
_PRIVACY_CAPTION = (
    "Notes are stored locally. Avoid sensitive or personally identifiable information."
)


def _state_key(target_instance_id: str, suffix: str) -> str:
    return f"llm_fb_{target_instance_id}_{suffix}"


def _ensure_submission_token(target_instance_id: str) -> str:
    key = _state_key(target_instance_id, "token")
    token = st.session_state.get(key)
    if not isinstance(token, str) or not token:
        token = new_uuid4()
        st.session_state[key] = token
    return token


def _clear_form_state(target_instance_id: str) -> None:
    for suffix in ("token", "rating", "open", "note", "reason", "error"):
        st.session_state.pop(_state_key(target_instance_id, suffix), None)


def _identity_from_target(target: FeedbackTarget, output_sha256: str) -> str:
    return compute_target_instance_id(
        surface=target.surface,
        run_id=target.run_id,
        subject_type=target.subject_type,
        subject_id=target.subject_id,
        module=target.module,
        artifact_rel_path=target.artifact_rel_path,
        output_sha256=output_sha256,
        question_id=target.question_id,
        questions_hash=target.questions_hash,
        logical_chart_id=target.logical_chart_id,
        block_id=target.block_id,
    )


def render_llm_feedback_controls(
    *,
    store: LlmFeedbackService,
    target: FeedbackTarget,
    output_text: str,
    provenance: FeedbackProvenance | Mapping[str, Any] | None = None,
    widget_key: str | None = None,
) -> None:
    """Render non-intrusive thumbs + form. ``store`` must be injected (no path resolve).

    Not safe to call from cached Streamlit helpers — submit mutates disk.
    """
    if not output_text or not str(output_text).strip():
        return

    output_sha = compute_output_sha256(output_text)
    instance_id = _identity_from_target(target, output_sha)
    key_base = widget_key or instance_id[:16]
    prov = (
        provenance
        if isinstance(provenance, FeedbackProvenance)
        else FeedbackProvenance.from_artifact_provenance(
            provenance if isinstance(provenance, Mapping) else None
        )
    )

    rating_key = _state_key(instance_id, "rating")
    open_key = _state_key(instance_id, "open")
    error_key = _state_key(instance_id, "error")
    last_key = _state_key(instance_id, "last_rating")
    note_key = _state_key(instance_id, "note")
    reason_key = _state_key(instance_id, "reason")

    up_col, down_col = st.columns(2)
    with up_col:
        if st.button(
            ":material/thumb_up:",
            key=f"llm_fb_up_{key_base}",
            help="Rate this model output helpful",
            type="tertiary",
        ):
            st.session_state[rating_key] = FeedbackRating.UP.value
            st.session_state[open_key] = True
            st.session_state.pop(error_key, None)
            _ensure_submission_token(instance_id)
    with down_col:
        if st.button(
            ":material/thumb_down:",
            key=f"llm_fb_down_{key_base}",
            help="Rate this model output not helpful",
            type="tertiary",
        ):
            st.session_state[rating_key] = FeedbackRating.DOWN.value
            st.session_state[open_key] = True
            st.session_state.pop(error_key, None)
            _ensure_submission_token(instance_id)

    last = st.session_state.get(last_key)
    if last in (FeedbackRating.UP.value, FeedbackRating.DOWN.value):
        st.caption(f"Thanks — recorded as {last}.")

    if not st.session_state.get(open_key):
        return

    rating_raw = st.session_state.get(rating_key)
    try:
        rating = FeedbackRating(str(rating_raw))
    except ValueError:
        st.session_state[open_key] = False
        return

    allowed = reasons_for_rating(rating)
    labels = [REASON_LABELS[r] for r in allowed]
    label_to_reason = {REASON_LABELS[r]: r for r in allowed}

    st.caption(_PRIVACY_CAPTION)
    err = st.session_state.get(error_key)
    if err:
        st.error(str(err))

    # Preserve prior selection across reruns when still valid
    default_label = labels[0]
    prior_reason = st.session_state.get(reason_key)
    if isinstance(prior_reason, str):
        try:
            prior_e = FeedbackReason(prior_reason)
            if prior_e in allowed:
                default_label = REASON_LABELS[prior_e]
        except ValueError:
            pass

    chosen_label = st.selectbox(
        "Reason",
        options=labels,
        index=labels.index(default_label),
        key=f"llm_fb_reason_sel_{key_base}",
    )
    chosen_reason = label_to_reason[chosen_label]
    st.session_state[reason_key] = chosen_reason.value

    if note_key not in st.session_state:
        st.session_state[note_key] = ""
    note = st.text_area(
        "Note (optional)",
        key=note_key,
        help=_NOTE_HELP,
        height=80,
        max_chars=2000,
    )

    submit_col, cancel_col = st.columns(2)
    with submit_col:
        submit = st.button(
            "Submit feedback",
            key=f"llm_fb_submit_{key_base}",
            type="primary",
        )
    with cancel_col:
        if st.button("Cancel", key=f"llm_fb_cancel_{key_base}", type="tertiary"):
            st.session_state[open_key] = False
            st.session_state.pop(error_key, None)
            st.rerun()

    if not submit:
        return

    token = _ensure_submission_token(instance_id)
    supersedes = None
    try:
        supersedes = store.latest_for_instance(instance_id)
    except LlmFeedbackError:
        supersedes = None

    try:
        result = store.submit(
            rating=rating,
            reason=chosen_reason,
            note=note or "",
            output_text=output_text,
            target=target,
            provenance=prov,
            submission_token=token,
            supersedes_feedback_id=supersedes,
        )
    except (
        LlmFeedbackValidationError,
        LlmFeedbackPersistenceError,
        LlmFeedbackError,
    ) as exc:
        st.session_state[error_key] = str(exc)
        st.rerun()
        return
    except OSError as exc:
        st.session_state[error_key] = f"Could not save feedback: {exc}"
        st.rerun()
        return

    # Success only after durable append / idempotent ack
    _clear_form_state(instance_id)
    st.session_state[last_key] = rating.value
    if result.duplicated:
        st.toast("Feedback already saved.")
    else:
        st.toast("Feedback saved. Thank you.")
    st.rerun()
