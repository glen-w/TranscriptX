"""Tests for Streamlit SpeechBrain file-watcher log noise filter."""

from __future__ import annotations

import logging

import pytest

from transcriptx.web.streamlit_watcher_noise import (
    SpeechBrainWatcherNoiseFilter,
    install_speechbrain_watcher_noise_filter,
)

_WATCHER = "streamlit.watcher.local_sources_watcher"


def _watcher_record(
    module: str,
    *,
    level: int = logging.WARNING,
    exc_info: tuple | None = None,
) -> logging.LogRecord:
    return logging.LogRecord(
        name=_WATCHER,
        level=level,
        pathname=__file__,
        lineno=1,
        msg="Examining the path of %s raised:",
        args=(module,),
        exc_info=exc_info,
    )


@pytest.fixture()
def noise_filter() -> SpeechBrainWatcherNoiseFilter:
    return SpeechBrainWatcherNoiseFilter()


def test_non_speechbrain_watcher_warning_passes(
    noise_filter: SpeechBrainWatcherNoiseFilter,
) -> None:
    record = _watcher_record("torch.nn")
    assert noise_filter.filter(record) is True
    assert "Examining the path of %s raised:" == record.msg
    assert record.args == ("torch.nn",)


def test_speechbrain_warnings_summarized_once(
    noise_filter: SpeechBrainWatcherNoiseFilter,
) -> None:
    first = _watcher_record(
        "speechbrain.integrations.nlp",
        exc_info=(ImportError, ImportError("no flair"), None),
    )
    second = _watcher_record(
        "speechbrain.integrations.k2_fsa",
        exc_info=(ImportError, ImportError("no k2"), None),
    )

    assert noise_filter.filter(first) is True
    assert "skipped SpeechBrain optional integrations" in first.msg
    assert first.args == ()
    assert first.exc_info is None

    assert noise_filter.filter(second) is False


def test_full_trace_emitted_at_debug(
    noise_filter: SpeechBrainWatcherNoiseFilter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="transcriptx")
    exc = ImportError("Failed to import flair")
    record = _watcher_record(
        "speechbrain.lobes.models.flair",
        exc_info=(ImportError, exc, None),
    )

    assert noise_filter.filter(record) is True
    assert any(
        "Streamlit watcher path probe failed for speechbrain.lobes.models.flair" in r
        for r in caplog.messages
    )


def test_install_is_idempotent() -> None:
    logger = logging.getLogger(_WATCHER)
    before = list(logger.filters)
    try:
        a = install_speechbrain_watcher_noise_filter()
        b = install_speechbrain_watcher_noise_filter()
        assert a is b
        assert (
            sum(1 for f in logger.filters if isinstance(f, SpeechBrainWatcherNoiseFilter))
            == 1
        )
    finally:
        logger.filters[:] = before
