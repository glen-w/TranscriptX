"""Ban runtime consumers from importing Pydantic config models (defaults SoT)."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src" / "transcriptx"

_PROHIBITED_RELATIVE = (
    "core/analysis",
    "pipeline",
    "app",
    "web",
    "services",
    "io",
    "core/data_extraction",
    "core/viz",
    "core/store",
    "core/output",
    "core/llm",
)

# Frozen: relative path under src/transcriptx → frozenset of imported symbols.
_ALLOWLIST: dict[str, frozenset[str]] = {
    "core/analysis/llm_support/runtime.py": frozenset({"LLMSummaryEffort"}),
}


def _iter_prohibited_py_files() -> list[Path]:
    files: list[Path] = []
    for rel in _PROHIBITED_RELATIVE:
        root = SRC / rel
        if not root.exists():
            continue
        files.extend(p for p in root.rglob("*.py") if p.is_file())
    return files


def _models_imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            if mod == "transcriptx.core.config.models" or mod.startswith(
                "transcriptx.core.config.models."
            ):
                for alias in node.names:
                    names.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("transcriptx.core.config.models"):
                    names.add(alias.asname or alias.name.split(".")[-1])
    return names


def test_prohibited_trees_respect_frozen_models_allowlist() -> None:
    violations: list[str] = []
    for path in _iter_prohibited_py_files():
        rel = path.relative_to(SRC).as_posix()
        names = _models_imported_names(path)
        if not names:
            continue
        allowed = _ALLOWLIST.get(rel)
        if allowed is None:
            violations.append(f"{rel}: unexpected models import {sorted(names)}")
            continue
        extra = names - allowed
        if extra:
            violations.append(f"{rel}: non-allowlisted symbols {sorted(extra)}")
    assert not violations, "Forbidden config.models imports:\n" + "\n".join(violations)


def test_allowlist_entries_still_present() -> None:
    for rel, symbols in _ALLOWLIST.items():
        path = SRC / rel
        assert path.is_file(), f"allowlisted file missing: {rel}"
        found = _models_imported_names(path)
        missing = symbols - found
        assert not missing, f"allowlisted import(s) missing in {rel}: {sorted(missing)}"
