"""Registry of DAG nodes built from the module registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class DAGNode:
    """Compatibility node shape for DAG registration."""

    name: str
    description: str
    category: str
    dependencies: List[str]
    function: Any
    timeout_seconds: int = 600
    requirements: List[Any] = None
    enhancements: List[Any] = None


@dataclass
class DAGRegistry:
    nodes: Dict[str, DAGNode]

    def add_module(
        self,
        *,
        name: str,
        description: str,
        category: str,
        dependencies: List[str],
        function: Any,
        timeout_seconds: int = 600,
        requirements: Optional[List[Any]] = None,
        enhancements: Optional[List[Any]] = None,
    ) -> None:
        self.nodes[name] = DAGNode(
            name=name,
            description=description,
            category=category,
            dependencies=dependencies,
            function=function,
            timeout_seconds=timeout_seconds,
            requirements=requirements or [],
            enhancements=enhancements or [],
        )


def get_module_registry():
    from transcriptx.core.pipeline.module_registry import get_module_registry

    return get_module_registry()


def build_dag_registry_from_module_registry() -> DAGRegistry:
    registry = DAGRegistry(nodes={})
    module_registry = get_module_registry()
    for module_name in module_registry.get_available_modules():
        module_info = module_registry.get_module_info(module_name)
        module_function = module_registry.get_module_function(module_name)
        if module_info and module_function:
            registry.add_module(
                name=module_name,
                description=module_info.description,
                category=module_info.category,
                dependencies=module_info.dependencies,
                function=module_function,
                timeout_seconds=module_info.timeout_seconds,
                requirements=module_info.requirements,
                enhancements=module_info.enhancements,
            )
    return registry
