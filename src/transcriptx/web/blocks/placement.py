"""Layout placement types for block instances on a page."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class BlockPlacement:
    """One block instance in a layout (placement_id is unique within the page)."""

    placement_id: str
    block_id: str
    title_override: str | None = None
    visible: bool = True
    params: Mapping[str, Any] = field(default_factory=dict)
    section: str | None = None
