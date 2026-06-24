"""Block catalog registry."""

from __future__ import annotations

from transcriptx.web.blocks.specs import BlockSpec

_REGISTRY: dict[str, BlockSpec] = {}


class DuplicateBlockError(ValueError):
    pass


def register_block(spec: BlockSpec) -> None:
    if spec.id in _REGISTRY:
        raise DuplicateBlockError(f"Block already registered: {spec.id}")
    if spec.render is None:
        raise ValueError(f"Block {spec.id} must define render")
    _REGISTRY[spec.id] = spec


def get_block(block_id: str) -> BlockSpec | None:
    return _REGISTRY.get(block_id)


def list_blocks() -> list[BlockSpec]:
    return list(_REGISTRY.values())


def list_blocks_by_group() -> dict[str, list[BlockSpec]]:
    grouped: dict[str, list[BlockSpec]] = {}
    for spec in sorted(_REGISTRY.values(), key=lambda s: (s.group, s.id)):
        grouped.setdefault(spec.group, []).append(spec)
    return grouped


def validate_block_id(block_id: str) -> None:
    if block_id not in _REGISTRY:
        raise ValueError(f"Unknown block_id: {block_id}")


def clear_registry_for_tests() -> None:
    _REGISTRY.clear()
    from transcriptx.web.blocks import builtin as builtin_mod

    builtin_mod._BUILTIN_REGISTERED = False
