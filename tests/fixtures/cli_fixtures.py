"""
Fixtures for app-layer workflow testing.

Replaces the former Typer CLI fixtures. The app layer accepts explicit
request objects; there is no interactive CLI to invoke.
"""

from __future__ import annotations

from typing import Dict
from unittest.mock import MagicMock

import pytest


def create_mock_workflow_result(
    success: bool = True, output_dir: str = "/tmp/test_output"
) -> dict:
    if success:
        return {"status": "success", "output_dir": output_dir, "errors": []}
    return {"status": "error", "output_dir": None, "errors": ["Test error"]}


@pytest.fixture
def typer_test_client():
    """Stub: returns a no-op runner (CLI removed)."""
    return MagicMock()


@pytest.fixture
def non_interactive_env() -> Dict[str, str]:
    """Environment with non-interactive mode enabled."""
    return {"TRANSCRIPTX_NON_INTERACTIVE": "1"}
