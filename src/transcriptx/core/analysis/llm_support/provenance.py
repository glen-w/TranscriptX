"""Provenance construction for LLM analysis artifacts."""

from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = [
    "build_llm_provenance",
]


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
) -> Dict[str, Any]:
    try:
        from transcriptx import __version__ as transcriptx_version
    except Exception:
        transcriptx_version = None

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
    return prov
