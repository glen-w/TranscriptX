"""Deprecated shim — import from ``transcriptx.export`` instead."""

from __future__ import annotations

from transcriptx.export.markdown_html import summary_markdown_to_html  # noqa: F401

__all__ = ["summary_markdown_to_html"]
