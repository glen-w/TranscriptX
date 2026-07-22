"""Strict LLM model resolution for topic_shift enrichment (no DEFAULT fallthrough)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Sequence

from transcriptx.core.analysis.llm_support.model_selection import (
    LlmModelSelection,
    SelectionSource,
    get_bound_llm_model_selection,
    selection_from_config_obj,
    _normalize_model,
)

EnrichmentResolveStatus = Literal["ok", "skipped"]


@dataclass(frozen=True)
class TopicShiftEnrichmentModelResolution:
    status: EnrichmentResolveStatus
    model: str | None
    source: SelectionSource | None
    skip_reason: str | None = None


def _model_in_installed(model: str, installed: Sequence[str]) -> bool:
    needle = model.strip()
    if not needle:
        return False
    tags = {str(t).strip() for t in installed if str(t).strip()}
    if needle in tags:
        return True
    # Accept base tag match (configured ``foo`` vs installed ``foo:latest``)
    base = needle.split(":", 1)[0]
    if ":" not in needle:
        for tag in tags:
            if tag == base or tag.startswith(base + ":"):
                return True
    return False


def resolve_topic_shift_enrichment_model(
    llm_cfg: Any,
    *,
    selection_override: LlmModelSelection | None = None,
    allow_global_configured: bool = True,
    require_installed: bool = True,
    installed_models_provider: Callable[[], Sequence[str]] | None = None,
) -> TopicShiftEnrichmentModelResolution:
    """
    Resolve model for consumer_id=topic_shift without DEFAULT_OLLAMA_MODEL.

    Order: bound/request → profile → documented global ``llm.model`` (only if
    ``allow_global_configured`` and non-empty). Never substitutes an arbitrary default.

    When ``require_installed`` is True (default), the resolved tag must appear in
    the installed Ollama model list; otherwise outcome is ``skipped``.
    """
    consumer_id = "topic_shift"
    bound = selection_override
    if bound is None:
        bound = get_bound_llm_model_selection()
    profile_sel = selection_from_config_obj(getattr(llm_cfg, "model_selection", None))

    def _from_selection(sel: LlmModelSelection | None) -> str | None:
        if sel is None:
            return None
        sel = sel.normalized()
        if sel.mode == "per_module":
            per = _normalize_model(sel.module_models.get(consumer_id))
            if per:
                return per
            return _normalize_model(sel.shared_model)
        return _normalize_model(sel.shared_model)

    resolved_model: str | None = None
    resolved_source: SelectionSource | None = None
    for sel, source in ((bound, "request"), (profile_sel, "profile")):
        model = _from_selection(sel)
        if model:
            resolved_model = model
            resolved_source = source  # type: ignore[assignment]
            break

    if resolved_model is None and allow_global_configured:
        global_model = _normalize_model(getattr(llm_cfg, "model", None))
        if global_model:
            resolved_model = global_model
            resolved_source = "global"

    if not resolved_model:
        return TopicShiftEnrichmentModelResolution(
            status="skipped",
            model=None,
            source=None,
            skip_reason=(
                "no_configured_model" if allow_global_configured else "no_binding"
            ),
        )

    if not require_installed:
        return TopicShiftEnrichmentModelResolution(
            status="ok", model=resolved_model, source=resolved_source
        )

    installed: Sequence[str]
    probe_error: str | None = None
    if installed_models_provider is not None:
        try:
            installed = list(installed_models_provider())
        except Exception as exc:  # noqa: BLE001
            installed = ()
            probe_error = str(exc)
    else:
        try:
            from transcriptx.core.llm.ollama_client import list_installed_ollama_models

            result = list_installed_ollama_models(
                getattr(llm_cfg, "base_url", None),
                timeout=float(getattr(llm_cfg, "availability_timeout", 5.0) or 5.0),
            )
            installed = list(result.models)
            probe_error = result.error
        except Exception as exc:  # noqa: BLE001
            installed = ()
            probe_error = str(exc)

    if probe_error and not installed:
        return TopicShiftEnrichmentModelResolution(
            status="skipped",
            model=resolved_model,
            source=resolved_source,
            skip_reason="ollama_unreachable",
        )
    if not _model_in_installed(resolved_model, installed):
        return TopicShiftEnrichmentModelResolution(
            status="skipped",
            model=resolved_model,
            source=resolved_source,
            skip_reason="model_not_installed",
        )
    return TopicShiftEnrichmentModelResolution(
        status="ok", model=resolved_model, source=resolved_source
    )
