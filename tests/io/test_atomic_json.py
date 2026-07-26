"""Unit tests for crash-safe atomic JSON / bytes persistence."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from transcriptx.io.atomic_json import (
    strict_json_dumps,
    write_bytes_atomic,
    write_bytes_atomic_locked,
    write_json_atomic,
    write_json_atomic_locked,
)


@pytest.mark.unit
class TestStrictJsonDumps:
    def test_roundtrip_object_with_trailing_newline(self):
        text = strict_json_dumps({"a": 1, "b": [True, None]})
        assert text.endswith("\n")
        assert json.loads(text) == {"a": 1, "b": [True, None]}

    def test_compact_when_indent_none(self):
        text = strict_json_dumps({"x": 1}, indent=None)
        assert "\n  " not in text
        assert text.endswith("\n")
        assert json.loads(text) == {"x": 1}

    def test_rejects_nan(self):
        with pytest.raises(ValueError, match="non-finite float"):
            strict_json_dumps({"v": math.nan})

    def test_rejects_inf(self):
        with pytest.raises(ValueError, match="non-finite float"):
            strict_json_dumps({"v": math.inf})

    def test_rejects_non_string_keys(self):
        with pytest.raises(TypeError, match="keys must be strings"):
            strict_json_dumps({1: "x"})

    def test_rejects_unsupported_types(self):
        with pytest.raises(TypeError, match="unsupported JSON type"):
            strict_json_dumps({"v": object()})


@pytest.mark.unit
class TestWriteAtomic:
    def test_write_json_atomic_creates_parent_and_file(self, tmp_path: Path):
        target = tmp_path / "nested" / "out.json"
        write_json_atomic(target, {"ok": True})
        assert target.is_file()
        assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}
        assert target.read_text(encoding="utf-8").endswith("\n")

    def test_write_bytes_atomic_replaces_existing(self, tmp_path: Path):
        target = tmp_path / "blob.bin"
        write_bytes_atomic(target, b"first")
        write_bytes_atomic(target, b"second")
        assert target.read_bytes() == b"second"

    def test_write_json_atomic_locked_roundtrip(self, tmp_path: Path):
        target = tmp_path / "locked.json"
        write_json_atomic_locked(target, {"n": 2}, indent=None)
        assert json.loads(target.read_text(encoding="utf-8")) == {"n": 2}

    def test_write_bytes_atomic_locked_roundtrip(self, tmp_path: Path):
        target = tmp_path / "locked.bin"
        write_bytes_atomic_locked(target, b"abc")
        assert target.read_bytes() == b"abc"

    def test_write_json_atomic_rejects_nan_before_write(self, tmp_path: Path):
        target = tmp_path / "bad.json"
        with pytest.raises(ValueError, match="non-finite float"):
            write_json_atomic(target, {"v": float("nan")})
        assert not target.exists()
