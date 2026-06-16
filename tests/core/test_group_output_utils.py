"""Group module output directory helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.utils.group_output_utils import (
    get_group_module_dir,
    write_group_module_csv,
    write_group_module_json,
)


@pytest.mark.unit
def test_get_group_module_dir_creates_layout(tmp_path: Path) -> None:
    d = get_group_module_dir(tmp_path, "stats")
    assert d.is_dir()
    assert (d / "combined").is_dir()
    assert (d / "by_session").is_dir()
    assert (d / "by_speaker").is_dir()


@pytest.mark.unit
def test_write_group_module_json_round_trip(tmp_path: Path) -> None:
    base = get_group_module_dir(tmp_path, "m1")
    jp = write_group_module_json(base, "out", {"a": 1})
    data = json.loads(Path(jp).read_text(encoding="utf-8"))
    assert data == {"a": 1}


@pytest.mark.unit
def test_write_group_module_csv_writes_rows(tmp_path: Path) -> None:
    base = get_group_module_dir(tmp_path, "m1")
    cp = write_group_module_csv(base, "by_session", "rows", [["col"], ["v1"], ["v2"]])
    text = Path(cp).read_text(encoding="utf-8")
    assert "col" in text and "v1" in text
