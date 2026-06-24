"""Base exception carrying a stable machine-readable error code."""

from __future__ import annotations

from typing import Any, Dict, Optional


class CodedError(Exception):
    """Exception with a stable machine-readable ``error_code``."""

    error_code: str
    error_context: Optional[Dict[str, Any]]

    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        error_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.error_context = error_context
