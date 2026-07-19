"""Unit tests for local pytorch_model.bin → model.safetensors conversion."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.analysis.hf_safetensors import ensure_local_safetensors


@pytest.mark.unit
def test_ensure_local_safetensors_converts_bin_and_returns_root(tmp_path: Path) -> None:
    """Bin-only snapshots must be converted; callers need the local root path."""
    torch = pytest.importorskip("torch")
    pytest.importorskip("safetensors")

    root = tmp_path / "snapshot"
    root.mkdir()
    state = {"weight": torch.ones(2, 2)}
    torch.save(state, root / "pytorch_model.bin")
    assert not (root / "model.safetensors").exists()

    with patch(
        "transcriptx.core.analysis.hf_safetensors._local_snapshot_root",
        return_value=root,
    ):
        got = ensure_local_safetensors("org/bin-only-model")

    assert got == root
    assert (root / "model.safetensors").is_file()
    # Temp file must not be left behind.
    assert not (root / "model.safetensors.tmp").exists()


@pytest.mark.unit
def test_ensure_local_safetensors_noop_when_safetensors_present(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    from safetensors.torch import save_file

    root = tmp_path / "snapshot"
    root.mkdir()
    save_file({"weight": torch.ones(2, 2)}, str(root / "model.safetensors"))
    # Bin also present — must not rewrite / fail.
    torch.save({"weight": torch.zeros(2, 2)}, root / "pytorch_model.bin")
    before = (root / "model.safetensors").read_bytes()

    with patch(
        "transcriptx.core.analysis.hf_safetensors._local_snapshot_root",
        return_value=root,
    ):
        got = ensure_local_safetensors("org/already-safe")

    assert got == root
    assert (root / "model.safetensors").read_bytes() == before


@pytest.mark.unit
def test_ensure_local_safetensors_returns_none_without_snapshot() -> None:
    with patch(
        "transcriptx.core.analysis.hf_safetensors._local_snapshot_root",
        return_value=None,
    ):
        assert ensure_local_safetensors("org/missing") is None


@pytest.mark.unit
def test_ensure_local_safetensors_returns_none_without_bin(tmp_path: Path) -> None:
    root = tmp_path / "snapshot"
    root.mkdir()
    (root / "config.json").write_text("{}", encoding="utf-8")

    with patch(
        "transcriptx.core.analysis.hf_safetensors._local_snapshot_root",
        return_value=root,
    ):
        assert ensure_local_safetensors("org/config-only") is None
