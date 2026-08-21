"""Shared Analysis preset resolve/render helpers for Run Analysis and Batch."""

from __future__ import annotations

from typing import Any, Optional, Sequence

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.core.analysis.selection import (
    VALID_PRESETS,
    AnalysisPreset,
    AnalysisTarget,
    EffectiveModulePlan,
    ResolvedAnalysisPreset,
    compute_effective_modules,
    reconcile_custom_modules,
    resolve_analysis_preset,
)
from transcriptx.core.utils.audio_availability import has_resolvable_audio
from transcriptx.web.module_option_format import format_module_option
from transcriptx.web.module_registry import build_module_label
from transcriptx.web.module_ui_groups import MODULE_UI_GROUPS, TECHNICAL_OTHER_TITLE
from transcriptx.web.components.info_tooltip import widget_help

_PRESET_LABELS: dict[AnalysisPreset, str] = {
    "quick": "Quick",
    "balanced": "Balanced",
    "thorough": "Thorough",
    "custom": "Custom",
}
_PRESET_HELP = (
    "**Quick** — no LLM, no heavy modules (and no modules that require them).\n\n"
    "**Balanced** — limited heavy modules + global LLM summary only.\n\n"
    "**Thorough** — all suitable modules for this target.\n\n"
    "**Custom** — pick modules.\n\n"
    "Edit Quick/Balanced/Thorough under Settings → Analysis."
)
_CUSTOM_QA_MODULE = "llm_custom_qa"
_REVIEW_KEEP_OPEN_SUFFIX = "_review_modules_keep_open"
_PENDING_REVIEW_REMOVAL_SUFFIX = "_pending_review_removal"


def migrate_legacy_analysis_keys(session_state: Any, *, key_prefix: str) -> None:
    """Retire old mode/profile/recommended keys; seed preset once if needed."""
    if key_prefix == "batch":
        legacy_mode = "batch_mode"
        legacy_profile = "batch_profile"
        legacy_defaults = "batch_use_defaults"
        legacy_modules = "batch_modules"
    else:
        legacy_mode = "run_analysis_mode"
        legacy_profile = "run_analysis_profile"
        legacy_defaults = "run_analysis_use_defaults"
        legacy_modules = "run_analysis_modules"

    preset_key = f"{key_prefix}_preset"
    custom_key = f"{key_prefix}_custom_modules"
    migrated_flag = f"{key_prefix}_legacy_analysis_migrated"

    if session_state.get(migrated_flag):
        session_state.pop(legacy_mode, None)
        session_state.pop(legacy_profile, None)
        session_state.pop(legacy_defaults, None)
        return

    if preset_key not in session_state:
        mode = session_state.get(legacy_mode)
        use_defaults = session_state.get(legacy_defaults, True)
        modules = session_state.get(legacy_modules)
        if isinstance(modules, list) and modules and use_defaults is False:
            session_state[preset_key] = "Custom"
            session_state[custom_key] = list(modules)
        elif mode == "quick":
            session_state[preset_key] = "Quick"
        else:
            session_state[preset_key] = "Balanced"

    session_state.pop(legacy_mode, None)
    session_state.pop(legacy_profile, None)
    session_state.pop(legacy_defaults, None)
    session_state[migrated_flag] = True


def _label_to_preset(label: str) -> AnalysisPreset:
    for key, text in _PRESET_LABELS.items():
        if text == label:
            return key
    return "balanced"


def format_preset_label(preset: AnalysisPreset | str) -> str:
    if preset in _PRESET_LABELS:
        return _PRESET_LABELS[preset]  # type: ignore[index]
    return str(preset).title()


def _pending_review_removal_key(key_prefix: str) -> str:
    return f"{key_prefix}{_PENDING_REVIEW_REMOVAL_SUFFIX}"


def apply_pending_review_module_removal(session_state: Any, *, key_prefix: str) -> None:
    """Apply a Review-modules removal queued after widgets already ran last tick."""
    pending = session_state.pop(_pending_review_removal_key(key_prefix), None)
    if not isinstance(pending, dict):
        return
    remaining = pending.get("remaining")
    if not isinstance(remaining, list) or not remaining:
        return
    session_state[f"{key_prefix}_preset"] = "Custom"
    session_state[f"{key_prefix}_custom_modules"] = list(remaining)
    # Drop the multiselect widget key so it re-seeds from custom_modules
    # (filtered to picker options) before the widget is created.
    session_state.pop(f"{key_prefix}_custom_modules_widget", None)
    qa_key_prefix = pending.get("clear_qa_key_prefix")
    if isinstance(qa_key_prefix, str) and qa_key_prefix:
        session_state[f"{qa_key_prefix}_adhoc_rows"] = []
        session_state[f"{qa_key_prefix}_saved"] = []


def apply_review_module_removal(
    session_state: Any,
    *,
    key_prefix: str,
    qa_key_prefix: str | None,
    module_ids: Sequence[str],
    remove_id: str,
) -> bool:
    """
    Queue dropping ``remove_id`` from the run (Custom + remainder).

    Returns False when the module is absent or would leave the plan empty.
    Removing ``llm_custom_qa`` also clears the Custom questions picker on apply.
    """
    if remove_id not in module_ids:
        return False
    remaining = [m for m in module_ids if m != remove_id]
    if not remaining:
        return False

    payload: dict[str, Any] = {"remaining": list(remaining)}
    if remove_id == _CUSTOM_QA_MODULE and qa_key_prefix:
        payload["clear_qa_key_prefix"] = qa_key_prefix
    session_state[_pending_review_removal_key(key_prefix)] = payload
    session_state[f"{key_prefix}{_REVIEW_KEEP_OPEN_SUFFIX}"] = True
    return True


def render_analysis_preset_selector(
    *,
    key_prefix: str,
    target: AnalysisTarget,
    transcript_targets: Optional[Sequence[Any]],
    available_modules: Sequence[str],
) -> ResolvedAnalysisPreset:
    """
    Render Analysis preset + Custom module picker.

    Returns resolved preset (modules without Custom QA fold-in).
    Callers apply ``compute_effective_modules`` / ``apply_custom_qa_to_plan``.
    """
    migrate_legacy_analysis_keys(st.session_state, key_prefix=key_prefix)
    apply_pending_review_module_removal(st.session_state, key_prefix=key_prefix)

    preset_key = f"{key_prefix}_preset"
    custom_key = f"{key_prefix}_custom_modules"
    target_fp_key = f"{key_prefix}_preset_target_fp"

    options = [format_preset_label(p) for p in VALID_PRESETS]
    if preset_key not in st.session_state:
        st.session_state[preset_key] = "Balanced"
    elif st.session_state.get(preset_key) not in options:
        st.session_state[preset_key] = "Balanced"

    label = st.segmented_control(
        "Analysis preset",
        options=options,
        key=preset_key,
        help=widget_help(_PRESET_HELP),
    )
    if label is None:
        label = st.session_state.get(preset_key) or "Balanced"
    preset = _label_to_preset(str(label))

    suitable_thorough = resolve_analysis_preset(
        "thorough",
        target=target,
        transcript_targets=transcript_targets,
        audio_resolver=has_resolvable_audio,
    ).module_ids
    suitable_set = list(suitable_thorough)

    fp = (
        target,
        tuple(str(t) for t in (transcript_targets or ())),
        tuple(suitable_set),
    )
    stored_custom = list(st.session_state.get(custom_key) or [])
    if not stored_custom:
        balanced_ids = resolve_analysis_preset(
            "balanced",
            target=target,
            transcript_targets=transcript_targets,
            audio_resolver=has_resolvable_audio,
        ).module_ids
        stored_custom = list(balanced_ids)
        st.session_state[custom_key] = stored_custom

    if st.session_state.get(target_fp_key) != fp:
        kept, removed_t = reconcile_custom_modules(stored_custom, suitable=suitable_set)
        if removed_t:
            st.session_state[custom_key] = list(kept)
            stored_custom = list(kept)
            st.caption(
                "Removed modules no longer suitable for this target: "
                + ", ".join(format_module_option(m) for m in removed_t[:8])
                + ("…" if len(removed_t) > 8 else "")
            )
        st.session_state[target_fp_key] = fp

    picker_options = (
        list(available_modules) if available_modules else list(suitable_set)
    )
    if preset == "custom":
        widget_key = f"{key_prefix}_custom_modules_widget"
        if widget_key not in st.session_state:
            st.session_state[widget_key] = [
                m for m in stored_custom if m in picker_options
            ]
        selected = st.multiselect(
            "Select modules",
            options=picker_options,
            format_func=format_module_option,
            key=widget_key,
            help=widget_help(
                "Custom preset: exact module set for this launch (dependencies still resolve)."
            ),
        )
        st.session_state[custom_key] = list(selected)
        custom_modules = selected
    else:
        custom_modules = list(st.session_state.get(custom_key) or [])

    return resolve_analysis_preset(
        preset,
        target=target,
        transcript_targets=transcript_targets,
        custom_modules=custom_modules,
        audio_resolver=has_resolvable_audio,
    )


def apply_custom_qa_to_plan(
    resolved: ResolvedAnalysisPreset,
    *,
    custom_qa_execution: bool,
) -> EffectiveModulePlan:
    """Fold Custom QA intent into the authoritative effective module plan."""
    return compute_effective_modules(resolved, custom_qa_execution=custom_qa_execution)


def render_effective_module_summary(
    plan: EffectiveModulePlan,
    *,
    preset: AnalysisPreset,
    key_prefix: str,
    qa_key_prefix: str | None = None,
) -> None:
    """Summary + Review expander from the authoritative effective plan."""
    n = len(plan.module_ids)
    parts = [f"**{format_preset_label(preset)}** · {n} modules"]
    if plan.llm_count:
        parts.append(f"{plan.llm_count} use an LLM")
    if plan.heavy_count:
        parts.append(f"{plan.heavy_count} heavy")
    st.caption(" · ".join(parts))
    keep_open_key = f"{key_prefix}{_REVIEW_KEEP_OPEN_SUFFIX}"
    expanded = bool(st.session_state.pop(keep_open_key, False))
    with st.expander("Review modules", expanded=expanded):
        _render_grouped_module_names(
            plan.module_ids,
            key_prefix=key_prefix,
            qa_key_prefix=qa_key_prefix,
        )


def _render_grouped_module_names(
    module_ids: Sequence[str],
    *,
    key_prefix: str,
    qa_key_prefix: str | None,
) -> None:
    remaining = set(module_ids)
    claimed: set[str] = set()
    can_remove = len(module_ids) > 1
    for group in MODULE_UI_GROUPS:
        rows: list[str] = []
        for mid in group.module_ids:
            if mid in remaining and mid not in claimed:
                rows.append(mid)
                claimed.add(mid)
        if rows:
            st.markdown(f"**{group.title}**")
            for mid in rows:
                _render_review_module_row(
                    mid,
                    key_prefix=key_prefix,
                    qa_key_prefix=qa_key_prefix,
                    module_ids=module_ids,
                    can_remove=can_remove,
                )
    other = [m for m in module_ids if m not in claimed]
    if other:
        st.markdown(f"**{TECHNICAL_OTHER_TITLE}**")
        for mid in other:
            _render_review_module_row(
                mid,
                key_prefix=key_prefix,
                qa_key_prefix=qa_key_prefix,
                module_ids=module_ids,
                can_remove=can_remove,
            )


def _render_review_module_row(
    module_id: str,
    *,
    key_prefix: str,
    qa_key_prefix: str | None,
    module_ids: Sequence[str],
    can_remove: bool,
) -> None:
    label = build_module_label(module_id)
    if not can_remove:
        st.markdown(f"- {label}")
        return
    label_col, remove_col = st.columns([20, 1], vertical_alignment="center")
    with label_col:
        st.markdown(f"- {label}")
    with remove_col:
        if st.button(
            "",
            icon=ic.CLOSE,
            key=f"{key_prefix}_review_rm_{module_id}",
            help=widget_help(f"Remove from run: {label}"),
            type="tertiary",
        ):
            if apply_review_module_removal(
                st.session_state,
                key_prefix=key_prefix,
                qa_key_prefix=qa_key_prefix,
                module_ids=module_ids,
                remove_id=module_id,
            ):
                st.rerun()
            else:
                st.toast("Keep at least one module in the run.")
