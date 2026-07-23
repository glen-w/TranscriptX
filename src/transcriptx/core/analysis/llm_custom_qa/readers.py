"""Safe readers for llm_custom_qa analytical artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from transcriptx.core.analysis.llm_custom_qa.commit import (
    analytical_artifacts_readable,
    read_active_generation_id,
)
from transcriptx.core.analysis.llm_custom_qa.constants import MODULE_NAME


def _module_succeeded(run_root: Path) -> bool:
    results_path = run_root / "run_results.json"
    if not results_path.exists():
        return False
    try:
        data = json.loads(results_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    modules_run = [str(x) for x in (data.get("modules_run") or []) if x]
    modules_failed = [str(x) for x in (data.get("modules_failed") or []) if x]
    if MODULE_NAME in modules_failed:
        return False
    if MODULE_NAME in modules_run:
        return True
    # Legacy / test shapes
    modules = data.get("modules") or data.get("module_results") or []
    if isinstance(modules, dict):
        row = modules.get(MODULE_NAME) or {}
        return str(row.get("status") or "").lower() == "success"
    if isinstance(modules, list):
        for row in modules:
            if not isinstance(row, dict):
                continue
            name = row.get("module") or row.get("module_name")
            if name == MODULE_NAME:
                return str(row.get("status") or "").lower() == "success"
    return False


def find_committed_custom_qa_artifact(run_root: Path) -> Optional[Path]:
    """Return the committed JSON artifact path when readable, else None."""
    if not _module_succeeded(Path(run_root)):
        return None
    matches = sorted(Path(run_root).rglob(f"*_{MODULE_NAME}.json"))
    for path in matches:
        # Stem without .json → e.g. .../demo_llm_custom_qa
        stem = path.with_suffix("")
        if analytical_artifacts_readable(stem=stem, module_succeeded=True):
            return path
        # Legacy / first-write without pointer: require active pointer absent ⇒ missing
        if read_active_generation_id(stem) is None:
            continue
    return None


def load_committed_custom_qa_payload(run_root: Path) -> Optional[dict[str, Any]]:
    path = find_committed_custom_qa_artifact(run_root)
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None
