"""Shared blocked-result helpers for optional-dependency modules.

Semantic mirror for modules that need optional extras (BERTopic, semantic_v2).
Keep reason strings stable: ``missing_extra:<name>`` / ``broken_extra:<name>``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from transcriptx.core.pipeline.contracts import ErrorKind
from transcriptx.core.utils.module_result import build_module_result, now_iso


def build_optional_dep_blocked_result(
    *,
    module_name: str,
    reason: str,
    error_kind: ErrorKind = ErrorKind.DEPENDENCY,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    extra_metrics: Optional[Dict[str, Any]] = None,
    install_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a module_result envelope with ``status="blocked"`` for optional deps.

    ``reason`` should be a stable machine-readable string such as
    ``missing_extra:bertopic`` or ``broken_extra:bertopic``.
    """
    started = started_at or now_iso()
    finished = finished_at or now_iso()
    metrics: Dict[str, Any] = {
        "reason": reason,
        "error_kind": error_kind.value,
    }
    if install_hint:
        metrics["install_hint"] = install_hint
    if extra_metrics:
        metrics.update(extra_metrics)
    return build_module_result(
        module_name=module_name,
        status="blocked",
        started_at=started,
        finished_at=finished,
        artifacts=[],
        metrics=metrics,
        payload_type="analysis_results",
        payload={},
    )


def missing_extra_reason(extra_name: str) -> str:
    return f"missing_extra:{extra_name}"


def broken_extra_reason(extra_name: str) -> str:
    return f"broken_extra:{extra_name}"


def install_hint_for_extra(extra_name: str) -> str:
    return f"pip install 'transcriptx[{extra_name}]'"
