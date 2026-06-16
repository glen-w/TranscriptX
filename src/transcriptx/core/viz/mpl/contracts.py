"""Contracts and shared policy for matplotlib chart rendering.

Bar-mode contract
-----------------
`BarCategoricalSpec` has three intentional shapes that both the renderer and the
signal probe must branch on consistently:

1) flat mode: `series is None` and `categories`/`values` are used.
2) grouped-populated mode: `series` is non-empty.
3) grouped-empty mode: `series == []` means grouped data was attempted but no
   groups were produced.

The grouped-empty case is valid-but-no-signal (overlay), not structural invalidity.
Do not collapse grouped-empty into flat mode during refactors.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import numpy as np

from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    BoxSpec,
    ChartSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
    NetworkGraphSpec,
    ScatterSpec,
)

if TYPE_CHECKING:
    from transcriptx.core.viz.mpl.empty_signal import SignalProbe


class RenderContractError(ValueError):
    """Raised when a chart violates renderer-layer contracts."""


NO_SIGNAL_MESSAGE = "None detected in this transcript."

# All registries use loose `dict[type, ...]` to avoid type[...] invariance
# friction. Runtime gatekeepers enforce the actual allowed shapes.
TYPE_TO_INTENTS: dict[type, frozenset[str]] = {
    LineTimeSeriesSpec: frozenset({"line_timeseries"}),
    ScatterSpec: frozenset({"scatter", "scatter_events"}),
    HeatmapMatrixSpec: frozenset({"heatmap_matrix"}),
    BarCategoricalSpec: frozenset({"bar_categorical"}),
    BoxSpec: frozenset({"box_plot"}),
    NetworkGraphSpec: frozenset({"network_graph"}),
}


def require_renderable_type(spec: ChartSpec) -> type:
    """Return the concrete renderable type or raise RenderContractError."""
    spec_type = type(spec)
    allowed = TYPE_TO_INTENTS.get(spec_type)
    if allowed is None:
        raise RenderContractError(
            f"{spec_type.__name__} is not a renderable chart spec. "
            "Bare ChartSpec and unregistered subclasses do not render."
        )
    if spec.chart_intent not in allowed:
        raise RenderContractError(
            f"{spec_type.__name__} requires chart_intent in {sorted(allowed)}, "
            f"got {spec.chart_intent!r}. Type and intent must agree."
        )
    return spec_type


def seeded_rng_for(spec: ChartSpec) -> np.random.Generator:
    """Return deterministic RNG keyed by spec identity."""
    seed_source = (
        spec.viz_id or f"{spec.module}/{spec.name}/{spec.scope}/{spec.speaker or ''}"
    )
    digest = hashlib.blake2b(seed_source.encode("utf-8"), digest_size=8).digest()
    seed = int.from_bytes(digest, byteorder="big", signed=False)
    return np.random.default_rng(seed)


def resolve_no_signal_message(spec: ChartSpec) -> str | None:
    """Return standardized no-signal overlay message for a spec.

    `spec.notes` is metadata only and is never rendered on axes by this renderer.
    """
    from transcriptx.core.viz.mpl.empty_signal import probe_for_spec

    probe: SignalProbe = probe_for_spec(spec)
    if probe(spec):
        return None
    return NO_SIGNAL_MESSAGE
