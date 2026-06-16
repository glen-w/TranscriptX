"""Matplotlib renderer dispatch registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from transcriptx.core.utils.lazy_imports import get_matplotlib_pyplot
from transcriptx.core.viz.mpl.contracts import (
    TYPE_TO_INTENTS,
    RenderContractError,
    require_renderable_type,
)
from transcriptx.core.viz.specs import ChartSpec

Renderer = Callable[[ChartSpec, Any], Any]

_RENDERERS: dict[type, Renderer] = {}


def register(spec_type: type) -> Callable[[Renderer], Renderer]:
    """Register renderer for one concrete spec type."""
    if spec_type is ChartSpec:
        raise RenderContractError(
            "Cannot register the bare ChartSpec base; only concrete subclasses render."
        )
    if spec_type not in TYPE_TO_INTENTS:
        raise RenderContractError(
            f"{spec_type.__name__} is not in TYPE_TO_INTENTS; add it there first."
        )

    def decorator(fn: Renderer) -> Renderer:
        if spec_type in _RENDERERS:
            raise RenderContractError(
                f"Duplicate renderer registration for {spec_type.__name__}."
            )
        _RENDERERS[spec_type] = fn
        return fn

    return decorator


def get_renderer_registry() -> dict[type, Renderer]:
    """Return copy of registered renderers."""
    return dict(_RENDERERS)


def render_mpl(spec: ChartSpec) -> Any:
    """Render matplotlib figure from a chart spec.

    Gatekeeping order:
      1) spec.validate() for spec-defined invariants
      2) require_renderable_type(spec) for renderer-layer contract invariants
      3) get_matplotlib_pyplot() only after both checks pass
      4) renderer dispatch by exact concrete spec type
    """
    spec.validate()
    spec_type = require_renderable_type(spec)
    plt = get_matplotlib_pyplot()
    renderer = _RENDERERS.get(spec_type)
    if renderer is None:
        raise RenderContractError(f"No renderer registered for {spec_type.__name__}.")
    return renderer(spec, plt)
