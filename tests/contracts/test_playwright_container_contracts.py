"""Contract tests for playwright container contracts."""

from __future__ import annotations

from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_runtime_dockerfile_includes_playwright_system_dependencies() -> None:
    dockerfile = (_repo_root() / "Dockerfile").read_text(encoding="utf-8")

    required_packages = {
        "libnss3",
        "libnspr4",
        "libatk1.0-0",
        "libatk-bridge2.0-0",
        "libcups2",
        "libatspi2.0-0",
        "libxcomposite1",
        "libxdamage1",
        "libxfixes3",
        "libxrandr2",
        "libgbm1",
        "libxkbcommon0",
        "libpango-1.0-0",
        "libcairo2",
        "libasound2",
        "libdrm2",
        "libx11-6",
        "libxcb1",
        "libxext6",
        "libxrender1",
        "libglib2.0-0",
    }

    missing = sorted(pkg for pkg in required_packages if pkg not in dockerfile)
    assert missing == []


@pytest.mark.unit
def test_compose_sets_playwright_browser_cache_path() -> None:
    compose = (_repo_root() / "docker-compose.yml").read_text(encoding="utf-8")
    assert "PLAYWRIGHT_BROWSERS_PATH=/data/.cache/ms-playwright" in compose


@pytest.mark.unit
def test_compose_persists_data_dir_for_speaker_voice() -> None:
    """Trusted-voice artefacts live under speaker_profiles on the ./data bind mount.

    Image rebuild/recreate must not wipe enrolled samples; only an explicit
    privacy revoke or profile wipe deletes voice/. Compose must keep DATA_DIR
    on a host bind, not an anonymous/named volume.
    """
    compose = (_repo_root() / "docker-compose.yml").read_text(encoding="utf-8")
    assert "./data:/data" in compose
    assert "TRANSCRIPTX_DATA_DIR=/data" in compose
    # Named volume is only for HF/home cache — not project data.
    assert "transcriptx_cache:/home/transcriptx/.cache" in compose
    top_volumes = (
        compose.rsplit("\nvolumes:\n", 1)[-1] if "\nvolumes:\n" in compose else ""
    )
    assert "speaker_profiles" not in top_volumes


@pytest.mark.unit
def test_compose_persists_config_dir_outside_clone_capable() -> None:
    """Project settings (saved questions, menus) mount via HOST_CONFIG_DIR.

    Default remains ./data/.transcriptx; operators can point HOST_CONFIG_DIR
    outside the git clone so wiping ./data does not drop Settings.
    """
    compose = (_repo_root() / "docker-compose.yml").read_text(encoding="utf-8")
    assert "${HOST_CONFIG_DIR:-./data/.transcriptx}:/data/.transcriptx" in compose
    assert "TRANSCRIPTX_CONFIG_DIR=/data/.transcriptx" in compose
    app = (_repo_root() / "src/transcriptx/web/app.py").read_text(encoding="utf-8")
    assert "apply_project_config_to_live_facade" in app
