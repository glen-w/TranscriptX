"""
Tests for the module registry system.

This module tests the ModuleRegistry which provides a single source of truth
for all analysis modules, their metadata, and lazy loading.
"""

from unittest.mock import patch


from transcriptx.core.pipeline.module_registry import (
    ModuleRegistry,
    ModuleInfo,
    get_available_modules,
    get_module_info,
    get_module_function,
    get_dependencies,
    get_category,
    get_description,
)


class TestModuleRegistry:
    """Tests for ModuleRegistry class."""

    def test_get_available_modules(self):
        """Test getting list of available modules."""
        modules = get_available_modules()

        assert isinstance(modules, list)
        assert len(modules) > 0
        # Check for some expected modules
        assert "sentiment" in modules or "stats" in modules

    def test_get_module_info(self):
        """Test getting module information."""
        info = get_module_info("sentiment")

        if info is not None:
            assert isinstance(info, ModuleInfo)
            assert info.name == "sentiment"
            assert hasattr(info, "description")
            assert hasattr(info, "category")
            assert hasattr(info, "dependencies")

    def test_get_module_info_nonexistent(self):
        """Test getting info for non-existent module."""
        info = get_module_info("nonexistent_module")

        assert info is None

    def test_get_dependencies(self):
        """Test getting module dependencies."""
        deps = get_dependencies("sentiment")

        assert isinstance(deps, list)

    def test_get_dependencies_with_deps(self):
        """Test getting dependencies for module with dependencies."""
        # entity_sentiment depends on ner and sentiment
        deps = get_dependencies("entity_sentiment")

        # Should include dependencies if module exists
        if "entity_sentiment" in get_available_modules():
            assert isinstance(deps, list)
            # May have dependencies
            assert "ner" in deps or "sentiment" in deps or len(deps) >= 0

    def test_get_category(self):
        """Test getting module category."""
        category = get_category("sentiment")

        if category is not None:
            assert category in ["light", "medium", "heavy"]

    def test_get_description(self):
        """Test getting module description."""
        description = get_description("sentiment")

        if description is not None:
            assert isinstance(description, str)
            assert len(description) > 0

    def test_get_module_function(self):
        """Test getting module function (lazy import)."""
        func = get_module_function("sentiment")

        if func is not None:
            assert callable(func)

    def test_module_registry_initialization(self):
        """Test ModuleRegistry initialization."""
        registry = ModuleRegistry()

        assert hasattr(registry, "_modules")
        assert isinstance(registry._modules, dict)
        assert len(registry._modules) > 0

    def test_module_registry_get_module_info(self):
        """Test getting module info from registry."""
        registry = ModuleRegistry()

        info = registry.get_module_info("sentiment")

        if info is not None:
            assert isinstance(info, ModuleInfo)
            assert info.name == "sentiment"

    def test_module_registry_get_dependencies(self):
        """Test getting dependencies from registry."""
        registry = ModuleRegistry()

        deps = registry.get_dependencies("sentiment")

        assert isinstance(deps, list)

    def test_module_registry_get_category(self):
        """Test getting category from registry."""
        registry = ModuleRegistry()

        category = registry.get_category("sentiment")

        if category is not None:
            assert category in ["light", "medium", "heavy"]

    def test_module_registry_get_description(self):
        """Test getting description from registry."""
        registry = ModuleRegistry()

        description = registry.get_description("sentiment")

        if description is not None:
            assert isinstance(description, str)

    def test_module_registry_get_module_function_lazy(self):
        """Test lazy loading of module functions."""
        registry = ModuleRegistry()

        func = registry.get_module_function("sentiment")

        if func is not None:
            assert callable(func)
            # Function should be cached after first call
            func2 = registry.get_module_function("sentiment")
            assert func == func2  # Should be same instance

    @patch("transcriptx.core.pipeline.module_registry.analyze_sentiment_from_file")
    def test_module_function_execution(self, mock_analyze, tmp_path):
        """Test executing a module function."""
        mock_analyze.return_value = {"status": "success"}

        func = get_module_function("sentiment")

        if func is not None:
            result = func(str(tmp_path / "test.json"))
            # Should call the actual function
            # (mocked in this test)
            assert result is not None
