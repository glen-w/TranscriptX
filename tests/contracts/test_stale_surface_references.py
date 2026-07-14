"""Contract tests for retired legacy entry points and stale surface references."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REMOVED_STUB_PATH = REPO_ROOT / "src/transcriptx/web/streamlit_app.py"
CANONICAL_APP = REPO_ROOT / "src/transcriptx/web/app.py"

_FORBIDDEN_RUNNABLE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"transcriptx\s+web-viewer\b"), "transcriptx web-viewer"),
    (
        re.compile(r"streamlit\s+run\s+\S*streamlit_app\.py"),
        "streamlit run …/streamlit_app.py",
    ),
    (
        re.compile(r"transcriptx\s+analyze\s+"),
        "transcriptx analyze …",
    ),
    (
        re.compile(r"transcriptx\s+transcript\s+"),
        "transcriptx transcript …",
    ),
)

# Files that may mention deprecated paths/terms (not as runnable examples).
_ALLOWLISTED_PATHS: frozenset[Path] = frozenset(
    {
        REPO_ROOT / "docs/public_surfaces.md",
        REPO_ROOT / "docs/generated/cli.md",
        REPO_ROOT / "tests/contracts/test_stale_surface_references.py",
        REPO_ROOT / "CHANGELOG.md",
        REPO_ROOT / "docs/dev/CONTRIBUTING.md",
        REPO_ROOT / "docs/runtime/transcription.md",
    }
)

_SCAN_ROOTS: tuple[Path, ...] = (
    REPO_ROOT / "docs",
    REPO_ROOT / "scripts",
    REPO_ROOT / "activate_env.sh",
    REPO_ROOT / "Makefile",
    REPO_ROOT / "transcriptx.sh",
)


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for root in _SCAN_ROOTS:
        if root.is_file():
            files.append(root)
            continue
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if "docs/archive" in path.as_posix():
                continue
            if path.suffix not in {".md", ".sh", ".py", ""} and path.name != "Makefile":
                continue
            files.append(path)
    return sorted(set(files))


def _is_allowlisted(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return False
    return path.resolve() in {p.resolve() for p in _ALLOWLISTED_PATHS}


def _line_looks_like_removed_cli_context(line: str, label: str) -> bool:
    lowered = line.lower()
    if label.startswith("transcriptx analyze") or label.startswith(
        "transcriptx transcript"
    ):
        return any(
            token in lowered
            for token in (
                "no supported",
                "not supported",
                "deprecated",
                "removed",
                "no `transcriptx",
                "there is no",
                "do not document",
            )
        )
    return False


def test_legacy_streamlit_stub_is_removed() -> None:
    assert not REMOVED_STUB_PATH.exists()


def test_canonical_web_launcher_resolves_app_py() -> None:
    from transcriptx.web import __main__ as web_main

    resolved = web_main._find_streamlit_app()
    assert resolved is not None
    assert resolved.name == "app.py"
    assert resolved.resolve() == CANONICAL_APP.resolve()


def test_canonical_web_help_is_discoverable() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "transcriptx.web", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "TranscriptX" in result.stdout or "transcriptx" in result.stdout.lower()


def test_no_legacy_streamlit_app_imports_in_repo() -> None:
    offenders: list[str] = []
    for path in (REPO_ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if (
            "transcriptx.web.streamlit_app" in text
            or "from transcriptx.web import streamlit_app" in text
        ):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    for path in (REPO_ROOT / "tests").rglob("*.py"):
        if path.name == "test_stale_surface_references.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "import transcriptx.web.streamlit_app" in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"unexpected legacy imports: {offenders}"


@pytest.mark.parametrize(
    "path", _iter_scan_files(), ids=lambda p: p.relative_to(REPO_ROOT).as_posix()
)
def test_no_runnable_stale_surface_references(path: Path) -> None:
    if _is_allowlisted(path):
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    for pattern, label in _FORBIDDEN_RUNNABLE_PATTERNS:
        for line in text.splitlines():
            if not pattern.search(line):
                continue
            if _line_looks_like_removed_cli_context(line, label):
                continue
            pytest.fail(
                f"{path.relative_to(REPO_ROOT)} contains runnable stale reference "
                f"({label}): {line.strip()}"
            )
