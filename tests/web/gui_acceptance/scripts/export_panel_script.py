"""AppTest entry: render export panel for TRANSCRIPTX_GUI_ACC_RUN_ROOT."""

from __future__ import annotations

import os
from pathlib import Path

from transcriptx.web.components.export_panel import render_export_panel_ui
from transcriptx.web.services.artifact_service import ArtifactService

_run_root = Path(os.environ["TRANSCRIPTX_GUI_ACC_RUN_ROOT"])
_artifacts = ArtifactService.list_artifacts(_run_root)
render_export_panel_ui(
    run_root=_run_root,
    artifacts=_artifacts,
    key_prefix="gui_acc_export",
)
