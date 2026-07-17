"""AST-based import-cycle check for run_cleanup (no module execution)."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

PACKAGE = "transcriptx.web.services.run_cleanup"
PKG_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "transcriptx"
    / "web"
    / "services"
    / "run_cleanup"
)


def _module_name_for(path: Path) -> str:
    rel = path.relative_to(PKG_ROOT)
    if rel.name == "__init__.py":
        return PACKAGE
    return f"{PACKAGE}.{rel.with_suffix('').as_posix().replace('/', '.')}"


def _internal_imports(tree: ast.AST, current_mod: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == PACKAGE or name.startswith(PACKAGE + "."):
                    found.add(name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = current_mod.split(".")
                if current_mod == PACKAGE:
                    parent_parts = parts[: max(0, len(parts) - (node.level - 1))]
                else:
                    parent_parts = parts[: -node.level]
                base = ".".join(parent_parts) if parent_parts else PACKAGE
                if node.module:
                    abs_mod = f"{base}.{node.module}" if base else node.module
                else:
                    abs_mod = base
            else:
                abs_mod = node.module or ""

            if not (abs_mod == PACKAGE or abs_mod.startswith(PACKAGE + ".")):
                continue

            # from package import submodule  -> edge to package.submodule
            # from package.submodule import name -> edge to package.submodule
            if abs_mod == PACKAGE:
                for alias in node.names:
                    found.add(f"{PACKAGE}.{alias.name}")
            else:
                found.add(abs_mod)
    return found


def _resolve_to_known(dep: str, known_modules: set[str]) -> str | None:
    if dep in known_modules:
        return dep
    tip = dep
    while tip not in known_modules and tip.startswith(PACKAGE):
        if "." not in tip:
            break
        tip = tip.rsplit(".", 1)[0]
    if tip in known_modules:
        return tip
    return None


def _build_graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    known_modules = {_module_name_for(p) for p in PKG_ROOT.glob("*.py")}
    known_modules.add(PACKAGE)
    for path in sorted(PKG_ROOT.glob("*.py")):
        mod = _module_name_for(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for dep in _internal_imports(tree, mod):
            resolved = _resolve_to_known(dep, known_modules)
            if resolved is None or resolved == mod:
                continue
            # Ignore package <-> service façade edges from __init__ re-exports:
            # __init__ imports service; service imports sibling submodules via
            # ``from package import sibling`` (resolved to package.sibling above).
            graph[mod].add(resolved)
    return dict(graph)


def _find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def dfs(node: str) -> list[str] | None:
        visiting.add(node)
        stack.append(node)
        for nbr in sorted(graph.get(node, ())):
            if nbr in visiting:
                i = stack.index(nbr)
                return stack[i:] + [nbr]
            if nbr not in visited:
                found = dfs(nbr)
                if found:
                    return found
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for n in sorted(graph):
        if n not in visited:
            cyc = dfs(n)
            if cyc:
                return cyc
    return None


def test_run_cleanup_has_no_import_cycles():
    graph = _build_graph()
    cycle = _find_cycle(graph)
    assert cycle is None, f"import cycle detected: {' -> '.join(cycle or ())}"


def test_staging_and_journal_do_not_import_each_other():
    graph = _build_graph()
    staging = f"{PACKAGE}.staging"
    journal = f"{PACKAGE}.journal"
    assert journal not in graph.get(staging, ())
    assert staging not in graph.get(journal, ())
