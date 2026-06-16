from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.requires_docker
def test_playwright_chromium_launches_in_transcriptx_web_container() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    command = [
        "docker",
        "compose",
        "run",
        "--rm",
        "--entrypoint",
        "python",
        "transcriptx-web",
        "-c",
        (
            "from playwright.sync_api import sync_playwright; "
            "p = sync_playwright().start(); "
            "b = p.chromium.launch(); "
            "b.close(); "
            "p.stop(); "
            "print('playwright-ok')"
        ),
    ]

    result = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    if result.returncode != 0:
        detail = (
            "docker compose playwright smoke command failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        raise AssertionError(detail)

    assert "playwright-ok" in result.stdout
