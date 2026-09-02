"""Tests for shared path-safety helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.utils.path_safety import (
    assert_path_under_root,
    assert_safe_path_segment,
    assert_safe_relpath,
)


def test_assert_safe_relpath_accepts_nested_relative() -> None:
    assert (
        assert_safe_relpath("voice/privacy.voice_settings.json")
        == "voice/privacy.voice_settings.json"
    )


def test_assert_safe_relpath_rejects_absolute_and_traversal() -> None:
    with pytest.raises(ValueError):
        assert_safe_relpath("/etc/passwd")
    with pytest.raises(ValueError):
        assert_safe_relpath("../escape")
    with pytest.raises(ValueError):
        assert_safe_relpath("voice/../../etc/passwd")
    with pytest.raises(ValueError):
        assert_safe_relpath("C:/windows/system32")
    with pytest.raises(ValueError):
        assert_safe_relpath("x\x00y")


def test_assert_safe_path_segment_rejects_separators() -> None:
    assert assert_safe_path_segment("team") == "team"
    with pytest.raises(ValueError):
        assert_safe_path_segment("foo/bar")
    with pytest.raises(ValueError):
        assert_safe_path_segment("../x")
    with pytest.raises(ValueError):
        assert_safe_path_segment("")


def test_assert_path_under_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    inside = root / "a.json"
    inside.write_text("{}", encoding="utf-8")
    assert assert_path_under_root(inside, root) == inside.resolve()
    with pytest.raises(ValueError):
        assert_path_under_root(tmp_path / "outside.json", root)
