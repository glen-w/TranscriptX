from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = ROOT / "src" / "transcriptx" / "core" / "pipeline"


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(), filename=str(path))


def _imports(path: Path) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _function_names(path: Path) -> set[str]:
    return {
        node.name
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _attribute_names(path: Path) -> set[str]:
    return {
        node.attr for node in ast.walk(_tree(path)) if isinstance(node, ast.Attribute)
    }


def test_pipeline_facade_does_not_import_config_internals() -> None:
    imports = _imports(PIPELINE_DIR / "pipeline.py")
    assert "transcriptx.core.config.persistence" not in imports
    assert "transcriptx.core.config.resolver" not in imports
    assert "transcriptx.core.config" not in imports


def test_dag_pipeline_retains_public_delegations_without_private_helper_implementations() -> (
    None
):
    functions = _function_names(PIPELINE_DIR / "dag_pipeline.py")
    assert {
        "topological_sort",
        "sort_by_category",
        "check_implicit_dependencies",
    }.issubset(functions)
    assert "_topological_sort" not in functions
    assert "_sort_by_category" not in functions
    assert "_check_implicit_dependencies" not in functions


def test_dag_planner_owns_planner_helper_implementations() -> None:
    planner_functions = _function_names(PIPELINE_DIR / "dag_planner.py")
    assert {
        "topological_sort",
        "sort_by_category",
        "check_implicit_dependencies",
    }.issubset(planner_functions)

    compat_functions = _function_names(PIPELINE_DIR / "dag_legacy_compat.py")
    assert "_topological_sort" not in compat_functions
    assert "_sort_by_category" not in compat_functions
    assert "_check_implicit_dependencies" not in compat_functions


def test_planner_private_attribute_does_not_leak_beyond_allowed_modules() -> None:
    allowed = {"dag_pipeline.py", "dag_legacy_compat.py"}
    offenders: list[str] = []
    for path in PIPELINE_DIR.glob("*.py"):
        if path.name in allowed:
            continue
        if "_planner" in _attribute_names(path):
            offenders.append(path.name)
    assert offenders == []


def test_parallel_and_max_workers_are_confined_to_public_facade_and_request() -> None:
    allowed = {"pipeline.py", "contracts.py"}
    offenders: list[str] = []
    for path in PIPELINE_DIR.glob("*.py"):
        if path.name in allowed:
            continue
        names = {
            node.arg for node in ast.walk(_tree(path)) if isinstance(node, ast.arg)
        }
        loaded_names = {
            node.id for node in ast.walk(_tree(path)) if isinstance(node, ast.Name)
        }
        if {"parallel", "max_workers"} & (names | loaded_names):
            offenders.append(path.name)
    assert offenders == []


def test_run_orchestrator_does_not_import_app_layer() -> None:
    imports = _imports(PIPELINE_DIR / "run_orchestrator.py")
    assert not any(
        name == "transcriptx.app" or name.startswith("transcriptx.app.")
        for name in imports
    )
