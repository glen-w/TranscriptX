"""
Regression tests: key modules import without side effects.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "transcriptx.core.utils.paths",
        "transcriptx.core.utils.config.workflow",
        "transcriptx.core.utils.processing_state",
        "transcriptx.core.utils.file_discovery",
        "transcriptx.core.audio.utils",
        "transcriptx.core.audio.fingerprinting",
        "transcriptx.web.__main__",
    ],
)
def test_module_imports_without_side_effects(module_name: str) -> None:
    """Smoke test: import key modules without triggering circular imports or failures."""
    importlib.import_module(module_name)
