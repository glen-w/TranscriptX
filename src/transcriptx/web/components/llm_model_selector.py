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
    LibraryMeta,
    fetch_ollama_library_meta,
    list_llm_model_guidance,
    producer_for_model,
)
from transcriptx.core.config import get_profile_target_adapter
from transcriptx.core.config.persistence import save_project_config
from transcriptx.core.llm import (
    OllamaModelInfo,
    enrich_model_infos_with_context,
    list_installed_ollama_models,
)
from transcriptx.core.llm.thinking_models import (
    LLM_JSON_FORMAT_CONSUMER_IDS,
    filter_models_for_json_consumers,
    is_thinking_model,
    selection_uses_thinking_for_json,
)
from transcriptx.core.utils.config import get_config
from transcriptx.web.components.info_tooltip import widget_help

_CUSTOM_PROFILE = "Custom (this run)"
_PROJECT_DEFAULT_LABEL = "Project default (active)"
_UNSET_MODEL = "(choose a model)"
_LLM_MODELS_TARGET = "llm_models"

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


@st.cache_data(ttl=120, show_spinner=False)
def cached_ollama_model_infos(
    base_url: str | None,
    model_names: tuple[str, ...],
) -> tuple[dict[str, dict[str, object | None]], str | None]:
    """Cached installed-model metadata (params/context/size) for the info table.

    ``model_names`` is part of the cache key so a refresh after pull/delete
    invalidates correctly. Values are plain dicts for Streamlit cache hashing.
    """
    result = list_installed_ollama_models(base_url)
    if result.error:
        return {}, result.error
    infos = enrich_model_infos_with_context(result.infos, base_url)
    # Keep only currently requested names (stable order not required here).
    wanted = set(model_names)
    payload: dict[str, dict[str, object | None]] = {}
    for info in infos:
        if info.name not in wanted:
            continue
        payload[info.name] = {
            "name": info.name,
            "size_bytes": info.size_bytes,
            "modified_at": info.modified_at,
            "family": info.family,
            "parameter_size": info.parameter_size,
            "quantization_level": info.quantization_level,
            "context_length": info.context_length,
        }
    return payload, None


@st.cache_data(ttl=86_400, show_spinner=False)
def cached_ollama_library_meta(model_base: str) -> dict[str, str | None] | None:
    """Daily-cached Ollama library meta (producer hints). Soft-fails offline."""
    meta = fetch_ollama_library_meta(model_base)
    if meta is None:
        return None
    return {
        "producer": meta.producer,
        "released": meta.released,
        "description": meta.description,
    }


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


def _with_global_model_fallback(
    selection: LlmModelSelection | None,
    *,
    global_model: str | None,
) -> LlmModelSelection:
    """Fill empty ``shared_model`` from global ``llm.model`` (runtime precedence)."""
    sel = (selection or LlmModelSelection()).normalized()
    fallback = (global_model or "").strip() or None
    if not fallback or sel.shared_model:
        return sel
    return LlmModelSelection(
        mode=sel.mode,
        shared_model=fallback,
        module_models=dict(sel.module_models),
    )


def _project_default_selection() -> LlmModelSelection:
    """Effective Project default pack: ``model_selection``, then ``llm.model``."""
    cfg = get_config().llm
    return _with_global_model_fallback(
        selection_from_config_obj(getattr(cfg, "model_selection", None)),
        global_model=getattr(cfg, "model", None),
    )


def _load_profile_selection(
    profile_label: str,
) -> tuple[LlmModelSelection | None, str | None]:
    """Load selection for a profile label.

    Returns ``(selection, warning)``. ``selection`` is ``None`` for Custom
    (leave widgets alone).
    """
    if not profile_label or profile_label == _CUSTOM_PROFILE:
        return None, None

    storage_name = _profile_storage_name(profile_label)
    if ProfileController.is_virtual_default_profile_name(storage_name):
        return _project_default_selection(), None

    ctrl = ProfileController()
    data = ctrl.load_profile(_LLM_MODELS_TARGET, storage_name)
    if not data or "config" not in data:
        warning = (
            f"LLM model profile `{storage_name}` is missing or corrupt; "
            "using project default selection."
        )
        logger.warning(warning)
        return _project_default_selection(), warning

    try:
        return selection_from_mapping(data["config"]), None
    except ValueError as exc:
        warning = (
            f"LLM model profile `{storage_name}` has invalid selection "
            f"({exc}); using project default selection."
        )
        logger.warning(warning)
        return _project_default_selection(), warning


def _selection_has_wanted_models(selection: LlmModelSelection | None) -> bool:
    if selection is None:
        return False
    sel = selection.normalized()
    return bool(sel.shared_model) or bool(sel.module_models)


def _session_missing_installable_selection(
    prefix: str,
    selection: LlmModelSelection | None,
    installed: Sequence[str],
) -> bool:
    """True when profile widgets are unset but an installable configured tag exists."""
    if selection is None or not installed:
        return False
    sel = selection.normalized()
    if sel.mode != "per_module":
        wanted = _installed_choice(sel.shared_model, installed)
        if not wanted:
            return False
        return (
            _session_model_value(st.session_state.get(_key(prefix, "shared_model")))
            is None
        )
    for consumer_id in LLM_MODEL_CONSUMER_IDS:
        chosen = sel.module_models.get(consumer_id) or sel.shared_model
        kept = _installed_choice(chosen, installed)
        if not kept:
            continue
        current = _session_model_value(
            st.session_state.get(_key(prefix, f"module_{consumer_id}"))
        )
        if current is None:
            return True
    return False


def _apply_profile_to_session(
    prefix: str,
    profile_label: str,
    installed: Sequence[str],
    *,
    applied_key: str,
) -> None:
    """Apply a non-Custom profile onto widgets; defer lock while tags are still empty."""
    if profile_label == _CUSTOM_PROFILE:
        st.session_state[applied_key] = profile_label
        return

    loaded, load_warning = _load_profile_selection(profile_label)
    needs_apply = st.session_state.get(applied_key) != profile_label or (
        _session_missing_installable_selection(prefix, loaded, installed)
    )
    if not needs_apply:
        return
    if load_warning:
        st.caption(load_warning)
    for note in _apply_selection_to_session(prefix, loaded, installed):
        st.caption(note)
    # Do not lock while Ollama tags are still empty and the pack names a model —
    # otherwise the first empty list permanently leaves "(choose a model)".
    if installed or not _selection_has_wanted_models(loaded):
        st.session_state[applied_key] = profile_label


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
    if sel.shared_model and shared is None and installed:
        notes.append(
            f"Saved model `{sel.shared_model}` is not installed — choose an installed model."
        )
    st.session_state[_key(prefix, "shared_model")] = shared or _UNSET_MODEL

    for consumer_id in LLM_MODEL_CONSUMER_IDS:
        chosen = sel.module_models.get(consumer_id) or sel.shared_model
        kept = _installed_choice(chosen, installed)
        if chosen and kept is None and installed:
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


def _consumer_needs_live_llm(module_name: str) -> bool:
    try:
        from transcriptx.core.analysis.llm_custom_qa.gating import (
            consumer_requires_live_llm,
        )

        return consumer_requires_live_llm(module_name)
    except Exception:
        return True


def selection_needs_live_llm(
    selected_modules: Sequence[str],
    *,
    include_group: bool = False,
) -> bool:
    """True when this launch will invoke a live LLM consumer.

    Matches launch-gate eligibility: registry ``requires_llm`` modules that
    still need a live call, plus enabled group LLM synthesis when applicable.
    """
    from transcriptx.core.pipeline.module_registry import get_module_info

    for mid in selected_modules:
        info = get_module_info(mid)
        if info is not None and getattr(info, "requires_llm", False):
            if _consumer_needs_live_llm(mid):
                return True
    return _include_group_consumer(include_group)


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

    if not selection_needs_live_llm(selected_modules, include_group=include_group):
        return reasons

    if not llm_enabled or (provider or "").strip().lower() != "ollama":
        reasons.append(
            "LLM modules are selected but LLM is disabled or provider is not Ollama. "
            "Enable Ollama under Settings → Configuration; manage models under "
            "Settings → Models."
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
            f"JSON modules ({joined}). Choose a non-thinking mid/large model such as "
            "gemma3:12b, qwen2.5:7b, or mistral — avoid tiny/small tags for "
            "llm_action_items."
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
        and _consumer_needs_live_llm(mid)
    ]
    if _include_group_consumer(include_group):
        consumers = list(dict.fromkeys([*consumers, "group_llm_synthesis"]))
    for consumer_id in consumers:
        model = sel.module_models.get(consumer_id) or sel.shared_model
        if not model or model not in installed:
            reasons.append(f"Choose an installed model for `{consumer_id}`.")
    return reasons


def _active_model_summary_label() -> str:
    """Human label for the project-active / configured model."""
    norm = _project_default_selection()
    if norm.mode == "per_module" and norm.module_models:
        n = len(norm.module_models)
        return f"{n} model assignments"
    return (norm.shared_model or "not configured").strip() or "not configured"


def _footer_model_label(selection: LlmModelSelection | None) -> str:
    if selection is None:
        return _active_model_summary_label()
    norm = selection.normalized()
    if norm.mode == "per_module" and norm.module_models:
        n = len({*norm.module_models.values()})
        if n > 1:
            return "Mixed models"
        if n == 1:
            return next(iter(norm.module_models.values()))
        return f"{len(norm.module_models)} model assignments"
    return (norm.shared_model or _active_model_summary_label()).strip()


def _render_model_information(installed: Sequence[str]) -> None:
    """Guidance table for installed Ollama tags (Run Analysis + Settings)."""
    st.caption(
        "Use this when assigning models per module. Avoid thinking-family "
        "tags (qwen3*, deepseek-r1*, gpt-oss*) for JSON modules — they often "
        "return an empty `response`. Prefer mid/large non-thinking tags "
        "(gemma3:12b+, qwen2.5:7b+, mistral) for narrative_summary, "
        "llm_action_items, and chart_descriptions. Tiny/small tags "
        "(e.g. llama3.2:3b, gemma3:1b) usually cannot satisfy "
        "llm_action_items schema validation and publish empty extracts."
    )
    if not installed:
        st.info(
            "No installed models to describe. Pull one with "
            "`ollama pull gemma3:12b`, then refresh models under Settings → Models."
        )
        return

    config = get_config()
    base_url = config.llm.base_url
    info_payload, info_error = cached_ollama_model_infos(base_url, tuple(installed))
    if info_error:
        st.caption(f"Model metadata unavailable: {info_error}")

    infos = [
        OllamaModelInfo(
            name=str(row["name"] or name),
            size_bytes=(
                row.get("size_bytes")
                if isinstance(row.get("size_bytes"), int)
                else None
            ),
            modified_at=(
                row.get("modified_at")
                if isinstance(row.get("modified_at"), str)
                else None
            ),
            family=row.get("family") if isinstance(row.get("family"), str) else None,
            parameter_size=(
                row.get("parameter_size")
                if isinstance(row.get("parameter_size"), str)
                else None
            ),
            quantization_level=(
                row.get("quantization_level")
                if isinstance(row.get("quantization_level"), str)
                else None
            ),
            context_length=(
                row.get("context_length")
                if isinstance(row.get("context_length"), int)
                else None
            ),
        )
        for name, row in info_payload.items()
    ]

    library_meta_by_base: dict[str, LibraryMeta] = {}
    for tag in installed:
        base = tag.split(":", 1)[0].strip().lower()
        if not base or base in library_meta_by_base:
            continue
        # Skip network when the curated catalog already knows the producer.
        if producer_for_model(tag):
            continue
        raw_meta = cached_ollama_library_meta(base)
        if not raw_meta:
            continue
        library_meta_by_base[base] = LibraryMeta(
            producer=raw_meta.get("producer"),
            released=raw_meta.get("released"),
            description=raw_meta.get("description"),
        )

    rows = list_llm_model_guidance(
        installed,
        infos=infos,
        library_meta_by_base=library_meta_by_base,
    )
    table = {
        "Model": [r.model for r in rows],
        "Class": [r.size_class for r in rows],
        "Parameters": [r.parameters or "—" for r in rows],
        "Context": [r.context_window or "—" for r in rows],
        "Producer": [r.producer or "—" for r in rows],
        "Released": [r.released or "—" for r in rows],
        "Size": [r.disk_size or "—" for r in rows],
        "Strengths": [r.strengths for r in rows],
        "Best for": [r.best_for for r in rows],
        "Notes": [r.notes for r in rows],
    }
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption(
        "Parameters, context, and size come from the local Ollama API. "
        "Producer / release month use a curated catalog, refined from the "
        "public Ollama library page when reachable."
    )


def _render_assignment_widgets(
    *,
    key_prefix: str,
    selected_modules: Sequence[str],
    include_group: bool,
    installed: Sequence[str],
    llm_model: str | None,
) -> None:
    mode = st.radio(
        "Model assignment",
        ["Same model for all", "Select per module"],
        horizontal=True,
        key=_key(key_prefix, "mode"),
        help=widget_help(
            "Same model applies one Ollama tag to every selected LLM module; per-module lets you mix."
        ),
    )
    shared_key = _key(key_prefix, "shared_model")
    json_consumers = _selected_json_consumers(
        selected_modules, include_group=include_group
    )
    if shared_key not in st.session_state:
        seeded = _seed_from_configured(installed, llm_model)
        if seeded and json_consumers and is_thinking_model(seeded):
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
        return

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


def render_compact_llm_setup(
    *,
    key_prefix: str,
    selected_modules: Sequence[str],
    include_group: bool = False,
) -> tuple[LlmModelSelection | None, list[str], str]:
    """
    Per-run LLM setup only (no refresh / preset CRUD / set-active).

    Hidden when the effective module list (and optional group synthesis) does
    not need a live LLM. Returns ``(selection_or_none, gate_reasons,
    footer_model_label)``.
    """
    if not selection_needs_live_llm(selected_modules, include_group=include_group):
        return None, [], "no LLM modules"

    config = get_config()
    llm = config.llm
    provider = (llm.provider or "null").strip().lower()
    summary = _active_model_summary_label()

    st.markdown("#### LLM setup")
    st.caption(f"Project default · `{summary}`")

    if not llm.enabled or provider != "ollama":
        st.caption(
            "LLM is disabled or not set to Ollama. Enable it under "
            "Settings → Configuration; manage Model presets under Settings → Models."
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
            st.caption(reason)
        return None, gates, summary

    installed, list_error = cached_list_ollama_models(llm.base_url)
    if list_error:
        st.caption(
            f"Ollama unavailable: {list_error}. Manage models in Settings → Models."
        )
    if not installed and not list_error:
        st.caption(
            "No installed Ollama models found. Pull a model, then open "
            "Settings → Models."
        )

    # Seed widgets from the selected Model preset (defaults to project-active).
    active = ProfileController().get_active_profile(_LLM_MODELS_TARGET)
    active_label = _profile_display_label(active)
    applied_key = _key(key_prefix, "applied_profile")
    profile_key = _key(key_prefix, "profile")

    with st.expander("Change for this run", expanded=False):
        st.caption(
            "Overrides apply to this launch only. Create or activate Model presets "
            "in Settings → Models."
        )
        profile_options = [_CUSTOM_PROFILE]
        for name in ProfileController().list_profiles(_LLM_MODELS_TARGET):
            label = _profile_display_label(name)
            if label not in profile_options:
                profile_options.append(label)
        if profile_key not in st.session_state:
            st.session_state[profile_key] = (
                active_label if active_label in profile_options else profile_options[0]
            )
        elif st.session_state.get(profile_key) not in profile_options:
            st.session_state[profile_key] = (
                active_label if active_label in profile_options else profile_options[0]
            )
        selected_profile = st.selectbox(
            "Model preset",
            options=profile_options,
            key=profile_key,
            help=widget_help(
                (
                    f"{_PROJECT_DEFAULT_LABEL} loads the project-active pack. "
                    f"{_CUSTOM_PROFILE} keeps this run's widgets."
                )
            ),
        )
        _apply_profile_to_session(
            key_prefix, selected_profile, installed, applied_key=applied_key
        )

        _render_assignment_widgets(
            key_prefix=key_prefix,
            selected_modules=selected_modules,
            include_group=include_group,
            installed=installed,
            llm_model=llm.model,
        )

        with st.expander("Model information", expanded=False):
            _render_model_information(installed)

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
        st.caption(reason)
    return selection, gates, _footer_model_label(selection)


def render_llm_models_settings_panel() -> None:
    """Settings → Models: refresh, guidance table, create/overwrite, set active."""
    key_prefix = "settings_llm_models"
    config = get_config()
    llm = config.llm
    provider = (llm.provider or "null").strip().lower()

    st.markdown("#### Model presets")
    st.caption(
        "Manage Ollama tags and Model presets used by analysis. "
        "Run Analysis only overrides models for a single launch."
    )

    if not llm.enabled or provider != "ollama":
        st.info(
            "LLM is disabled or provider is not Ollama. Enable Ollama under "
            "Settings → Configuration before managing models."
        )
        return

    installed, list_error = cached_list_ollama_models(llm.base_url)
    if st.button("Refresh models", key=_key(key_prefix, "refresh")):
        cached_list_ollama_models.clear()
        cached_ollama_model_infos.clear()
        cached_ollama_library_meta.clear()
        st.rerun()

    if list_error:
        st.warning(list_error)
    if not installed:
        st.info("No installed Ollama models found. Pull a model with `ollama pull …`.")

    ctrl = ProfileController()
    profiles = ctrl.list_profiles(_LLM_MODELS_TARGET)
    profile_options = [_CUSTOM_PROFILE]
    for name in profiles:
        label = _profile_display_label(name)
        if label not in profile_options:
            profile_options.append(label)

    active = ctrl.get_active_profile(_LLM_MODELS_TARGET)
    active_label = _profile_display_label(active)
    st.caption(f"Project active Model preset: **{active_label}**")

    profile_key = _key(key_prefix, "profile")
    if profile_key not in st.session_state:
        st.session_state[profile_key] = (
            active_label if active_label in profile_options else profile_options[0]
        )
    elif st.session_state.get(profile_key) not in profile_options:
        st.session_state[profile_key] = (
            active_label if active_label in profile_options else profile_options[0]
        )

    selected_profile = st.selectbox(
        "Model preset",
        options=profile_options,
        key=profile_key,
    )
    applied_key = _key(key_prefix, "applied_profile")
    _apply_profile_to_session(
        key_prefix, selected_profile, installed, applied_key=applied_key
    )

    _render_assignment_widgets(
        key_prefix=key_prefix,
        selected_modules=(),
        include_group=True,
        installed=installed,
        llm_model=llm.model,
    )

    st.markdown("##### Model information")
    _render_model_information(installed)

    st.markdown("##### Save as Model preset")
    name = st.text_input(
        "Preset name",
        key=_key(key_prefix, "save_name"),
        help=widget_help(
            "Cannot be 'default'. Use overwrite to replace an existing name."
        ),
    )
    description = st.text_input(
        "Description (optional)",
        key=_key(key_prefix, "save_description"),
    )
    overwrite = st.checkbox(
        "Overwrite existing preset",
        value=False,
        key=_key(key_prefix, "save_overwrite"),
    )
    set_active = st.checkbox(
        "Set as project active preset",
        value=False,
        key=_key(key_prefix, "save_set_active"),
    )
    if st.button("Save preset", key=_key(key_prefix, "save_btn")):
        draft = build_selection_from_session(key_prefix, include_group=True)
        try:
            validated = validate_llm_model_selection(draft, for_profile_save=True)
        except ValueError as exc:
            st.error(str(exc))
        else:
            profile_name = (name or "").strip()
            if not profile_name or ProfileController.is_virtual_default_profile_name(
                profile_name
            ):
                st.error("Enter a non-default preset name.")
            else:
                payload = selection_to_profile_config(validated)
                desc = description or f"Model preset {profile_name}"
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
                            "Failed to save preset (it may already exist). "
                            "Enable “Overwrite existing preset” to replace it."
                        )
                    else:
                        st.error("Failed to save preset.")
                else:
                    st.success(f"Saved Model preset `{profile_name}`.")
                    if set_active:
                        adapter = get_profile_target_adapter(_LLM_MODELS_TARGET)
                        if adapter is not None:
                            adapter.set_active_profile_name(config, profile_name)
                            save_project_config(config.to_dict())
                            st.info(f"Active project preset set to `{profile_name}`.")


def render_llm_model_selector(
    *,
    key_prefix: str,
    selected_modules: Sequence[str],
    include_group: bool = False,
) -> tuple[LlmModelSelection | None, list[str]]:
    """Compatibility wrapper → compact run setup (no management actions)."""
    selection, gates, _label = render_compact_llm_setup(
        key_prefix=key_prefix,
        selected_modules=selected_modules,
        include_group=include_group,
    )
    return selection, gates
