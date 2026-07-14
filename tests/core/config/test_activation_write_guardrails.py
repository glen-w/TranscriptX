"""Tests for activation write guardrails."""

from __future__ import annotations

import ast
from pathlib import Path

_ALLOWED_DIRECT_WRITE_FILES = {
    "src/transcriptx/core/config/profile_target_adapter.py",
    "src/transcriptx/core/utils/config/analysis.py",
    "src/transcriptx/core/utils/config/main.py",
    "src/transcriptx/core/utils/config/system.py",
}


def _is_active_profile_attr(name: str) -> bool:
    return name.startswith("active_") and name.endswith("_profile")


def test_no_direct_active_profile_mutation_outside_adapter_owned_paths() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    src_root = repo_root / "src"
    violations: list[str] = []

    for py_file in src_root.rglob("*.py"):
        rel = py_file.relative_to(repo_root).as_posix()
        if rel in _ALLOWED_DIRECT_WRITE_FILES:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and _is_active_profile_attr(
                        target.attr
                    ):
                        violations.append(f"{rel}:{node.lineno}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "setattr":
                    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                        attr_name = node.args[1].value
                        if isinstance(attr_name, str) and _is_active_profile_attr(
                            attr_name
                        ):
                            violations.append(f"{rel}:{node.lineno}")

    assert violations == [], "direct active profile writes found:\n" + "\n".join(
        violations
    )
