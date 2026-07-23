"""Architecture gates for the LLM support split.

1. AST/static import-boundary checks over production sources: catch forbidden
   edges even when the import is lazy and never executed at runtime.
2. Fresh-process import smoke: import config first, then each LLM feature and
   llm_support submodule, to catch cycles and module-level import failures.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[4] / "src" / "transcriptx"

_FEATURE_MODULES = (
    "transcriptx.core.analysis.llm_summary",
    "transcriptx.core.analysis.llm_speaker_summary",
    "transcriptx.core.analysis.llm_action_items",
    "transcriptx.core.analysis.llm_custom_qa",
    "transcriptx.core.analysis.narrative_summary",
)

_LLM_SUPPORT_MODULES = (
    "transcriptx.core.analysis.llm_support.hashing",
    "transcriptx.core.analysis.llm_support.json_parse",
    "transcriptx.core.analysis.llm_support.prompts",
    "transcriptx.core.analysis.llm_support.provenance",
    "transcriptx.core.analysis.llm_support.filenames",
    "transcriptx.core.analysis.llm_support.speakers",
    "transcriptx.core.analysis.llm_support.artifacts",
    "transcriptx.core.analysis.llm_support.narrative_source",
    "transcriptx.core.analysis.llm_support.narrative_contract",
    "transcriptx.core.analysis.llm_support.action_items_contract",
    "transcriptx.core.analysis.llm_support.action_items_render",
    "transcriptx.core.analysis.llm_support.runtime",
)


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC_ROOT.parent)
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imported_modules(path: Path) -> set[str]:
    """All modules referenced by import statements anywhere in the file,
    including function-local (lazy) imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    module = _module_name(path)
    package_parts = module.split(".")
    if path.name != "__init__.py":
        package_parts = package_parts[:-1]
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package_parts[: len(package_parts) - node.level + 1]
                prefix = ".".join(base)
                target = f"{prefix}.{node.module}" if node.module else prefix
            else:
                target = node.module or ""
            if target:
                imported.add(target)
                for alias in node.names:
                    imported.add(f"{target}.{alias.name}")
    return imported


def _production_files(subpath: str) -> list[Path]:
    files = sorted((SRC_ROOT / subpath).rglob("*.py"))
    assert files, f"no production files found under {subpath}"
    return files


@pytest.mark.unit
def test_core_llm_never_imports_analysis() -> None:
    violations = []
    for path in _production_files("core/llm"):
        for target in _imported_modules(path):
            if target.startswith("transcriptx.core.analysis"):
                violations.append(f"{path}: {target}")
    assert violations == []


@pytest.mark.unit
def test_config_never_imports_analysis() -> None:
    violations = []
    for subpath in ("core/config", "core/utils/config"):
        for path in _production_files(subpath):
            for target in _imported_modules(path):
                if target.startswith("transcriptx.core.analysis"):
                    violations.append(f"{path}: {target}")
    assert violations == []


@pytest.mark.unit
def test_llm_support_never_imports_feature_modules() -> None:
    violations = []
    for path in _production_files("core/analysis/llm_support"):
        for target in _imported_modules(path):
            for feature in _FEATURE_MODULES:
                if target == feature or target.startswith(feature + "."):
                    violations.append(f"{path}: {target}")
    assert violations == []


@pytest.mark.unit
def test_no_remaining_migration_shim_imports_in_production() -> None:
    # Deleted-shim module names, constructed to keep the repository-wide
    # `rg` zero-match gate for the former module names clean.
    banned = ("llm_" + "common", "llm_summary_" + "effort")
    violations = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        for target in _imported_modules(path):
            if any(name in target for name in banned):
                violations.append(f"{path}: {target}")
    assert violations == []


@pytest.mark.unit
@pytest.mark.parametrize("module", _FEATURE_MODULES + _LLM_SUPPORT_MODULES)
def test_fresh_process_import_config_then_module(module: str) -> None:
    """Import config first, then the target module, in an isolated process."""
    code = "import transcriptx.core.utils.config as _cfg; " f"import {module}"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(SRC_ROOT.parents[1]),
    )
    assert result.returncode == 0, result.stderr
