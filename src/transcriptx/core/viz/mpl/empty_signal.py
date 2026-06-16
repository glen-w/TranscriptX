"""No-signal probe registry for matplotlib renderers."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from transcriptx.core.viz.mpl.contracts import (
    TYPE_TO_INTENTS,
    RenderContractError,
    require_renderable_type,
)
from transcriptx.core.viz.specs import ChartSpec

SignalProbe = Callable[[ChartSpec], bool]

_PROBES: dict[type, SignalProbe] = {}


def register_probe(spec_type: type) -> Callable[[SignalProbe], SignalProbe]:
    """Register a no-signal probe for one concrete spec type."""
    if spec_type is ChartSpec:
        raise RenderContractError(
            "Cannot register probe for bare ChartSpec; use a concrete subclass."
        )
    if spec_type not in TYPE_TO_INTENTS:
        raise RenderContractError(
            f"{spec_type.__name__} is not in TYPE_TO_INTENTS; add it there first."
        )

    def decorator(fn: SignalProbe) -> SignalProbe:
        if spec_type in _PROBES:
            raise RenderContractError(
                f"Duplicate probe registration for {spec_type.__name__}."
            )
        _PROBES[spec_type] = fn
        return fn

    return decorator


def get_probe_registry() -> dict[type, SignalProbe]:
    """Return a copy of registered no-signal probes."""
    return dict(_PROBES)


def probe_for_spec(spec: ChartSpec) -> SignalProbe:
    """Return probe for this concrete spec, enforcing render contracts."""
    spec_type = require_renderable_type(spec)
    probe = _PROBES.get(spec_type)
    if probe is None:
        raise RenderContractError(
            f"No no-signal probe registered for {spec_type.__name__}."
        )
    return probe


def coerce_floats(values: Iterable[object] | None) -> list[float]:
    """Best-effort float conversion; invalid values are dropped."""
    out: list[float] = []
    if values is None:
        return out
    for value in values:
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            continue
    return out


def any_nonzero(values: Iterable[float]) -> bool:
    """True when at least one numeric value is non-zero."""
    return any(float(v) != 0.0 for v in values)
