"""Matplotlib rendering package with contract-driven dispatch."""

from transcriptx.core.viz.mpl import renderers as _renderers  # noqa: F401
from transcriptx.core.viz.mpl.dispatch import render_mpl

__all__ = ["render_mpl"]
