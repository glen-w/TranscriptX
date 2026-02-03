"""
Helpers for writing module-scoped group outputs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from transcriptx.io import save_json, save_csv  # type: ignore[import]


def get_group_module_dir(base_dir: Path, module_name: str) -> Path:
    """
    Ensure and return a module-scoped group output directory.

    Creates:
        <base_dir>/<module_name>/
            combined/
            by_session/
            by_speaker/
    """
    module_dir = base_dir / module_name
    (module_dir / "combined").mkdir(parents=True, exist_ok=True)
    (module_dir / "by_session").mkdir(parents=True, exist_ok=True)
    (module_dir / "by_speaker").mkdir(parents=True, exist_ok=True)
    return module_dir


def write_group_module_json(
    module_dir: Path, name: str, data: Dict[str, Any]
) -> str:
    path = module_dir / "combined" / f"{name}.json"
    save_json(data, str(path))
    return str(path)


def write_group_module_csv(
    module_dir: Path, subdir: str, name: str, rows: List[Dict[str, Any]]
) -> str:
    path = module_dir / subdir / f"{name}.csv"
    save_csv(rows, str(path))
    return str(path)
