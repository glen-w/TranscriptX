"""Import smoke tests to detect side effects early.

Heavy import tests (multiple modules) live in tests/regression/test_module_imports.py
so they run under regression/conftest.py and avoid autouse fixtures that affect
import order. This file keeps a single lightweight check when run under root conftest.
"""

from __future__ import annotations

import importlib


def test_core_processing_state_imports_under_root_conftest() -> None:
    """core.utils.processing_state can be imported (lightweight; no pipeline/database)."""
    importlib.import_module("transcriptx.core.utils.processing_state")
