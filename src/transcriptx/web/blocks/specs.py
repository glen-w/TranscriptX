"""Block specification types for the composition platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping

from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.placement import BlockPlacement

BlockRenderFn = Callable[[BlockContext, BlockPlacement], None]


class BlockPrereq(str, Enum):
    """Minimum context required before a block can render meaningfully."""

    NONE = "none"
    RUN_SCOPED = "run_scoped"


@dataclass(frozen=True)
class BlockSpec:
    """Reusable view block type registered in the block catalog."""

    id: str
    title: str
    group: str
    description: str
    module_deps: tuple[str, ...] = ()
    artifact_patterns: tuple[str, ...] = ()
    artifact_kinds: tuple[str, ...] = ()
    prerequisites: BlockPrereq = BlockPrereq.RUN_SCOPED
    params_schema: Mapping[str, Any] = field(default_factory=dict)
    render: BlockRenderFn | None = None
    fragment: bool = False
    supports_instance_id: bool = False
