"""
Smoke test for capabilities snapshot shape and determinism.
"""

from __future__ import annotations

import json

import pytest

from tests.capabilities import get_capabilities_snapshot


@pytest.mark.smoke
def test_capabilities_snapshot_shape() -> None:
    snapshot = get_capabilities_snapshot()

    assert "runtime" in snapshot
    assert "packages" in snapshot
    assert "environment" in snapshot

    runtime = snapshot["runtime"]
    assert isinstance(runtime, dict)
    assert set(runtime.keys()) == {"has_models", "has_docker", "has_ffmpeg"}
    assert all(isinstance(v, bool) for v in runtime.values())

    packages = snapshot["packages"]
    assert isinstance(packages, dict)
    assert packages
    assert all(isinstance(k, str) for k in packages.keys())
    assert all(isinstance(v, bool) for v in packages.values())

    environment = snapshot["environment"]
    assert isinstance(environment, dict)
    assert "TRANSCRIPTX_TEST_MODELS" in environment
    assert "TRANSCRIPTX_DISABLE_DOWNLOADS" in environment

    json.dumps(snapshot)


@pytest.mark.smoke
def test_capabilities_snapshot_deterministic() -> None:
    snapshot1 = get_capabilities_snapshot()
    snapshot2 = get_capabilities_snapshot()

    assert snapshot1 == snapshot2
