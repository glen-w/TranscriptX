"""Shared LLM model selector for Run Analysis / Batch."""

from __future__ import annotations

import logging
from typing import Any, Sequence

import streamlit as st

from transcriptx.app.controllers.profile_controller import ProfileController
from transcriptx.core.analysis.llm_support.model_selection import (
    LLM_MODEL_CONSUMER_IDS,
    LlmModelSelection,
    selection_from_config_obj,
    selection_from_mapping,
    selection_to_profile_config,
    validate_llm_model_selection,
)
from transcriptx.core.analysis.llm_support.model_guidance import (
    list_llm_model_guidance,
)
from transcriptx.core.config import get_profile_target_adapter
from transcriptx.core.config.persistence import save_project_config
from transcriptx.core.llm import list_installed_ollama_models
from transcriptx.core.llm.thinking_models import (
    LLM_JSON_FORMAT_CONSUMER_IDS,
    filter_models_for_json_consumers,
    is_thinking_model,
    selection_uses_thinking_for_json,
)
from transcriptx.core.utils.config import get_config

_CUSTOM_PROFILE = "Custom (this run)"
_PROJECT_DEFAULT_LABEL = "Project default (active)"
_UNSET_MODEL = "(choose a model)"
_LLM_MODELS_TARGET = "llm_models"
_THINKING_MODEL_HELP = (
    "Thinking-family Ollama tags (qwen3*, deepseek-r1*, gpt-oss*, …) often leave "
    "the `response` field empty when TranscriptX requests JSON. They are excluded "
    "from picks that feed JSON modules (narrative_summary, llm_action_items, "
    "chart_descriptions, group_llm_synthesis). Prefer gemma3, qwen2.5, llama3.2, "
    "or mistral for those modules."
)

logger = logging.getLogger(__name__)


def _key(prefix: str, name: str) -> str:
    return f"{prefix}_{name}"


def _group_synthesis_enabled() -> bool:
    return bool(get_config().analysis.group_llm_synthesis.enabled)


def _include_group_consumer(include_group: bool) -> bool:
    return bool(include_group) and _group_synthesis_enabled()


def _consumer_ids(*, include_group: bool) -> list[str]:
    return [
        c
        for c in LLM_MODEL_CONSUMER_IDS
        if c != "group_llm_synthesis" or _include_group_consumer(include_group)
    ]


@st.cache_data(ttl=20, show_spinner=False)
def cached_list_ollama_models(
    base_url: str | None,
) -> tuple[tuple[str, ...], str | None]:
    """Short-TTL list of installed Ollama tags for the selector UI."""
    result = list_installed_ollama_models(base_url)
    return result.models, result.error


def _installed_choice(current: Any, installed: Sequence[str]) -> str | None:
    """Keep ``current`` only when it is an exact installed tag; else unset."""
    if isinstance(current, str) and current.strip() and current in installed:
        return current
    return None


def _seed_from_configured(
    installed: Sequence[str], configured: str | None
) -> str | None:
    """Seed widgets from a configured tag only when that tag is installed."""
    if configured and configured in installed:
        return configured
    return None


def _model_select_options(installed: Sequence[str]) -> list[str]:
    return [_UNSET_MODEL, *installed]


def _selected_json_consumers(
    selected_modules: Sequence[str],
    *,
    include_group: bool,
) -> list[str]:
    """JSON-format LLM consumers that will run for this launch."""
    selected = {str(mid) for mid in selected_modules}
    consumers: list[str] = []
    for consumer_id in sorted(LLM_JSON_FORMAT_CONSUMER_IDS):
        if consumer_id == "group_llm_synthesis":
            if _include_group_consumer(include_group):
                consumers.append(consumer_id)
            continue
        if consumer_id in selected:
            consumers.append(consumer_id)
    return consumers


def _options_for_consumer(
    installed: Sequence[str],
    *,
    consumer_id: str | None,
    json_consumers_selected: Sequence[str],
) -> list[str]:
    """Build selectbox options; hide thinking tags when the pick feeds JSON."""
    if consumer_id is None:
        needs_json_safe = bool(json_consumers_selected)
    else:
        # Always JSON-safe for JSON consumer rows (module may be toggled later).
        needs_json_safe = consumer_id in LLM_JSON_FORMAT_CONSUMER_IDS

    if needs_json_safe:
        return _model_select_options(
            filter_models_for_json_consumers(installed, include_thinking=False)
        )
    return _model_select_options(installed)


def _ensure_session_model_in_options(
    key: str,
    options: Sequence[str],
    *,
    label: str,
) -> None:
    """Clear session value when it is no longer selectable (e.g. thinking tag)."""
    current = st.session_state.get(key)
    if not isinstance(current, str) or current in options:
        return
    if current not in (_UNSET_MODEL, "") and is_thinking_model(current):
        st.caption(
            f"{label}: `{current}` is a thinking model and cannot be used for "
            "JSON LLM modules — choose a non-thinking installed model."
        )
    elif current not in (_UNSET_MODEL, ""):
        st.caption(f"{label}: `{current}` is not available — choose another model.")
    st.session_state[key] = _UNSET_MODEL


def _thinking_excluded_note(
    installed: Sequence[str],
    *,
    json_consumers_selected: Sequence[str],
) -> str | None:
    if not json_consumers_selected:
        return None
    hidden = [name for name in installed if is_thinking_model(name)]
    if not hidden:
        return None
    sample = ", ".join(f"`{n}`" for n in hidden[:4])
    extra = f" (+{len(hidden) - 4} more)" if len(hidden) > 4 else ""
    return (
        f"Hidden thinking models for JSON modules: {sample}{extra}. "
        f"{_THINKING_MODEL_HELP}"
    )


def _session_model_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text == _UNSET_MODEL:
        return None
    return text


def _profile_storage_name(label: str) -> str:
    if label == _PROJECT_DEFAULT_LABEL:
        return "default"
    return label


def _profile_display_label(storage_name: str) -> str:
    if storage_name == "default":
        return _PROJECT_DEFAULT_LABEL
    return storage_name


def _load_profile_selection(
    profile_label: str,
) -> tuple[LlmModelSelection | None, str | None]:
    """Load selection for a profile label.

    Returns ``(selection, warning)``. ``selection`` is ``None`` for Custom
    (leave widgets alone) or when falling back after corruption.
    """
    if not profile_label or profile_label == _CUSTOM_PROFILE:
        return None, None

    storage_name = _profile_storage_name(profile_label)
    if ProfileController.is_virtual_default_profile_name(storage_name):
        cfg = get_config().llm
        return selection_from_config_obj(getattr(cfg, "model_selection", None)), None

    ctrl = ProfileController()
    data = ctrl.load_profile(_LLM_MODELS_TARGET, storage_name)
    if not data or "config" not in data:
        warning = (
            f"LLM model profile `{storage_name}` is missing or corrupt; "
            "using project default selection."
        )
        logger.warning(warning)
        cfg = get_config().llm
        return selection_from_config_obj(getattr(cfg, "model_selection", None)), warning

    try:
        return selection_from_mapping(data["config"]), None
    except ValueError as exc:
        warning = (
            f"LLM model profile `{storage_name}` has invalid selection "
            f"({exc}); using project default selection."
        )
        logger.warning(warning)
        cfg = get_config().llm
        return selection_from_config_obj(getattr(cfg, "model_selection", None)), warning


def _apply_selection_to_session(
    prefix: str,
    selection: LlmModelSelection | None,
    installed: Sequence[str],
) -> list[str]:
    """Apply selection onto session keys without substituting unavailable tags.

    Returns captions explaining any unset unavailable tags.
    """
    notes: list[str] = []
    if selection is None:
        sel = LlmModelSelection(mode="shared", shared_model=None)
    else:
        sel = selection.normalized()

    st.session_state[_key(prefix, "mode")] = (
        "Select per module" if sel.mode == "per_module" else "Same model for all"
    )

    shared = _installed_choice(sel.shared_model, installed)
    if sel.shared_model and shared is None:
        notes.append(
            f"Saved model `{sel.shared_model}` is not installed — choose an installed model."
        )
    st.session_state[_key(prefix, "shared_model")] = shared or _UNSET_MODEL

    for consumer_id in LLM_MODEL_CONSUMER_IDS:
        chosen = sel.module_models.get(consumer_id) or sel.shared_model
        kept = _installed_choice(chosen, installed)
        if chosen and kept is None:
            notes.append(
                f"Saved model `{chosen}` for `{consumer_id}` is not installed — "
                "choose an installed model."
            )
        st.session_state[_key(prefix, f"module_{consumer_id}")] = kept or _UNSET_MODEL
    return notes


def build_selection_from_session(
    prefix: str,
    *,
    include_group: bool,
) -> LlmModelSelection:
    """Build a launch snapshot from widget session state."""
    mode_label = st.session_state.get(_key(prefix, "mode"), "Same model for all")
    mode = "per_module" if mode_label == "Select per module" else "shared"
    shared = _session_model_value(st.session_state.get(_key(prefix, "shared_model")))
    modules: dict[str, str] = {}
    for consumer_id in _consumer_ids(include_group=include_group):
        value = _session_model_value(
            st.session_state.get(_key(prefix, f"module_{consumer_id}"))
        )
        if value:
            modules[consumer_id] = value
    return LlmModelSelection(
        mode=mode,
        shared_model=shared,
        module_models=modules,
    ).normalized()


def launch_gate_reasons(
    *,
    selection: LlmModelSelection,
    selected_modules: Sequence[str],
    installed: Sequence[str],
    list_error: str | None,
    include_group: bool,
    llm_enabled: bool,
    provider: str,
) -> list[str]:
    """Return human-readable reasons the launch button should stay disabled."""
    reasons: list[str] = []
    from transcriptx.core.pipeline.module_registry import get_module_info

    needs_llm = False
    for mid in selected_modules:
        info = get_module_info(mid)
        if info is not None and getattr(info, "requires_llm", False):
            needs_llm = True
            break
    if _include_group_consumer(include_group):
        needs_llm = True
    if not needs_llm:
        return reasons

    if not llm_enabled or (provider or "").strip().lower() != "ollama":
        reasons.append(
            "LLM modules are selected but LLM is disabled or provider is not Ollama. "
            "Enable Ollama under Settings → Configuration."
        )
        return reasons

    if list_error:
        reasons.append(f"Cannot reach Ollama to list models: {list_error}")
    if not installed:
        reasons.append("No Ollama models are installed (empty /api/tags).")
        return reasons

    sel = selection.normalized()
    json_consumers = _selected_json_consumers(
        selected_modules, include_group=include_group
    )
    thinking_hits = selection_uses_thinking_for_json(
        mode=sel.mode,
        shared_model=sel.shared_model,
        module_models=dict(sel.module_models),
        json_consumer_ids=json_consumers,
    )
    if thinking_hits:
        joined = ", ".join(f"`{c}`" for c in thinking_hits)
        reasons.append(
            "Thinking-family models often return an empty Ollama `response` for "
            f"JSON modules ({joined}). Choose a non-thinking model such as "
            "gemma3, qwen2.5, llama3.2, or mistral."
        )

    if sel.mode == "shared":
        if not sel.shared_model or sel.shared_model not in installed:
            reasons.append("Choose an installed shared model for LLM modules.")
        return reasons

    consumers = [
        mid
        for mid in selected_modules
        if (info := get_module_info(mid)) is not None
        and getattr(info, "requires_llm", False)
    ]
    if _include_group_consumer(include_group):
        consumers = list(dict.fromkeys([*consumers, "group_llm_synthesis"]))
    for consumer_id in consumers:
        model = sel.module_models.get(consumer_id) or sel.shared_model
        if not model or model not in installed:
            reasons.append(f"Choose an installed model for `{consumer_id}`.")
    return reasons


def render_llm_model_selector(
    *,
    key_prefix: str,
    selected_modules: Sequence[str],
    include_group: bool = False,
) -> tuple[LlmModelSelection | None, list[str]]:
    """
    Render model profile / shared-vs-per-module controls.

    Returns ``(selection_or_none, gate_reasons)``. Selection is ``None`` when
    LLM is not Ollama-enabled (callers still pass ``None`` on the request).
    Gate reasons are still computed when LLM modules require a working Ollama
    setup so launch stays blocked.
    """
    config = get_config()
    llm = config.llm
    provider = (llm.provider or "null").strip().lower()
    st.markdown("#### LLM models")

    if not llm.enabled or provider != "ollama":
        st.caption(
            "LLM is disabled or not set to Ollama. Enable it in Settings to choose "
            "models for LLM-backed modules."
        )
        gates = launch_gate_reasons(
            selection=LlmModelSelection(),
            selected_modules=selected_modules,
            installed=(),
            list_error=None,
            include_group=include_group,
            llm_enabled=bool(llm.enabled),
            provider=provider,
        )
        for reason in gates:
            st.warning(reason)
        return None, gates

    base_url = llm.base_url
    installed, list_error = cached_list_ollama_models(base_url)
    if st.button("Refresh models", key=_key(key_prefix, "refresh")):
        cached_list_ollama_models.clear()
        installed, list_error = cached_list_ollama_models(base_url)
        st.rerun()

    if list_error:
        st.warning(list_error)
    if not installed:
        st.info("No installed Ollama models found. Pull a model with `ollama pull …`.")

    ctrl = ProfileController()
    profiles = ctrl.list_profiles(_LLM_MODELS_TARGET)
    profile_options = [_CUSTOM_PROFILE]
    for name in profiles:
        profile_options.append(_profile_display_label(name))
    # Deduplicate while preserving order (list_profiles already includes default).
    seen: set[str] = set()
    deduped: list[str] = []
    for opt in profile_options:
        if opt not in seen:
            seen.add(opt)
            deduped.append(opt)
    profile_options = deduped

    active = ctrl.get_active_profile(_LLM_MODELS_TARGET)
    active_label = _profile_display_label(active)
    default_ix = 0
    if active_label in profile_options:
        default_ix = profile_options.index(active_label)

    profile_key = _key(key_prefix, "profile")
    if profile_key not in st.session_state:
        st.session_state[profile_key] = profile_options[default_ix]
    elif st.session_state.get(profile_key) not in profile_options:
        preferred = (
            active_label
            if active_label in profile_options
            else profile_options[default_ix]
        )
        st.session_state[profile_key] = preferred

    selected_profile = st.selectbox(
        "LLM model profile",
        options=profile_options,
        key=profile_key,
        help=(
            f"{_PROJECT_DEFAULT_LABEL} loads the project-active llm_models pack "
            f"(or global defaults). {_CUSTOM_PROFILE} keeps this run's widgets."
        ),
    )

    applied_key = _key(key_prefix, "applied_profile")
    if st.session_state.get(applied_key) != selected_profile:
        loaded, load_warning = _load_profile_selection(selected_profile)
        if load_warning:
            st.caption(load_warning)
        if selected_profile != _CUSTOM_PROFILE:
            for note in _apply_selection_to_session(key_prefix, loaded, installed):
                st.caption(note)
        st.session_state[applied_key] = selected_profile

    mode = st.radio(
        "Model assignment",
        ["Same model for all", "Select per module"],
        horizontal=True,
        key=_key(key_prefix, "mode"),
    )

    shared_key = _key(key_prefix, "shared_model")
    json_consumers = _selected_json_consumers(
        selected_modules, include_group=include_group
    )
    thinking_note = _thinking_excluded_note(
        installed, json_consumers_selected=json_consumers
    )
    if thinking_note:
        st.info(thinking_note)

    if shared_key not in st.session_state:
        seeded = _seed_from_configured(installed, llm.model)
        # Do not seed a thinking global default into a JSON-safe shared pick.
        if (
            seeded
            and json_consumers
            and is_thinking_model(seeded)
        ):
            seeded = None
        st.session_state[shared_key] = seeded or _UNSET_MODEL
    else:
        kept = _installed_choice(st.session_state.get(shared_key), installed)
        prev = st.session_state.get(shared_key)
        if (
            isinstance(prev, str)
            and prev not in (_UNSET_MODEL, "")
            and kept is None
            and prev not in installed
        ):
            st.caption(f"Model `{prev}` is not installed — choose an installed model.")
        st.session_state[shared_key] = kept or _UNSET_MODEL

    if mode == "Same model for all":
        shared_options = (
            _options_for_consumer(
                installed,
                consumer_id=None,
                json_consumers_selected=json_consumers,
            )
            if installed
            else [_UNSET_MODEL]
        )
        _ensure_session_model_in_options(
            shared_key, shared_options, label="Shared model"
        )
        st.selectbox(
            "Model for all LLM modules",
            options=shared_options,
            key=shared_key,
            disabled=not bool(installed),
        )
    else:
        for consumer_id in _consumer_ids(include_group=include_group):
            mk = _key(key_prefix, f"module_{consumer_id}")
            if mk not in st.session_state:
                shared_val = _session_model_value(st.session_state.get(shared_key))
                st.session_state[mk] = shared_val or _UNSET_MODEL
            else:
                kept = _installed_choice(st.session_state.get(mk), installed)
                prev = st.session_state.get(mk)
                if (
                    isinstance(prev, str)
                    and prev not in (_UNSET_MODEL, "")
                    and kept is None
                    and prev not in installed
                ):
                    st.caption(
                        f"Model `{prev}` for `{consumer_id}` is not installed — "
                        "choose an installed model."
                    )
                st.session_state[mk] = kept or _UNSET_MODEL
            module_options = (
                _options_for_consumer(
                    installed,
                    consumer_id=consumer_id,
                    json_consumers_selected=json_consumers,
                )
                if installed
                else [_UNSET_MODEL]
            )
            _ensure_session_model_in_options(
                mk, module_options, label=f"Model · {consumer_id}"
            )
            st.selectbox(
                f"Model · {consumer_id}",
                options=module_options,
                key=mk,
                disabled=not bool(installed),
            )

    with st.expander("Installed models — what they're good at", expanded=False):
        st.caption(
            "Use this when assigning models per module. Avoid thinking-family "
            "tags (qwen3*, deepseek-r1*, gpt-oss*) for JSON modules — they often "
            "return an empty `response`. Prefer gemma3 / qwen2.5 / llama3.2 / "
            "mistral for narrative_summary, llm_action_items, and chart_descriptions."
        )
        rows = list_llm_model_guidance(installed)
        if not rows:
            st.info(
                "No installed models to describe. Pull one with "
                "`ollama pull gemma3:12b`, then Refresh models."
            )
        else:
            table = {
                "Model": [r.model for r in rows],
                "Class": [r.size_class for r in rows],
                "Strengths": [r.strengths for r in rows],
                "Best for": [r.best_for for r in rows],
                "Notes": [r.notes for r in rows],
            }
            st.dataframe(table, hide_index=True, width="stretch")

    with st.expander("Save as LLM model profile", expanded=False):
        name = st.text_input(
            "Profile name",
            key=_key(key_prefix, "save_name"),
            help="Cannot be 'default'. Use overwrite to replace an existing name.",
        )
        description = st.text_input(
            "Description (optional)",
            key=_key(key_prefix, "save_description"),
        )
        overwrite = st.checkbox(
            "Overwrite existing profile",
            value=False,
            key=_key(key_prefix, "save_overwrite"),
        )
        set_active = st.checkbox(
            "Set as project active profile",
            value=False,
            key=_key(key_prefix, "save_set_active"),
        )
        if st.button("Save profile", key=_key(key_prefix, "save_btn")):
            draft = build_selection_from_session(
                key_prefix, include_group=include_group
            )
            try:
                validated = validate_llm_model_selection(draft, for_profile_save=True)
            except ValueError as exc:
                st.error(str(exc))
            else:
                profile_name = (name or "").strip()
                if (
                    not profile_name
                    or ProfileController.is_virtual_default_profile_name(profile_name)
                ):
                    st.error("Enter a non-default profile name.")
                else:
                    payload = selection_to_profile_config(validated)
                    desc = description or f"LLM model profile {profile_name}"
                    if overwrite:
                        ok = ctrl.save_profile(
                            _LLM_MODELS_TARGET, profile_name, payload, description=desc
                        )
                    else:
                        ok = ctrl.create_profile(
                            _LLM_MODELS_TARGET, profile_name, payload, description=desc
                        )
                    if not ok:
                        if not overwrite:
                            st.error(
                                "Failed to save profile (it may already exist). "
                                "Enable “Overwrite existing profile” to replace it."
                            )
                        else:
                            st.error("Failed to save profile.")
                    else:
                        st.success(f"Saved LLM model profile `{profile_name}`.")
                        if set_active:
                            adapter = get_profile_target_adapter(_LLM_MODELS_TARGET)
                            if adapter is not None:
                                adapter.set_active_profile_name(config, profile_name)
                                save_project_config(config.to_dict())
                                st.info(
                                    f"Active project profile set to `{profile_name}`."
                                )

    selection = build_selection_from_session(key_prefix, include_group=include_group)
    gates = launch_gate_reasons(
        selection=selection,
        selected_modules=selected_modules,
        installed=installed,
        list_error=list_error,
        include_group=include_group,
        llm_enabled=bool(llm.enabled),
        provider=provider,
    )
    for reason in gates:
        st.warning(reason)
    return selection, gates
