"""Subprocess-isolated BERTopic fit helpers (outside analysis/ for audit rules)."""

from transcriptx.core.utils.bertopic_fit.isolated import (
    IsolatedFitResult,
    fit_bertopic_isolated,
)

__all__ = ["IsolatedFitResult", "fit_bertopic_isolated"]
