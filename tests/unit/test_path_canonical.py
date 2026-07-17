"""Unit tests for path_canonical.canonicalise_path (lock/cleanup identity)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from transcriptx.core.utils.path_canonical import (
    _resolve_existing_parents,
    canonicalise_path,
)


@pytest.mark.unit
class TestCanonicalisePath:
    def test_absolute_existing_path(self, tmp_path: Path) -> None:
        target = tmp_path / "outputs" / "slug" / "run1"
        target.mkdir(parents=True)
        result = canonicalise_path(target)
        assert Path(result) == Path(result).resolve()
        assert "run1" in result

    def test_relative_path_joins_cwd(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "rel").mkdir()
        result = canonicalise_path("rel")
        assert Path(result).is_absolute()
        assert Path(result).name == "rel" or result.endswith(os.sep + "rel")

    def test_missing_leaf_still_normalises_parents(self, tmp_path: Path) -> None:
        parent = tmp_path / "outputs" / "slug"
        parent.mkdir(parents=True)
        missing = parent / "missing_run"
        result = canonicalise_path(missing)
        assert Path(result).is_absolute()
        assert result.endswith("missing_run") or result.endswith("missing_run" + os.sep)
        assert "slug" in result

    def test_redundant_dots_collapse(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b"
        target.mkdir(parents=True)
        via_dot = tmp_path / "a" / "." / "b"
        assert canonicalise_path(target) == canonicalise_path(via_dot)

    def test_string_and_path_inputs_agree(self, tmp_path: Path) -> None:
        target = tmp_path / "x"
        target.mkdir()
        assert canonicalise_path(target) == canonicalise_path(str(target))

    @pytest.mark.skipif(
        sys.platform != "darwin" and os.name != "nt",
        reason="case normalisation only on case-insensitive platforms",
    )
    def test_applies_normcase_on_insensitive_fs(self, tmp_path: Path) -> None:
        target = tmp_path / "MixedCase"
        target.mkdir()
        result = canonicalise_path(target)
        assert result == os.path.normcase(result)


@pytest.mark.unit
class TestResolveExistingParents:
    def test_walks_until_missing_component(self, tmp_path: Path) -> None:
        existing = tmp_path / "a" / "b"
        existing.mkdir(parents=True)
        full = existing / "c" / "d"
        resolved = _resolve_existing_parents(full)
        assert resolved == existing / "c" / "d"
        assert resolved.parts[-2:] == ("c", "d")

    def test_fully_existing_path_resolves(self, tmp_path: Path) -> None:
        target = tmp_path / "only"
        target.mkdir()
        assert _resolve_existing_parents(target) == target.resolve()
