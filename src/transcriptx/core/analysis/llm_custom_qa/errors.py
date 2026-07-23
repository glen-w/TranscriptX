"""Typed failure codes and exceptions for llm_custom_qa."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from transcriptx.core.errors.coded import CodedError


class CustomQAFailureCode(str, Enum):
    """Complete top-level failure-code enum (module / readiness / config)."""

    CUSTOM_QA_QUESTIONS_INVALID = "CUSTOM_QA_QUESTIONS_INVALID"
    CUSTOM_QA_EMPTY_INPUT = "CUSTOM_QA_EMPTY_INPUT"
    CUSTOM_QA_MODEL_RESPONSE_INVALID = "CUSTOM_QA_MODEL_RESPONSE_INVALID"
    CUSTOM_QA_PROVIDER_UNAVAILABLE = "CUSTOM_QA_PROVIDER_UNAVAILABLE"
    CUSTOM_QA_MODEL_MISSING = "CUSTOM_QA_MODEL_MISSING"
    CUSTOM_QA_TIMEOUT = "CUSTOM_QA_TIMEOUT"
    CUSTOM_QA_CANCELLED = "CUSTOM_QA_CANCELLED"
    CUSTOM_QA_CLIENT_ERROR = "CUSTOM_QA_CLIENT_ERROR"
    CUSTOM_QA_RETRY_EXHAUSTED = "CUSTOM_QA_RETRY_EXHAUSTED"
    CUSTOM_QA_ARTIFACT_VALIDATION_FAILED = "CUSTOM_QA_ARTIFACT_VALIDATION_FAILED"
    CUSTOM_QA_ARTIFACT_COMMIT_FAILED = "CUSTOM_QA_ARTIFACT_COMMIT_FAILED"
    CUSTOM_QA_CACHE_INVALID = "CUSTOM_QA_CACHE_INVALID"
    CONFIG_LOCK_TIMEOUT = "CONFIG_LOCK_TIMEOUT"
    CONFIG_CORRUPT = "CONFIG_CORRUPT"
    CUSTOM_QA_INTERNAL = "CUSTOM_QA_INTERNAL"


class CustomQAError(CodedError):
    """Base coded error for llm_custom_qa."""

    def __init__(
        self,
        message: str,
        *,
        code: CustomQAFailureCode,
        error_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            error_code=code.value,
            error_context=error_context,
        )
        self.code = code


class CustomQAQuestionsValidationError(CustomQAError):
    """Resolver/normaliser validation failure."""

    def __init__(
        self,
        message: str,
        *,
        error_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code=CustomQAFailureCode.CUSTOM_QA_QUESTIONS_INVALID,
            error_context=error_context,
        )


class CustomQAEmptyInputError(CustomQAError):
    def __init__(
        self,
        message: str = "No usable transcript segment text for custom questions",
        *,
        error_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code=CustomQAFailureCode.CUSTOM_QA_EMPTY_INPUT,
            error_context=error_context,
        )


class CustomQAModelResponseInvalidError(CustomQAError):
    def __init__(
        self,
        message: str,
        *,
        error_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code=CustomQAFailureCode.CUSTOM_QA_MODEL_RESPONSE_INVALID,
            error_context=error_context,
        )


class CustomQAArtifactValidationError(CustomQAError):
    def __init__(
        self,
        message: str,
        *,
        error_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code=CustomQAFailureCode.CUSTOM_QA_ARTIFACT_VALIDATION_FAILED,
            error_context=error_context,
        )


class CustomQAArtifactCommitError(CustomQAError):
    def __init__(
        self,
        message: str,
        *,
        error_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code=CustomQAFailureCode.CUSTOM_QA_ARTIFACT_COMMIT_FAILED,
            error_context=error_context,
        )


class CustomQAConfigLockTimeoutError(CustomQAError):
    def __init__(
        self,
        message: str = "Could not acquire project config lock",
        *,
        error_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code=CustomQAFailureCode.CONFIG_LOCK_TIMEOUT,
            error_context=error_context,
        )


class CustomQAConfigCorruptError(CustomQAError):
    def __init__(
        self,
        message: str = "Project config unreadable or invalid",
        *,
        error_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code=CustomQAFailureCode.CONFIG_CORRUPT,
            error_context=error_context,
        )


def map_exception_to_failure_code(exc: BaseException) -> CustomQAFailureCode:
    """Map an exception to exactly one top-level failure code."""
    if isinstance(exc, CustomQAError):
        return exc.code
    # Map shared persistence codes without importing analysis from config.
    from transcriptx.core.config.persistence import (
        ConfigCorruptError,
        ConfigLockTimeoutError,
    )

    if isinstance(exc, ConfigLockTimeoutError):
        return CustomQAFailureCode.CONFIG_LOCK_TIMEOUT
    if isinstance(exc, ConfigCorruptError):
        return CustomQAFailureCode.CONFIG_CORRUPT
    if isinstance(exc, CodedError):
        try:
            return CustomQAFailureCode(exc.error_code)
        except ValueError:
            pass
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "cancel" in name or "cancel" in msg:
        return CustomQAFailureCode.CUSTOM_QA_CANCELLED
    if "timeout" in name or "timed out" in msg:
        return CustomQAFailureCode.CUSTOM_QA_TIMEOUT
    if "auth" in msg or "unauthorized" in msg:
        return CustomQAFailureCode.CUSTOM_QA_CLIENT_ERROR
    if "model" in msg and ("missing" in msg or "not found" in msg):
        return CustomQAFailureCode.CUSTOM_QA_MODEL_MISSING
    if "provider" in msg or "connection" in msg or "unreachable" in msg:
        return CustomQAFailureCode.CUSTOM_QA_PROVIDER_UNAVAILABLE
    return CustomQAFailureCode.CUSTOM_QA_INTERNAL
