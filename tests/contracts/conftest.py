from __future__ import annotations

import warnings

import pytest

pytestmark = pytest.mark.filterwarnings(r"ignore:\[W095\].*:UserWarning")


def pytest_configure() -> None:
    # Ensure spaCy version warnings are silenced during contract collection.
    warnings.filterwarnings("ignore", message=r"\[W095\].*", category=UserWarning)
