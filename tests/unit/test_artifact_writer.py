"""Unit tests for atomic artifact_writer helpers."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.utils.artifact_writer import (
    write_bytes,
    write_csv,
    write_json,
    write_jsonl,
    write_text,
)


@pytest.mark.unit
def test_write_bytes_creates_parent_and_file(tmp_path) -> None:
    target = tmp_path / "nested" / "blob.bin"
    out = write_bytes(target, b"abc")
    assert out == target
    assert target.read_bytes() == b"abc"


@pytest.mark.unit
def test_write_text_roundtrip(tmp_path) -> None:
    target = tmp_path / "note.txt"
    write_text(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"


@pytest.mark.unit
def test_write_json_pretty_and_default_str(tmp_path) -> None:
    target = tmp_path / "meta.json"
    write_json(target, {"n": 1, "p": tmp_path})
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["n"] == 1
    assert loaded["p"] == str(tmp_path)


@pytest.mark.unit
def test_write_jsonl_empty_and_rows(tmp_path) -> None:
    empty = tmp_path / "empty.jsonl"
    write_jsonl(empty, [])
    assert empty.read_text(encoding="utf-8") == ""

    rows_path = tmp_path / "rows.jsonl"
    write_jsonl(rows_path, [{"a": 1}, {"b": 2}])
    lines = rows_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [{"a": 1}, {"b": 2}]


@pytest.mark.unit
def test_write_csv_with_header(tmp_path) -> None:
    target = tmp_path / "out.csv"
    write_csv(target, rows=[["x", 1], ["y", 2]], header=["name", "n"])
    text = target.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "name,n"
    assert "x,1" in text
    assert "y,2" in text


@pytest.mark.unit
def test_write_csv_overwrites_existing(tmp_path) -> None:
    target = tmp_path / "out.csv"
    target.write_text("stale\n", encoding="utf-8")
    write_csv(target, rows=[["ok"]], header=["col"])
    assert target.read_text(encoding="utf-8").startswith("col")
    assert "stale" not in target.read_text(encoding="utf-8")
