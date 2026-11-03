"""GUI/AppTest isolation: never write fixtures into the owner library."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_DATA = (_REPO_ROOT / "data").resolve()


def _assert_isolated(label: str, raw: str | None) -> None:
    if not raw:
        pytest.fail(f"{label} must be set for GUI tests (isolated tmp / .test_data)")
    resolved = Path(raw).expanduser().resolve()
    if resolved == _REPO_DATA or _REPO_DATA in resolved.parents:
        pytest.fail(
            f"{label} resolves inside the repo data dir ({resolved}). "
            "Set TRANSCRIPTX_DATA_DIR / TRANSCRIPTX_OUTPUT_DIR to a temp path."
        )


@pytest.fixture(scope="session", autouse=True)
def _gui_lane_rejects_owner_library() -> None:
    _assert_isolated("TRANSCRIPTX_DATA_DIR", os.getenv("TRANSCRIPTX_DATA_DIR"))
    _assert_isolated("TRANSCRIPTX_OUTPUT_DIR", os.getenv("TRANSCRIPTX_OUTPUT_DIR"))
