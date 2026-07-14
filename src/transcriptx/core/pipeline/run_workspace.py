"""Allocate and manage per-run workspace directories."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Iterator

from transcriptx.core.pipeline.contracts import RunWorkspace
from transcriptx.core.utils._path_core import (
    clear_transcript_output_dir,
    set_transcript_output_dir,
)
from transcriptx.core.utils import paths as paths_module


class RunWorkspaceService:
    def create(
        self,
        *,
        transcript_path: str,
        slug: str,
        run_id: str,
        output_dir_override: str | None = None,
    ) -> RunWorkspace:
        base_output = (
            output_dir_override
            or str(paths_module.OUTPUTS_DIR)
            or os.getenv("TRANSCRIPTX_OUTPUT_DIR")
        )
        output_dir = str(Path(base_output) / slug / run_id)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return RunWorkspace(output_dir=output_dir)

    @contextmanager
    def scoped_transcript_output_dir(
        self, transcript_path: str, output_dir: str
    ) -> Iterator[None]:
        set_transcript_output_dir(transcript_path, output_dir)
        try:
            yield
        finally:
            clear_transcript_output_dir(transcript_path)
