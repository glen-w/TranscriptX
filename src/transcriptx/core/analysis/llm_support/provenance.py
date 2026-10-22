"""Provenance construction for LLM analysis artifacts."""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlparse

__all__ = [
    "build_llm_provenance",
    "redact_llm_base_url",
]


def redact_llm_base_url(base_url: str | None) -> str:
    """Scheme + host + port only. Drop userinfo, path, query, and fragment."""
    raw = (base_url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except ValueError:
        return ""
    host = (parsed.hostname or "").strip()
    if not host:
        return ""
    scheme = (parsed.scheme or "http").strip().lower() or "http"
    netloc = host
    if parsed.port:
        netloc = f"{host}:{parsed.port}"
    return f"{scheme}://{netloc}"


def _configured_llm_base_url() -> str:
    try:
        from transcriptx.core.utils.config import get_config

        return str(getattr(get_config().llm, "base_url", "") or "").strip()
    except Exception:
        return ""


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
    base_url: Optional[str] = None,
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
    if model_selection_source:
        prov["model_selection_source"] = model_selection_source
    if (provider or "").strip().lower() == "openai_compatible":
        redacted = redact_llm_base_url(
            base_url if base_url is not None else _configured_llm_base_url()
        )
        if redacted:
            prov["base_url"] = redacted
    return prov
