"""BERTopic collection-time isolation and catalogue detection contracts."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_registry_import_does_not_import_bertopic() -> None:
    """Catalogue/registry import must not pull bertopic or its natives."""
    banned = {
        "bertopic",
        "hdbscan",
        "umap",
        "umap.umap_",
    }
    # Clear any prior accidental imports from this process for a fair check
    # of *new* imports triggered by registry load. We still assert the registry
    # module itself does not reference them at import time.
    before = set(sys.modules)
    from transcriptx.core.pipeline import module_registry  # noqa: F401
    from transcriptx.core.pipeline import optional_extras  # noqa: F401

    after = set(sys.modules) - before
    leaked = after & banned
    assert not leaked, f"registry import leaked heavy modules: {sorted(leaked)}"


@pytest.mark.unit
def test_catalogue_uses_distribution_probe_not_import() -> None:
    from transcriptx.core.pipeline import module_registry

    with (
        patch(
            "transcriptx.core.pipeline.optional_extras.is_extra_distribution_present",
            return_value=False,
        ) as dist_probe,
        patch.object(
            module_registry,
            "is_extra_available",
            side_effect=AssertionError("no import probe"),
        ),
    ):
        assert module_registry.is_extra_distribution_present("bertopic") is False
        dist_probe.assert_called()
