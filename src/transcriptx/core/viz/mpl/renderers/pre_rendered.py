"""Pre-rendered matplotlib figure passthrough renderer."""

from __future__ import annotations

from typing import Any

from transcriptx.core.viz.mpl.dispatch import register
from transcriptx.core.viz.mpl.empty_signal import register_probe
from transcriptx.core.viz.specs import PreRenderedFigureSpec


@register_probe(PreRenderedFigureSpec)
def pre_rendered_has_signal(spec: PreRenderedFigureSpec) -> bool:
    if spec.labels or spec.values or spec.series:
        return True
    return spec.figure is not None


@register(PreRenderedFigureSpec)
def render_pre_rendered(spec: PreRenderedFigureSpec, plt: Any) -> Any:
    del plt  # figure already drawn by the caller
    return spec.figure
