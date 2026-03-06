"""
Regression tests use pure filesystem/config scanning and must not trigger
transcriptx imports that cause circular import chains. Override root
conftest autouse fixtures with no-ops so regression tests run in isolation.
"""

import pytest

# Fixtures (cli_runner, state_recovery, path_resolution) are in root conftest via pytest_plugins.
# This conftest only overrides autouse fixtures so regression tests run without transcriptx import chains.


@pytest.fixture(autouse=True)
def mock_questionary():
    """No-op: regression tests do pure filesystem scanning, no transcriptx imports."""
    yield


@pytest.fixture(autouse=True)
def suppress_logging():
    """No-op: regression tests do not use transcriptx logger."""
    yield


@pytest.fixture(autouse=True)
def clean_environment():
    """No-op: regression tests do not depend on env cleanup."""
    yield
