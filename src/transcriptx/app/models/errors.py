"""Domain-specific error types for the application layer."""

from __future__ import annotations


class AppError(Exception):
    """Base exception for application layer errors."""

    pass


class ValidationError(AppError):
    """Invalid input or parameters."""

    pass


class DependencyError(AppError):
    """Missing or incompatible dependency (e.g. model, library)."""

    pass


class PathConfigError(AppError):
    """Invalid path or configuration."""

    pass


class WorkflowExecutionError(AppError):
    """Workflow execution failed."""

    pass


class ModuleExecutionError(AppError):
    """A specific analysis module failed."""

    pass


class ArtifactReadError(AppError):
    """Failed to read or parse an artifact."""

    pass
