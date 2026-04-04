"""Adapter package exports for the import_core architecture."""

from transcriptx.io.import_core.registry import ImportAdapterRegistry


def build_default_registry() -> ImportAdapterRegistry:
    from transcriptx.io.import_adapters.registry_builtins import (
        build_default_registry as _build_default_registry,
    )

    return _build_default_registry()


__all__ = ["ImportAdapterRegistry", "build_default_registry"]
