"""Settings → Analysis panel for UI preset policies and overrides."""

from __future__ import annotations

from typing import Any

import streamlit as st

from transcriptx.core.analysis.selection import is_heavy_module
from transcriptx.core.config.persistence import patch_project_config_keys
from transcriptx.core.pipeline.module_registry import (
    get_module_info,
    get_module_registry,
)
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.config.analysis import (
    default_ui_presets_dict,
    validate_ui_presets_dict,
)
from transcriptx.web.module_option_format import format_module_option
from transcriptx.web.components.info_tooltip import widget_help

_PRESET_KEYS = ("quick", "balanced", "thorough")
_PRESET_TITLES = {
    "quick": "Quick",
    "balanced": "Balanced",
    "thorough": "Thorough",
}


def _catalogue_module_ids() -> list[str]:
    reg = get_module_registry()
    out: list[str] = []
    for mid in reg.get_available_modules():
        info = get_module_info(mid)
        if info is None or info.legacy:
            continue
        out.append(mid)
    return out


def _llm_module_ids(catalogue: list[str]) -> list[str]:
    return [
        mid
        for mid in catalogue
        if bool(getattr(get_module_info(mid), "requires_llm", False))
    ]


def _heavy_module_ids(catalogue: list[str]) -> list[str]:
    return [mid for mid in catalogue if is_heavy_module(get_module_info(mid))]


def _policy_to_dict(policy: Any) -> dict[str, Any]:
    return {
        "allow_llm": bool(getattr(policy, "allow_llm", False)),
        "llm_module_ids": list(getattr(policy, "llm_module_ids", None) or []),
        "allow_heavy": bool(getattr(policy, "allow_heavy", False)),
        "heavy_module_ids": list(getattr(policy, "heavy_module_ids", None) or []),
        "include_excluded_from_default": bool(
            getattr(policy, "include_excluded_from_default", False)
        ),
        "module_ids": (
            None
            if getattr(policy, "module_ids", None) is None
            else list(getattr(policy, "module_ids") or [])
        ),
    }


def _seed_draft_from_config() -> dict[str, dict[str, Any]]:
    cfg = get_config().analysis.ui_presets
    return {key: _policy_to_dict(getattr(cfg, key)) for key in _PRESET_KEYS}


def _seed_draft_from_defaults() -> dict[str, dict[str, Any]]:
    return default_ui_presets_dict()


def _render_preset_editor(
    preset_key: str,
    draft: dict[str, Any],
    *,
    catalogue: list[str],
    llm_options: list[str],
    heavy_options: list[str],
    gen: int,
) -> None:
    title = _PRESET_TITLES[preset_key]
    st.markdown(f"#### {title}")
    prefix = f"settings_ui_presets_{gen}_{preset_key}"

    draft["allow_llm"] = st.checkbox(
        "Allow LLM modules",
        value=bool(draft.get("allow_llm")),
        key=f"{prefix}_allow_llm",
        help=widget_help(
            "When off, modules marked requires_llm are excluded from this preset."
        ),
    )
    if draft["allow_llm"]:
        draft["llm_module_ids"] = st.multiselect(
            "LLM allowlist (empty = all LLM modules)",
            options=llm_options,
            default=[
                m for m in (draft.get("llm_module_ids") or []) if m in llm_options
            ],
            format_func=format_module_option,
            key=f"{prefix}_llm_ids",
            help=widget_help(
                "Leave empty to allow every LLM module; otherwise only the listed ones run."
            ),
        )
    else:
        draft["llm_module_ids"] = list(draft.get("llm_module_ids") or [])

    draft["allow_heavy"] = st.checkbox(
        "Allow heavy modules",
        value=bool(draft.get("allow_heavy")),
        key=f"{prefix}_allow_heavy",
        help=widget_help("Heavy = registry cost_tier or category marked heavy."),
    )
    if draft["allow_heavy"]:
        draft["heavy_module_ids"] = st.multiselect(
            "Heavy allowlist (empty = all heavy modules)",
            options=heavy_options,
            default=[
                m for m in (draft.get("heavy_module_ids") or []) if m in heavy_options
            ],
            format_func=format_module_option,
            key=f"{prefix}_heavy_ids",
            help=widget_help(
                "Leave empty to allow every heavy module; otherwise only the listed ones run."
            ),
        )
    else:
        draft["heavy_module_ids"] = list(draft.get("heavy_module_ids") or [])

    draft["include_excluded_from_default"] = st.checkbox(
        "Include exclude-from-default modules",
        value=bool(draft.get("include_excluded_from_default")),
        key=f"{prefix}_excl",
        help=widget_help(
            "Opt in registry modules marked exclude_from_default (usually experimental)."
        ),
    )

    use_override = st.checkbox(
        "Override with explicit module list",
        value=draft.get("module_ids") is not None,
        key=f"{prefix}_use_override",
        help=widget_help(
            "When enabled, policy filters are ignored and only this list runs."
        ),
    )
    if use_override:
        current = list(draft.get("module_ids") or [])
        draft["module_ids"] = st.multiselect(
            "Module override",
            options=catalogue,
            default=[m for m in current if m in catalogue],
            format_func=format_module_option,
            key=f"{prefix}_override",
            help=widget_help(
                "Exact module set for this preset when override is enabled."
            ),
        )
    else:
        draft["module_ids"] = None


def render_analysis_presets_panel() -> None:
    """Edit Quick / Balanced / Thorough policies; save to project config."""
    st.subheader("Analysis presets")
    st.caption(
        "Defines what Quick, Balanced, and Thorough include when you launch analysis. "
        "Run Analysis / Batch still choose which preset to use. "
        "Custom on those pages remains a one-off module picker."
    )

    catalogue = _catalogue_module_ids()
    llm_options = _llm_module_ids(catalogue)
    heavy_options = _heavy_module_ids(catalogue)

    if "settings_ui_presets_draft" not in st.session_state:
        st.session_state["settings_ui_presets_draft"] = _seed_draft_from_config()
    if "settings_ui_presets_gen" not in st.session_state:
        st.session_state["settings_ui_presets_gen"] = 0

    draft_root: dict[str, dict[str, Any]] = st.session_state[
        "settings_ui_presets_draft"
    ]
    gen = int(st.session_state["settings_ui_presets_gen"])

    tabs = st.tabs([_PRESET_TITLES[k] for k in _PRESET_KEYS])
    for tab, key in zip(tabs, _PRESET_KEYS):
        with tab:
            _render_preset_editor(
                key,
                draft_root[key],
                catalogue=catalogue,
                llm_options=llm_options,
                heavy_options=heavy_options,
                gen=gen,
            )

    col_save, col_reset = st.columns(2)
    with col_save:
        save = st.button(
            "Save presets",
            type="primary",
            key="settings_ui_presets_save",
        )
    with col_reset:
        reset = st.button(
            "Reset to defaults",
            key="settings_ui_presets_reset",
        )

    if reset:
        st.session_state["settings_ui_presets_draft"] = _seed_draft_from_defaults()
        st.session_state["settings_ui_presets_gen"] = gen + 1
        st.info("Draft reset to built-in defaults (not saved yet).")
        st.rerun()

    if save:
        payload = {key: dict(draft_root[key]) for key in _PRESET_KEYS}
        try:
            dumped = validate_ui_presets_dict(payload)
        except Exception as exc:
            st.error(f"Invalid preset settings: {exc}")
            return
        patch_project_config_keys({"analysis": {"ui_presets": dumped}})
        cfg = get_config().analysis.ui_presets
        for key in _PRESET_KEYS:
            policy = getattr(cfg, key)
            src = dumped[key]
            policy.allow_llm = src["allow_llm"]
            policy.llm_module_ids = list(src["llm_module_ids"])
            policy.allow_heavy = src["allow_heavy"]
            policy.heavy_module_ids = list(src["heavy_module_ids"])
            policy.include_excluded_from_default = src["include_excluded_from_default"]
            policy.module_ids = src["module_ids"]
        st.session_state["settings_ui_presets_draft"] = _seed_draft_from_config()
        st.session_state["settings_ui_presets_gen"] = gen + 1
        st.success("Saved analysis presets to project config.")
        st.rerun()
