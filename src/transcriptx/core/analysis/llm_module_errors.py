"""Typed exceptions for LLM analysis module input/pipeline failures."""

from __future__ import annotations

from transcriptx.core.errors.coded import CodedError

LLM_DEPENDENCY_MISSING = "llm_dependency_missing"
LLM_EMPTY_INPUT = "llm_empty_input"


class ModuleDependencyMissingError(CodedError):
    def __init__(self, message: str = "Required module dependency is missing") -> None:
        super().__init__(message, error_code=LLM_DEPENDENCY_MISSING)


class ModuleEmptyInputError(CodedError):
    def __init__(self, message: str = "No usable input for LLM module") -> None:
        super().__init__(message, error_code=LLM_EMPTY_INPUT)
