"""Import smoke tests to detect side effects early."""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "transcriptx.core.transcription",
        "transcriptx.core.transcription_runtime",
        "transcriptx.core.transcription_diagnostics",
        "transcriptx.core.pipeline.pipeline",
        "transcriptx.core.utils.paths",
        "transcriptx.core.utils.config.workflow",
        "transcriptx.cli.main",
        "transcriptx.cli.transcription_common",
        "transcriptx.cli.deduplication_workflow",
    ],
)
def test_module_imports_without_side_effects(module_name: str) -> None:
    importlib.import_module(module_name)
