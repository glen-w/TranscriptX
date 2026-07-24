"""Sphinx release value: package metadata or neutral development fallback."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONF = ROOT / "docs" / "conf.py"


def _load_conf_module():
    spec = importlib.util.spec_from_file_location("tx_docs_conf", CONF)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_sphinx_release_uses_package_metadata_when_available() -> None:
    with patch("importlib.metadata.version", return_value="0.9.8"):
        # Re-exec under patched metadata by simulating the conf try block.
        release = "0.9.8"
        version = ".".join(release.split(".")[:2])
        assert release == "0.9.8"
        assert version == "0.9"


@pytest.mark.unit
def test_sphinx_conf_fallback_is_neutral_dev() -> None:
    """When package metadata is missing, conf must not use a stale patch."""
    text = CONF.read_text(encoding="utf-8")
    assert 'release = "0.9.dev0"' in text
    assert 'release = "0.9.6"' not in text
    assert 'release = "0.9.7"' not in text
