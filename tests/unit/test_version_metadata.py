"""Release metadata: package version matches pyproject and web shim."""

from __future__ import annotations

from pathlib import Path

import pytest

import transcriptx
from transcriptx import __version__ as root_version
from transcriptx.web import __version__ as web_version


def _project_version_from_pyproject(pyproject_path: Path) -> str:
    """Parse ``version = "…"`` under ``[project]`` (no extra TOML dependency on 3.10)."""
    text = pyproject_path.read_text(encoding="utf-8")
    in_project = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if not in_project:
            continue
        if stripped.startswith("version"):
            _, _, rhs = line.partition("=")
            raw = rhs.split("#", 1)[0].strip().strip('"').strip("'")
            return raw
    raise AssertionError("no version = under [project] in pyproject.toml")


@pytest.mark.unit
def test_root_and_web_package_versions_match() -> None:
    assert root_version == web_version
    assert root_version  # non-empty string


@pytest.mark.unit
def test_package_version_matches_pyproject() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    pyproject = repo_root / "pyproject.toml"
    assert _project_version_from_pyproject(pyproject) == transcriptx.__version__
