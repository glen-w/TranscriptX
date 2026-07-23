"""Run-scoped and profile-backed LLM model selection.

Resolution precedence for each consumer:
1. Explicit request / bound selection override
2. ``llm.model_selection`` (active ``llm_models`` profile applied onto config)
3. Global ``llm.model`` / ``DEFAULT_OLLAMA_MODEL``
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from transcriptx.core.llm import DEFAULT_OLLAMA_MODEL
from transcriptx.core.llm.errors import LLMModelMissingError

LLMModelSelectionMode = Literal["shared", "per_module"]

LLM_MODEL_CONSUMER_IDS: tuple[str, ...] = (
    "narrative_summary",
    "llm_summary",
    "llm_speaker_summary",
    "llm_action_items",
    "llm_custom_qa",
    "chart_descriptions",
    "group_llm_synthesis",
    "topic_shift",
)

LLM_MODEL_CONSUMER_ID_SET: frozenset[str] = frozenset(LLM_MODEL_CONSUMER_IDS)

SelectionSource = Literal["request", "profile", "global"]

_bound_selection: ContextVar["LlmModelSelection | None"] = ContextVar(
    "transcriptx_llm_model_selection", default=None
)


@dataclass(frozen=True)
class LlmModelSelection:
    """Immutable model selection snapshot (request or profile config)."""

    mode: LLMModelSelectionMode = "shared"
    shared_model: str | None = None
    module_models: Mapping[str, str] = field(default_factory=dict)

    def normalized(self) -> "LlmModelSelection":
        """Return a copy with blanks stripped and unknown keys dropped."""
        shared = _normalize_model(self.shared_model)
        modules: dict[str, str] = {}
        for key, value in dict(self.module_models or {}).items():
            kid = str(key).strip()
            if kid not in LLM_MODEL_CONSUMER_ID_SET:
                continue
            mid = _normalize_model(value)
            if mid:
                modules[kid] = mid
        mode: LLMModelSelectionMode = (
            "per_module" if self.mode == "per_module" else "shared"
        )
        return LlmModelSelection(mode=mode, shared_model=shared, module_models=modules)


@dataclass(frozen=True)
class ResolvedLlmModel:
    """Effective model tag plus where it came from."""

    model: str
    source: SelectionSource


def _normalize_model(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def selection_from_mapping(data: Mapping[str, Any] | None) -> LlmModelSelection:
    """Build a selection from a config/profile dict.

    Raises ``ValueError`` when ``mode`` is present but not ``shared`` /
    ``per_module``. Missing mode defaults to ``shared``.
    """
    if not data:
        return LlmModelSelection()
    if "mode" in data and data.get("mode") is not None:
        mode_raw = str(data.get("mode")).strip().lower()
    else:
        mode_raw = "shared"
    if mode_raw not in ("shared", "per_module"):
        raise ValueError(f"Invalid llm model selection mode: {mode_raw!r}")
    mode: LLMModelSelectionMode = mode_raw  # type: ignore[assignment]
    modules_raw = data.get("module_models") or {}
    modules: dict[str, str] = {}
    if isinstance(modules_raw, Mapping):
        for key, value in modules_raw.items():
            mid = _normalize_model(value)
            if mid:
                modules[str(key)] = mid
    return LlmModelSelection(
        mode=mode,
        shared_model=_normalize_model(data.get("shared_model")),
        module_models=modules,
    ).normalized()


def selection_from_config_obj(model_selection: Any | None) -> LlmModelSelection | None:
    """Project ``llm.model_selection`` dataclass/object to ``LlmModelSelection``.

    Soft-fails to ``None`` when the payload cannot be parsed (corrupt / invalid
    mode), so resolution can fall through to global ``llm.model``.
    """
    if model_selection is None:
        return None
    if isinstance(model_selection, LlmModelSelection):
        if model_selection.mode not in ("shared", "per_module"):
            return None
        return model_selection.normalized()
    try:
        if isinstance(model_selection, Mapping):
            return selection_from_mapping(model_selection)
        mode = getattr(model_selection, "mode", "shared")
        shared = getattr(model_selection, "shared_model", None)
        modules = getattr(model_selection, "module_models", None) or {}
        return selection_from_mapping(
            {"mode": mode, "shared_model": shared, "module_models": modules}
        )
    except ValueError:
        return None


def validate_llm_model_selection(
    selection: LlmModelSelection | Mapping[str, Any],
    *,
    for_profile_save: bool = False,
    require_shared_when_shared_mode: bool = False,
) -> LlmModelSelection:
    """Validate and normalize a selection; raise ``ValueError`` on hard failures."""
    if isinstance(selection, Mapping):
        sel = selection_from_mapping(selection)
    else:
        if selection.mode not in ("shared", "per_module"):
            raise ValueError(f"Invalid llm model selection mode: {selection.mode!r}")
        sel = selection.normalized()

    if sel.mode not in ("shared", "per_module"):
        raise ValueError(f"Invalid llm model selection mode: {sel.mode!r}")

    if for_profile_save or require_shared_when_shared_mode:
        if sel.mode == "shared" and not sel.shared_model:
            raise ValueError(
                "shared_model is required when mode is 'shared' for a saved profile"
            )
        if sel.mode == "per_module" and not sel.module_models and not sel.shared_model:
            raise ValueError(
                "per_module profile requires at least one module model or shared_model"
            )
    return sel


def selection_to_profile_config(selection: LlmModelSelection) -> dict[str, Any]:
    """Serialize a validated selection into a ProfileManager ``config`` payload."""
    normalized = selection.normalized()
    return {
        "mode": normalized.mode,
        "shared_model": normalized.shared_model,
        "module_models": dict(normalized.module_models),
    }


def get_bound_llm_model_selection() -> LlmModelSelection | None:
    return _bound_selection.get()


def bind_llm_model_selection(
    selection: LlmModelSelection | None,
) -> Token:
    """Bind a run-scoped selection; caller must ``reset_llm_model_selection(token)``."""
    return _bound_selection.set(
        selection.normalized() if selection is not None else None
    )


def reset_llm_model_selection(token: Token) -> None:
    _bound_selection.reset(token)


def resolve_module_llm_model(
    llm_cfg: Any,
    consumer_id: str,
    *,
    selection_override: LlmModelSelection | None = None,
) -> ResolvedLlmModel:
    """Resolve the effective model for one LLM consumer."""
    bound = selection_override
    if bound is None:
        bound = get_bound_llm_model_selection()

    profile_sel = selection_from_config_obj(getattr(llm_cfg, "model_selection", None))

    def _from_selection(
        sel: LlmModelSelection | None, source: SelectionSource
    ) -> str | None:
        if sel is None:
            return None
        sel = sel.normalized()
        if sel.mode == "per_module":
            per = _normalize_model(sel.module_models.get(consumer_id))
            if per:
                return per
            if sel.shared_model:
                return sel.shared_model
            return None
        return sel.shared_model

    for sel, source in ((bound, "request"), (profile_sel, "profile")):
        model = _from_selection(sel, source)  # type: ignore[arg-type]
        if model:
            return ResolvedLlmModel(model=model, source=source)  # type: ignore[arg-type]

    global_model = (
        _normalize_model(getattr(llm_cfg, "model", None)) or DEFAULT_OLLAMA_MODEL
    )
    if not global_model:
        raise LLMModelMissingError(
            f"No LLM model configured for consumer {consumer_id!r}"
        )
    return ResolvedLlmModel(model=str(global_model), source="global")


def require_resolved_model(
    llm_cfg: Any,
    consumer_id: str,
    *,
    selection_override: LlmModelSelection | None = None,
) -> ResolvedLlmModel:
    """Resolve model or raise ``LLMModelMissingError`` if empty."""
    resolved = resolve_module_llm_model(
        llm_cfg, consumer_id, selection_override=selection_override
    )
    if not resolved.model.strip():
        raise LLMModelMissingError(f"LLM model missing for consumer {consumer_id!r}")
    return resolved
