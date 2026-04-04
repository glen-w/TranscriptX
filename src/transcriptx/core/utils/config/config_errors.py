"""Structured errors for configuration loading."""

from __future__ import annotations

from typing import Literal

ConfigErrorCode = Literal[
    "unknown_section",
    "unsupported_key",
    "unsupported_legacy_shape",
    "invalid_value",
]


class ConfigLoadError(ValueError):
    """Raised when JSON config or environment violates the supported contract."""

    def __init__(
        self,
        message: str,
        *,
        code: ConfigErrorCode,
    ) -> None:
        super().__init__(message)
        self.code: ConfigErrorCode = code
