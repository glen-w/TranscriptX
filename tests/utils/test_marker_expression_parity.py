"""Lane marker expressions stay in sync and only use registered markers.

``make test-fast`` and bare ``pytest`` must select the same tests, so the
Makefile ``FAST_MARKERS`` variable must equal the ``-m`` in ``pytest.ini``
``addopts``. Other Makefile ``-m`` expressions must only name registered
markers (a typo there silently selects nothing or everything).
"""

from __future__ import annotations

import re
import shlex
from configparser import ConfigParser
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_KEYWORDS = {"and", "or", "not"}


def _addopts_marker_expr() -> str:
    cfg = ConfigParser()
    cfg.read(_ROOT / "pytest.ini", encoding="utf-8")
    args = shlex.split(cfg.get("pytest", "addopts"))
    return args[args.index("-m") + 1]


def _makefile_text() -> str:
    return (_ROOT / "Makefile").read_text(encoding="utf-8")


def _makefile_fast_markers() -> str:
    match = re.search(r"^FAST_MARKERS\s*:=\s*(.+)$", _makefile_text(), re.MULTILINE)
    assert match, "Makefile must define FAST_MARKERS"
    return match.group(1).strip()


def _makefile_marker_exprs() -> list[str]:
    text = _makefile_text().replace("$(FAST_MARKERS)", _makefile_fast_markers())
    return re.findall(r'-m\s+"([^"]+)"', text)


def _names(expr: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expr)) - _KEYWORDS


def test_makefile_fast_markers_match_pytest_ini_addopts() -> None:
    assert _makefile_fast_markers() == _addopts_marker_expr()


def test_fast_and_coverage_targets_use_shared_expression() -> None:
    text = _makefile_text()
    fast = re.search(r"^test-fast:\n(?:\t.*\n)+", text, re.MULTILINE)
    cov = re.search(r"^test-coverage:\n(?:\t.*\n)+", text, re.MULTILINE)
    assert fast and '-m "$(FAST_MARKERS)"' in fast.group(0)
    assert cov and "$(FAST_MARKERS)" in cov.group(0)


def test_fast_lane_excludes_contracts() -> None:
    assert "not contract" in _addopts_marker_expr()


def test_lane_expressions_only_use_registered_markers(
    pytestconfig: pytest.Config,
) -> None:
    registered = {
        line.split(":", 1)[0].split("(", 1)[0].strip()
        for line in pytestconfig.getini("markers")
    }
    exprs = [_addopts_marker_expr(), *_makefile_marker_exprs()]
    unknown = {name for expr in exprs for name in _names(expr)} - registered
    assert not unknown, f"unregistered markers in lane expressions: {sorted(unknown)}"
