"""
Smoke test for module registry availability.
"""

from transcriptx.core.pipeline.module_registry import get_available_modules


def test_module_registry_returns_expected_modules() -> None:
    modules = get_available_modules()
    assert isinstance(modules, list)
    assert len(modules) > 0
    assert "sentiment" in modules or "stats" in modules
