"""Base Compose library mounts: Admit needs a writable transcripts volume."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_COMPOSE = _REPO / "docker-compose.yml"


def _volume_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("- ") and ":/mnt/" in line
    ]


def _line_for_target(lines: list[str], target: str) -> str:
    matches = [
        line for line in lines if re.search(rf":{re.escape(target)}(?::|\s|$)", line)
    ]
    assert len(matches) == 1, matches
    return matches[0]


@pytest.mark.unit
@pytest.mark.contract
def test_base_compose_library_mounts_match_admit_door() -> None:
    """README Compose file is the admit door: transcripts writable, inbox and recordings read-only."""
    text = _COMPOSE.read_text(encoding="utf-8")
    lines = _volume_lines(text)

    transcripts = _line_for_target(lines, "/mnt/transcripts")
    inbox = _line_for_target(lines, "/mnt/transcript-inbox")
    recordings = _line_for_target(lines, "/mnt/recordings")
    imports = _line_for_target(lines, "/mnt/recordings/imports")

    assert not transcripts.endswith(":ro")
    assert inbox.endswith(":/mnt/transcript-inbox:ro")
    assert recordings.endswith(":/mnt/recordings:ro")
    assert imports.endswith(":/mnt/recordings/imports")
    assert not imports.endswith(":ro")
    assert "writable" in text.split("services:", 1)[0].lower()
    readme = (_REPO / "README.md").read_text(encoding="utf-8")
    assert "docker compose up transcriptx-web" in readme
