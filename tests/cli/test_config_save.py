"""
Tests for config save utilities (default path, no interactive prompts).
"""

from unittest.mock import MagicMock

import pytest

from transcriptx.cli.config_editors.save import _default_save_path
from transcriptx.core.config.persistence import get_project_config_path


class TestDefaultSavePath:
    """Tests for _default_save_path (non-interactive, no quarantine)."""

    def test_uses_project_config_path_when_setting_empty(self) -> None:
        """When default_config_save_path is empty, returns project config path."""
        config = MagicMock()
        config.workflow.default_config_save_path = ""
        result = _default_save_path(config)
        assert result == str(get_project_config_path())

    def test_uses_project_config_path_when_setting_whitespace_only(self) -> None:
        """When default_config_save_path is only whitespace, returns project config path."""
        config = MagicMock()
        config.workflow.default_config_save_path = "   \n\t  "
        result = _default_save_path(config)
        assert result == str(get_project_config_path())

    def test_uses_configured_path_when_set(self) -> None:
        """When default_config_save_path is set, returns that path."""
        config = MagicMock()
        custom = "/custom/config.json"
        config.workflow.default_config_save_path = custom
        result = _default_save_path(config)
        assert result == custom

    def test_strips_configured_path(self) -> None:
        """Configured path is stripped of surrounding whitespace."""
        config = MagicMock()
        config.workflow.default_config_save_path = "  /my/config.json  "
        result = _default_save_path(config)
        assert result == "/my/config.json"
