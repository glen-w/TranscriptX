"""Typed exceptions for LLM provider/client failures."""

from __future__ import annotations

from transcriptx.core.errors.coded import CodedError

# Stable machine-readable error codes (provider/client).
LLM_UNAVAILABLE = "llm_unavailable"
LLM_MODEL_MISSING = "llm_model_missing"
LLM_TIMEOUT = "llm_timeout"
LLM_INVALID_RESPONSE = "llm_invalid_response"
LLM_GENERATION_ERROR = "llm_generation_error"
LLM_CONFIGURATION_ERROR = "llm_configuration_error"


class LLMError(CodedError):
    """Base class for LLM provider/client errors."""


class LLMUnavailableError(LLMError):
    def __init__(self, message: str = "LLM service is unreachable") -> None:
        super().__init__(message, error_code=LLM_UNAVAILABLE)


class LLMModelMissingError(LLMError):
    def __init__(self, message: str = "Configured LLM model is not installed") -> None:
        super().__init__(message, error_code=LLM_MODEL_MISSING)


class LLMTimeoutError(LLMError):
    def __init__(self, message: str = "LLM request timed out") -> None:
        super().__init__(message, error_code=LLM_TIMEOUT)


class LLMResponseError(LLMError):
    def __init__(self, message: str = "LLM response was malformed or empty") -> None:
        super().__init__(message, error_code=LLM_INVALID_RESPONSE)


class LLMGenerationError(LLMError):
    def __init__(self, message: str = "LLM generation failed") -> None:
        super().__init__(message, error_code=LLM_GENERATION_ERROR)


class LLMConfigurationError(LLMError):
    def __init__(self, message: str = "LLM configuration is invalid") -> None:
        super().__init__(message, error_code=LLM_CONFIGURATION_ERROR)


class _RetryableTransient(Exception):
    """Internal marker: transient network failure eligible for retry."""

    def __init__(self, cause: Exception, *, http_status: int | None = None) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.http_status = http_status
