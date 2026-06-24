"""Typed exceptions for LLM analysis module input/pipeline failures."""

from __future__ import annotations

from transcriptx.core.errors.coded import CodedError

LLM_DEPENDENCY_MISSING = "llm_dependency_missing"
LLM_EMPTY_INPUT = "llm_empty_input"


class ModuleDependencyMissingError(CodedError):
    def __init__(
        self,
        message: str = "Required module dependency is missing",
        *,
        dependency: str | None = None,
        state: str | None = None,
    ) -> None:
        error_context = None
        if dependency is not None and state is not None:
            error_context = {"dependency": dependency, "state": state}
        super().__init__(
            message,
            error_code=LLM_DEPENDENCY_MISSING,
            error_context=error_context,
        )


class ModuleEmptyInputError(CodedError):
    def __init__(self, message: str = "No usable input for LLM module") -> None:
        super().__init__(message, error_code=LLM_EMPTY_INPUT)
