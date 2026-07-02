"""Guard against engine/io/app layers importing web perf instrumentation."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (
    ROOT / "src" / "transcriptx" / "io",
    ROOT / "src" / "transcriptx" / "core",
    ROOT / "src" / "transcriptx" / "app",
)


def _import_from_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def _imports_perf_from_web(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "transcriptx.web.perf" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom) and node.module == "transcriptx.web":
            if any(alias.name == "perf" for alias in node.names):
                return True
    return False


def test_engine_io_app_do_not_import_web_perf() -> None:
    violations: list[str] = []
    for root in SCAN_ROOTS:
        for path in root.rglob("*.py"):
            if _imports_perf_from_web(path):
                violations.append(str(path.relative_to(ROOT)))
            elif "transcriptx.web.perf" in _import_from_modules(path):
                violations.append(str(path.relative_to(ROOT)))
    assert not violations, "web perf imports in engine/io/app:\n" + "\n".join(
        sorted(set(violations))
    )
