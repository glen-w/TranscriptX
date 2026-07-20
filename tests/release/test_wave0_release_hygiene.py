"""Unit tests for Wave 0 release hygiene helpers (denylist + tracked-data allowlist)."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "scripts" / "release"


def _load(name: str):
    path = RELEASE / name
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.unit
def test_tracked_data_allowlist_matches_git_ls_files() -> None:
    mod = _load("check_tracked_data.py")
    assert mod.main() == 0


@pytest.mark.unit
def test_denylist_passes_on_current_repo() -> None:
    mod = _load("check_denylist.py")
    assert mod.main() == 0


@pytest.mark.unit
def test_denylist_detects_forbidden_tracked_path(tmp_path: Path, monkeypatch) -> None:
    mod = _load("check_denylist.py")
    banned = "whisperx.env"

    def fake_tracked() -> list[str]:
        return [banned, "README.md"]

    monkeypatch.setattr(mod, "_tracked_files", fake_tracked)
    monkeypatch.setattr(mod, "_check_untracked_forbidden", lambda _g: [])
    monkeypatch.setattr(mod, "_check_ignored_forbidden", lambda _g: [])
    monkeypatch.setattr(mod, "_check_secrets", lambda _p: [])
    assert mod.main() == 1


@pytest.mark.unit
def test_stale_refs_script_exits_zero() -> None:
    proc = subprocess.run(
        ["bash", str(RELEASE / "stale_refs.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "stale-ref sweep passed" in proc.stdout
