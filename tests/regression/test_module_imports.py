"""
Regression tests: key modules import without side effects.

Uses tests/regression/conftest.py so autouse fixtures (questionary, logging)
do not run and affect import order. Tests here avoid pulling in pipeline/database
chains that can cause circular imports when run under the root conftest.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "transcriptx.cli.workflow_modules",
        "transcriptx.cli.deduplication_workflow",
        "transcriptx.core.utils.paths",
        "transcriptx.core.utils.config.workflow",
    ],
)
def test_module_imports_without_side_effects(module_name: str) -> None:
    """Smoke test: import key modules without triggering circular imports or failures."""
    importlib.import_module(module_name)
