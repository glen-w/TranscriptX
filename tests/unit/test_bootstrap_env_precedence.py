"""Repo ``.env`` must not override an explicitly set process environment."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_shell_env_wins_over_repo_dotenv(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("dotenv")
    import transcriptx._bootstrap as boot

    env_file = tmp_path / ".env"
    env_file.write_text(
        "TRANSCRIPTX_TRANSCRIPTS_DIR=/owner/library\nTX_TEST_ONLY_FROM_DOTENV=yes\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TRANSCRIPTX_TRANSCRIPTS_DIR", str(tmp_path / "isolated"))
    monkeypatch.delenv("TX_TEST_ONLY_FROM_DOTENV", raising=False)
    monkeypatch.setattr(boot, "_bootstrapped", False)

    boot.bootstrap(env_path=env_file)

    import os

    assert os.environ["TRANSCRIPTX_TRANSCRIPTS_DIR"] == str(tmp_path / "isolated")
    # Keys absent from the shell are still filled from .env.
    assert os.environ.get("TX_TEST_ONLY_FROM_DOTENV") == "yes"
    monkeypatch.delenv("TX_TEST_ONLY_FROM_DOTENV", raising=False)
