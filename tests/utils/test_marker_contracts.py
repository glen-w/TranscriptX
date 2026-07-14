"""Tests for marker contracts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _collect_nodeids(*args: str) -> set[str]:
    cmd = [
        "pytest",
        "--override-ini",
        "addopts=",
        "--collect-only",
        "-q",
        *args,
    ]
    proc = subprocess.run(
        cmd,
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        check=True,
    )
    nodeids: set[str] = set()
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("tests/") and "::" in line:
            nodeids.add(line)
    return nodeids


@pytest.mark.unit
def test_smoke_folder_collects_under_smoke_marker_expression() -> None:
    all_items = _collect_nodeids("tests/smoke")
    smoke_items = _collect_nodeids("-m", "smoke", "tests/smoke")
    assert all_items
    assert smoke_items == all_items


@pytest.mark.unit
def test_integration_core_folder_collects_under_integration_markers() -> None:
    all_items = _collect_nodeids("tests/integration/core")
    integration_items = _collect_nodeids(
        "-m",
        "integration_core or integration",
        "tests/integration/core",
    )
    assert all_items
    assert integration_items == all_items


@pytest.mark.unit
def test_optional_capability_markers_collect_for_touched_smoke_and_integration_files() -> (
    None
):
    # This keeps the contract explicit for known touched files without broad brittle scans.
    touched = [
        "tests/smoke/test_module_registry_smoke.py",
        "tests/integration/core/test_managed_import_pipeline_integration.py",
    ]
    for file_path in touched:
        items = _collect_nodeids(file_path)
        assert items, f"Expected collected items in {file_path}"
