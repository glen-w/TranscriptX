from __future__ import annotations

from transcriptx.core.pipeline.ports import ReporterSink
from transcriptx.core.utils.logger import get_logger


class LoggingReporter(ReporterSink):
    def __init__(self) -> None:
        self._logger = get_logger()

    def info(self, message: str) -> None:
        self._logger.info(message)

    def warning(self, message: str) -> None:
        self._logger.warning(message)

    def error(self, message: str) -> None:
        self._logger.error(message)
