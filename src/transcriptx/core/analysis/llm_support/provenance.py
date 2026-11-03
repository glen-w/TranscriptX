"""Provenance construction for LLM analysis artifacts."""

from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = [
    "build_llm_provenance",
    "json_generate_provenance_fields",
]


def json_generate_provenance_fields(
    *,
    model: str,
    model_selection_source: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Prefer the producing JSON model; stamp ``fallback`` when secondary was used."""
    try:
        from transcriptx.core.llm.json_with_fallback import (
            get_last_json_generate_outcome,
        )
    except Exception:
        return model, model_selection_source
    outcome = get_last_json_generate_outcome()
    if outcome is None:
        return model, model_selection_source
    producing = (outcome.model or "").strip() or model
    source = "fallback" if outcome.used_fallback else model_selection_source
    return producing, source


def build_llm_provenance(
    *,
    module_name: str,
    prompt_version: str,
    provider: str,
    model: str,
    seed: int,
    temperature: float,
    max_output_tokens: Optional[int],
    llm_request_sha256: str,
    generation_options: Optional[Dict[str, Any]] = None,
    source_module: Optional[str] = None,
    source_result_sha256: Optional[str] = None,
    truncation: Optional[Dict[str, Any]] = None,
    model_digest: Optional[str] = None,
    model_selection_source: Optional[str] = None,
    apply_json_outcome: bool = False,
) -> Dict[str, Any]:
    try:
        from transcriptx import __version__ as transcriptx_version
    except Exception:
        transcriptx_version = None

    if apply_json_outcome:
        model, model_selection_source = json_generate_provenance_fields(
            model=model,
            model_selection_source=model_selection_source,
        )

    prov: Dict[str, Any] = {
        "module": module_name,
        "prompt_version": prompt_version,
        "provider": provider,
        "model": model,
        "seed": seed,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "llm_request_sha256": llm_request_sha256,
        "transcriptx_version": transcriptx_version,
        "generation_options": generation_options or {},
    }
    if source_module:
        prov["source_module"] = source_module
    if source_result_sha256:
        prov["source_result_sha256"] = source_result_sha256
    if truncation:
        prov.update(truncation)
    if model_digest:
        prov["model_digest"] = model_digest
    if model_selection_source:
        prov["model_selection_source"] = model_selection_source
    return prov
