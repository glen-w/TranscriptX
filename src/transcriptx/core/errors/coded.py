"""Base exception carrying a stable machine-readable error code."""

from __future__ import annotations


class CodedError(Exception):
    """Exception with a stable machine-readable ``error_code``."""

    error_code: str

    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code
