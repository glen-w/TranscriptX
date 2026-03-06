"""
Standard module result envelope utilities.
"""

from __future__ import annotations

from datetime import datetime
import traceback
from typing import Any, Dict, List, Optional


TRACEBACK_LIMIT = 50_000  # bytes/characters cap


def _cap_traceback(text: str) -> str:
    if len(text) <= TRACEBACK_LIMIT:
        return text
    return text[-TRACEBACK_LIMIT:]


def capture_exception(error: Exception) -> Dict[str, Any]:
    return {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback_text": _cap_traceback(traceback.format_exc()),
    }


def build_module_result(
    module_name: str,
    status: str,
    started_at: str,
    finished_at: str,
    artifacts: Optional[List[Dict[str, Any]]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    payload_type: Optional[str] = None,
    payload_schema: Optional[str] = None,
    payload: Optional[Any] = None,
    error: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "module_name": module_name,
        "module": module_name,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts or [],
        "metrics": metrics or {},
        "payload_type": payload_type or "generic",
        "payload_schema": payload_schema,
        "payload": payload if payload is not None else {},
        "results": payload if payload is not None else {},
        "error": error,
    }


def now_iso() -> str:
    return datetime.utcnow().isoformat()
