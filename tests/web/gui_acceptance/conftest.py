"""Fixtures for Streamlit AppTest GUI acceptance."""

from __future__ import annotations

import pytest

from tests.web.gui_acceptance.harness import GuiWorkspace, isolate_workspace

pytestmark = [
    pytest.mark.gui_acceptance,
    pytest.mark.heavy,
]


@pytest.fixture
def gui_ws(monkeypatch: pytest.MonkeyPatch, tmp_path) -> GuiWorkspace:
    """Isolated PATHS + import/group roots for one journey."""
    return isolate_workspace(monkeypatch, tmp_path)
