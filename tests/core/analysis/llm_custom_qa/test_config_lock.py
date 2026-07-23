"""Additional llm_custom_qa tests: config lock + failure codes."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from transcriptx.core.analysis.llm_custom_qa.errors import CustomQAFailureCode
from transcriptx.core.config.persistence import (
    ConfigLockTimeoutError,
    config_write_lock,
    patch_project_config_keys,
)
from transcriptx.core.utils.file_lock import FileLock


def test_config_write_lock_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "config.json"
    target.write_text('{"schema_version":1,"config":{}}', encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.core.config.persistence.CONFIG_LOCK_TIMEOUT_SECONDS",
        1,
    )
    held = threading.Event()
    release = threading.Event()

    def holder() -> None:
        with FileLock(target, timeout=5):
            held.set()
            release.wait(timeout=5)

    t = threading.Thread(target=holder)
    t.start()
    assert held.wait(timeout=2)
    with pytest.raises(ConfigLockTimeoutError) as exc:
        with config_write_lock(target):
            pass
    assert exc.value.error_code == CustomQAFailureCode.CONFIG_LOCK_TIMEOUT.value
    release.set()
    t.join(timeout=2)


def test_patch_project_config_keys_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        '{"schema_version":1,"config":{"analysis":{"llm_custom_qa":{"saved_questions":[]}}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "transcriptx.core.config.persistence.get_project_config_path",
        lambda: cfg_path,
    )
    merged = patch_project_config_keys(
        {"analysis": {"llm_custom_qa": {"saved_questions": ["What next?"]}}}
    )
    assert merged["analysis"]["llm_custom_qa"]["saved_questions"] == ["What next?"]
