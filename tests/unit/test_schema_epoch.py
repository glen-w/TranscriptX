"""Unit tests for schema_epoch marker and data-root assessment."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.utils.schema_epoch import (
    CURRENT_SCHEMA_EPOCH,
    MARKER_FILENAME,
    DataRootStatus,
    SchemaEpochError,
    assess_data_root,
    ensure_epoch_marker,
    read_epoch,
    require_compatible_data_root,
    write_epoch,
)


def test_write_and_read_epoch(tmp_path: Path) -> None:
    root = tmp_path / "data"
    path = write_epoch(root)
    assert path.name == MARKER_FILENAME
    assert read_epoch(root) == CURRENT_SCHEMA_EPOCH
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_epoch"] == CURRENT_SCHEMA_EPOCH
    assert payload["kind"] == "transcriptx.schema_epoch"


def test_assess_empty_missing_root(tmp_path: Path) -> None:
    root = tmp_path / "missing"
    result = assess_data_root(root)
    assert result.status == DataRootStatus.EMPTY
    assert result.ok


def test_assess_empty_directory(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    result = assess_data_root(root)
    assert result.status == DataRootStatus.EMPTY


def test_assess_compatible(tmp_path: Path) -> None:
    root = tmp_path / "data"
    write_epoch(root)
    (root / "transcripts").mkdir()
    result = assess_data_root(root)
    assert result.status == DataRootStatus.COMPATIBLE
    assert result.epoch == CURRENT_SCHEMA_EPOCH
    assert result.ok


def test_assess_missing_marker_occupied(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    (root / "outputs").mkdir()
    result = assess_data_root(root)
    assert result.status == DataRootStatus.MISSING_MARKER
    assert not result.ok
    assert str(root) in result.detail


def test_assess_pre_epoch(tmp_path: Path) -> None:
    root = tmp_path / "data"
    write_epoch(root, epoch=0)
    result = assess_data_root(root)
    assert result.status == DataRootStatus.PRE_EPOCH
    assert result.epoch == 0
    assert not result.ok


def test_assess_foreign_future_epoch(tmp_path: Path) -> None:
    root = tmp_path / "data"
    write_epoch(root, epoch=CURRENT_SCHEMA_EPOCH + 1)
    result = assess_data_root(root)
    assert result.status == DataRootStatus.FOREIGN
    assert not result.ok


def test_ensure_epoch_initializes_empty(tmp_path: Path) -> None:
    root = tmp_path / "data"
    result = ensure_epoch_marker(root)
    assert result.status == DataRootStatus.COMPATIBLE
    assert read_epoch(root) == CURRENT_SCHEMA_EPOCH


def test_ensure_epoch_does_not_overwrite_occupied(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    (root / "outputs").mkdir()
    result = ensure_epoch_marker(root)
    assert result.status == DataRootStatus.MISSING_MARKER
    assert not (root / MARKER_FILENAME).exists()


def test_require_compatible_raises(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    (root / "outputs").mkdir()
    with pytest.raises(SchemaEpochError) as exc_info:
        require_compatible_data_root(root)
    assert exc_info.value.assessment.status == DataRootStatus.MISSING_MARKER


def test_require_compatible_ok_on_empty(tmp_path: Path) -> None:
    root = tmp_path / "data"
    result = require_compatible_data_root(root)
    assert result.status == DataRootStatus.COMPATIBLE
