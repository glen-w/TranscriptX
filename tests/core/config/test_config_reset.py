"""Tests for get_config/load_config and reset_config_for_tests isolation."""

import json
from pathlib import Path

import pytest

from transcriptx.core.utils.config import (
    get_config,
    load_config,
    reset_config_for_tests,
    set_config,
)


def test_load_config_then_get_config_returns_that_instance(tmp_path: Path) -> None:
    """Loading from file then get_config() returns that instance."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"output": {"base_output_dir": str(tmp_path)}}))
    reset_config_for_tests()
    try:
        loaded = load_config(str(config_file))
        current = get_config()
        assert current is loaded
    finally:
        reset_config_for_tests()


def test_reset_config_for_tests_isolates_state(tmp_path: Path) -> None:
    """reset_config_for_tests() clears global so next get_config() is fresh."""
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"output": {"base_output_dir": str(tmp_path / "out")}})
    )
    reset_config_for_tests()
    try:
        load_config(str(config_file))
        a = get_config()
        reset_config_for_tests()
        b = get_config()
        assert a is not b
    finally:
        reset_config_for_tests()
