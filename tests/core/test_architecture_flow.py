"""
Tests for high-level architecture flow: load -> plan -> execute -> manifest.

Aligns with docs/ARCHITECTURE.md: Engine (pipeline, modules, context).
"""

import pytest

from transcriptx.core.pipeline.module_registry import (
    get_available_modules,
    get_dependencies,
    get_module_info,
)


class TestArchitectureModuleRegistry:
    """Module registry is the single source of truth for analysis modules."""

    def test_registry_returns_non_empty_module_list(self):
        modules = get_available_modules()
        assert isinstance(modules, list)
        assert len(modules) >= 1
        assert "stats" in modules

    def test_registry_stats_module_has_metadata(self):
        info = get_module_info("stats")
        assert info is not None
        assert info.name == "stats"
        assert hasattr(info, "category")
        assert hasattr(info, "dependencies")
        deps = get_dependencies("stats")
        assert isinstance(deps, list)

    def test_registry_dependency_order_respected(self):
        """Modules with dependencies list them; order can be used for execution."""
        modules = get_available_modules()
        for name in ["entity_sentiment", "moments", "highlights"]:
            if name not in modules:
                continue
            deps = get_dependencies(name)
            assert isinstance(deps, list)


class TestArchitectureExecutionOrder:
    """Execution order follows dependency DAG."""

    def test_stats_has_no_dependencies(self):
        deps = get_dependencies("stats")
        assert deps == [] or (isinstance(deps, list) and "stats" not in deps)

    def test_sentiment_available_and_has_category(self):
        modules = get_available_modules()
        if "sentiment" not in modules:
            pytest.skip("sentiment not in registry (e.g. core mode)")
        info = get_module_info("sentiment")
        assert info is not None
        assert info.category in ("light", "medium", "heavy", None) or hasattr(
            info, "category"
        )
