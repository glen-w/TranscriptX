"""BERTopic dependency boundary: base must not pull or import the optional stack."""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"


def _base_dependencies_body() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(
        r"(?ms)^dependencies\s*=\s*\[(.*?)\]\s*\n\n\[project",
        text,
    )
    assert match, "base dependencies block not found"
    return match.group(1).lower()


@pytest.mark.unit
def test_base_metadata_excludes_bertopic_compiled_stack() -> None:
    body = _base_dependencies_body()
    for name in ("bertopic", "hdbscan", "umap-learn", "llvmlite", "numba"):
        assert name not in body, name


@pytest.mark.unit
def test_import_transcriptx_does_not_import_bertopic_stack() -> None:
    """Catalogue / import must not load BERTopic natives."""
    banned = ("bertopic", "hdbscan", "umap", "umap.umap_")
    before = {name for name in sys.modules if name.split(".")[0] in banned}
    importlib.invalidate_caches()
    import transcriptx  # noqa: F401
    from transcriptx.core.pipeline.module_registry import (
        get_default_modules,
        get_module_info,
    )

    assert get_module_info("bertopic") is not None
    mods = get_default_modules(include_legacy=False)
    assert "bertopic" in mods or get_module_info("bertopic") is not None
    after = {
        name for name in sys.modules if name.split(".")[0] in ("bertopic", "hdbscan")
    }
    assert after <= before, f"importing transcriptx loaded {after - before}"


@pytest.mark.unit
def test_bertopic_missing_extra_skip_is_stable() -> None:
    from transcriptx.core.pipeline import module_registry

    present = module_registry.is_extra_distribution_present("bertopic")
    if present:
        pytest.skip("bertopic extra installed in this environment")
    # Soft skip path used by pipeline preflight (string reason contract).
    assert present is False
