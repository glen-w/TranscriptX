from __future__ import annotations

from transcriptx.core.utils.downloads import (
    downloads_disabled,
    downloads_disabled_failfast_message,
)


def test_downloads_disabled_defaults_to_false_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_DISABLE_DOWNLOADS", raising=False)
    assert downloads_disabled() is False


def test_downloads_disabled_accepts_common_truthy_values(monkeypatch) -> None:
    for value in ("1", "true", "yes", "on", " TRUE "):
        monkeypatch.setenv("TRANSCRIPTX_DISABLE_DOWNLOADS", value)
        assert downloads_disabled() is True


def test_downloads_disabled_treats_non_truthy_values_as_enabled(monkeypatch) -> None:
    for value in ("0", "false", "off", "nope"):
        monkeypatch.setenv("TRANSCRIPTX_DISABLE_DOWNLOADS", value)
        assert downloads_disabled() is False


def test_downloads_disabled_failfast_message_appends_extra_hint() -> None:
    message = downloads_disabled_failfast_message(
        "TextBlob corpora", "Run python -m textblob.download_corpora"
    )
    assert "TextBlob corpora is not available" in message
    assert "TRANSCRIPTX_DISABLE_DOWNLOADS=1" in message
    assert "Run python -m textblob.download_corpora" in message
