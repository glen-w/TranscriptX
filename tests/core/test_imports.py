"""Import smoke tests to detect side effects early.

Heavy import tests (multiple modules) live in tests/regression/test_module_imports.py
so they run under regression/conftest.py and avoid autouse fixtures that affect
import order. This file keeps a single lightweight check when run under root conftest.
"""

from __future__ import annotations

import importlib


def test_workflow_modules_imports_under_root_conftest() -> None:
    """CLI workflow_modules can be imported (lightweight; no pipeline/database)."""
    importlib.import_module("transcriptx.cli.workflow_modules")
