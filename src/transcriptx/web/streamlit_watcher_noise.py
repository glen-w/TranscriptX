"""Quiet Streamlit file-watcher noise from SpeechBrain optional integrations.

SpeechBrain exposes lazy optional modules (``flair``, ``k2``, …). Streamlit's
``LocalSourcesWatcher`` probes ``__file__`` / ``__path__`` on every imported
module and logs a full WARNING traceback when those lazy imports fail.

This filter keeps one summary WARNING and moves per-module stack traces to
DEBUG on the ``transcriptx`` logger.
"""

from __future__ import annotations

import logging
from typing import Final

_WATCHER_LOGGER: Final = "streamlit.watcher.local_sources_watcher"
_MSG_MARKER: Final = "Examining the path of"
_SPEECHBRAIN_PREFIX: Final = "speechbrain"


class SpeechBrainWatcherNoiseFilter(logging.Filter):
    """Collapse SpeechBrain optional-import watcher WARNINGs into one summary."""

    def __init__(self) -> None:
        super().__init__(name=_WATCHER_LOGGER)
        self._seen_modules: set[str] = set()
        self._summary_emitted = False

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != _WATCHER_LOGGER:
            return True
        if not isinstance(record.msg, str) or _MSG_MARKER not in record.msg:
            return True

        module_name = _module_name_from_record(record)
        if not module_name.startswith(_SPEECHBRAIN_PREFIX):
            return True

        self._seen_modules.add(module_name)
        _emit_debug_trace(module_name, record.exc_info)

        if self._summary_emitted:
            return False

        self._summary_emitted = True
        record.msg = (
            "Streamlit file watcher skipped SpeechBrain optional integrations "
            "(missing extras such as flair/k2); full traces at DEBUG"
        )
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        return True


def install_speechbrain_watcher_noise_filter() -> SpeechBrainWatcherNoiseFilter:
    """Attach the filter once to Streamlit's local sources watcher logger."""
    logger = logging.getLogger(_WATCHER_LOGGER)
    for existing in logger.filters:
        if isinstance(existing, SpeechBrainWatcherNoiseFilter):
            return existing
    filt = SpeechBrainWatcherNoiseFilter()
    logger.addFilter(filt)
    return filt


def _module_name_from_record(record: logging.LogRecord) -> str:
    if record.args:
        if isinstance(record.args, tuple) and record.args:
            return str(record.args[0])
        if isinstance(record.args, dict):
            # %-format with mapping is uncommon here; fall through.
            pass
    # Last resort: parse from already-formatted message text.
    try:
        formatted = record.getMessage()
    except Exception:
        return ""
    # "Examining the path of <name> raised:"
    prefix = f"{_MSG_MARKER} "
    if prefix in formatted:
        rest = formatted.split(prefix, 1)[1]
        return rest.split(" raised", 1)[0].strip()
    return ""


def _emit_debug_trace(module_name: str, exc_info: object) -> None:
    tx = logging.getLogger("transcriptx")
    if not tx.isEnabledFor(logging.DEBUG):
        return
    tx.debug(
        "Streamlit watcher path probe failed for %s",
        module_name,
        exc_info=exc_info if exc_info else None,
    )
