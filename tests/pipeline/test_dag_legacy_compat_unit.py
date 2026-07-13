"""Unit tests for DAGLegacyCompatHelpers edge branches."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from transcriptx.core.pipeline.dag_legacy_compat import DAGLegacyCompatHelpers


class _FakeNode:
    def __init__(
        self,
        dependencies: Optional[List[str]] = None,
        function: Any = lambda: None,
        raise_on_function: Optional[BaseException] = None,
    ) -> None:
        self.dependencies = list(dependencies or [])
        self._function = function
        self._raise_on_function = raise_on_function

    @property
    def function(self) -> Any:
        if self._raise_on_function is not None:
            raise self._raise_on_function
        return self._function


class _FakePipeline:
    def __init__(self, nodes: Dict[str, _FakeNode]) -> None:
        self.nodes = nodes
        self._topo_error: Optional[BaseException] = None
        self._topo_return: Optional[List[str]] = None

    def check_implicit_dependencies(self, _module_name: str) -> List[str]:
        return []

    def topological_sort(self, modules: List[str]) -> List[str]:
        if self._topo_error is not None:
            raise self._topo_error
        if self._topo_return is not None:
            return list(self._topo_return)
        return list(modules)

    def sort_by_category(self, modules: List[str]) -> List[str]:
        return list(modules)


@pytest.mark.unit
def test_validate_dependencies_reports_missing_module() -> None:
    helpers = DAGLegacyCompatHelpers()
    pipeline = _FakePipeline({"a": _FakeNode()})
    ok, errors = helpers.validate_dependencies(pipeline, modules=["a", "missing"])
    assert ok is False
    assert any("not found in registry" in e for e in errors)


@pytest.mark.unit
def test_validate_dependencies_circular_when_topo_drops_modules() -> None:
    helpers = DAGLegacyCompatHelpers()
    pipeline = _FakePipeline({"a": _FakeNode(), "b": _FakeNode(["a"])})
    pipeline._topo_return = ["a"]  # shorter than requested → cycle signal
    ok, errors = helpers.validate_dependencies(pipeline, modules=["a", "b"])
    assert ok is False
    assert any("Circular dependency" in e for e in errors)


@pytest.mark.unit
def test_validate_dependencies_topo_value_error_is_circular() -> None:
    helpers = DAGLegacyCompatHelpers()
    pipeline = _FakePipeline({"a": _FakeNode()})
    pipeline._topo_error = ValueError("cycle")
    ok, errors = helpers.validate_dependencies(pipeline, modules=["a"])
    assert ok is False
    assert any("Circular dependency detected" in e for e in errors)


@pytest.mark.unit
def test_validate_dependencies_topo_generic_exception_message() -> None:
    helpers = DAGLegacyCompatHelpers()
    pipeline = _FakePipeline({"a": _FakeNode()})
    pipeline._topo_error = RuntimeError("boom")
    ok, errors = helpers.validate_dependencies(pipeline, modules=["a"])
    assert ok is False
    assert any("Circular dependency check failed: boom" in e for e in errors)


@pytest.mark.unit
def test_resolve_dependencies_skips_unknown_selected_and_raises_on_missing_dep() -> (
    None
):
    helpers = DAGLegacyCompatHelpers()
    # Selected unknown module is ignored; registered module depends on missing dep.
    pipeline = _FakePipeline({"child": _FakeNode(["ghost"])})
    with pytest.raises(ValueError, match="Missing dependencies"):
        helpers.resolve_dependencies(pipeline, ["child", "not_registered"])


@pytest.mark.unit
def test_preflight_check_resolve_failure() -> None:
    helpers = DAGLegacyCompatHelpers()
    pipeline = _FakePipeline({"child": _FakeNode(["ghost"])})
    result = helpers.preflight_check(pipeline, ["child"])
    assert result["all_importable"] is False
    assert any("Failed to resolve dependencies" in w for w in result["warnings"])


@pytest.mark.unit
def test_preflight_check_function_none_and_import_errors() -> None:
    helpers = DAGLegacyCompatHelpers()
    pipeline = _FakePipeline(
        {
            "ok": _FakeNode(function=lambda: None),
            "none_fn": _FakeNode(function=None),
            "bad_import": _FakeNode(raise_on_function=ImportError("missing pkg")),
            "other": _FakeNode(raise_on_function=RuntimeError("weird")),
        }
    )
    result = helpers.preflight_check(
        pipeline, ["ok", "none_fn", "bad_import", "other", "absent"]
    )
    assert "absent" in result["skipped_modules"]
    assert "none_fn" in result["missing_dependencies"]
    assert "bad_import" in result["missing_dependencies"]
    assert result["all_importable"] is False
    assert any("function is None" in w for w in result["warnings"])
    assert any("import failed" in w for w in result["warnings"])
    assert any("check failed" in w for w in result["warnings"])


@pytest.mark.unit
def test_get_dependency_graph_copies_deps() -> None:
    helpers = DAGLegacyCompatHelpers()
    pipeline = _FakePipeline(
        {
            "base": _FakeNode([]),
            "child": _FakeNode(["base"]),
        }
    )
    graph = helpers.get_dependency_graph(pipeline, ["child"])
    assert graph["base"] == []
    assert graph["child"] == ["base"]


@pytest.mark.unit
def test_make_deterministic_sorts() -> None:
    helpers = DAGLegacyCompatHelpers()
    assert helpers._make_deterministic(["c", "a", "b"]) == ["a", "b", "c"]
