"""Plan DAG execution order from selected modules."""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Set

from transcriptx.core.pipeline.contracts import ExecutionPlan, RegistrySnapshot


class DAGPlanner:
    """Pure planning from requested modules + immutable registry snapshot."""

    def plan(
        self, requested_modules: List[str], registry_snapshot: RegistrySnapshot
    ) -> ExecutionPlan:
        modules = registry_snapshot.modules
        requested = list(dict.fromkeys(requested_modules))
        unknown = [m for m in requested if m not in modules]

        blocked: Dict[str, List[str]] = {}
        runnable_set: Set[str] = set()
        dependency_added: Set[str] = set()

        for module_name in requested:
            if module_name not in modules:
                continue
            self._collect_transitive(
                module_name=module_name,
                modules=modules,
                runnable_set=runnable_set,
                dependency_added=dependency_added,
                stack=[],
            )

        # Finalize-phase modules are selectable for reporting/coordinator but
        # must never be scheduled as DAG peers of chart writers.
        finalize_phase = {
            name
            for name in runnable_set
            if bool(getattr(modules.get(name), "finalize_phase", False))
        }
        runnable_set -= finalize_phase

        skipped_preflight = sorted(unknown)
        deterministic_order = self.topological_sort(
            sorted(runnable_set), registry_snapshot
        )
        dependency_added = dependency_added - set(requested)

        payload = {
            "requested": requested,
            "runnable": sorted(runnable_set),
            "dependency_added": sorted(dependency_added),
            "blocked": blocked,
            "skipped_preflight": skipped_preflight,
            "deterministic_order": deterministic_order,
        }
        plan_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return ExecutionPlan(plan_hash=plan_hash, **payload)

    def _collect_transitive(
        self,
        *,
        module_name: str,
        modules,
        runnable_set: Set[str],
        dependency_added: Set[str],
        stack: List[str],
    ) -> None:
        if module_name in stack:
            raise ValueError(
                f"Circular dependency detected: {' -> '.join(stack + [module_name])}"
            )
        if module_name in runnable_set:
            return
        if module_name not in modules:
            raise ValueError(f"Missing dependency: {module_name}")
        stack_next = [*stack, module_name]
        for dep in modules[module_name].dependencies:
            if dep not in modules:
                raise ValueError(f"Missing dependency for {module_name}: {dep}")
            dependency_added.add(dep)
            self._collect_transitive(
                module_name=dep,
                modules=modules,
                runnable_set=runnable_set,
                dependency_added=dependency_added,
                stack=stack_next,
            )
        runnable_set.add(module_name)

    def check_implicit_dependencies(self, module_name: str) -> List[str]:
        if module_name == "contagion":
            return ["emotion"]
        return []

    def topological_sort(
        self, module_names: List[str], registry_snapshot: RegistrySnapshot
    ) -> List[str]:
        modules = registry_snapshot.modules
        in_degree = {m: 0 for m in module_names}
        adjacency = {m: [] for m in module_names}
        module_set = set(module_names)
        for name in module_names:
            if name not in modules:
                continue
            deps = list(modules[name].dependencies)
            for opt in getattr(modules[name], "optional_dependencies", None) or []:
                if opt in module_set:
                    deps.append(opt)
            for dep in deps:
                if dep in module_set:
                    adjacency[dep].append(name)
                    in_degree[name] += 1

        queue = sorted([m for m, degree in in_degree.items() if degree == 0])
        ordered: List[str] = []
        while queue:
            current = queue.pop(0)
            ordered.append(current)
            for nxt in sorted(adjacency[current]):
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)
                    queue.sort()
        if len(ordered) != len(module_names):
            raise ValueError("Circular dependency detected in plan")
        return ordered

    def sort_by_category(
        self, module_names: List[str], registry_snapshot: RegistrySnapshot
    ) -> List[str]:
        modules = registry_snapshot.modules
        category_order = {"light": 0, "medium": 1, "heavy": 2}
        module_set = set(module_names)
        dep_graph = {
            module_name: {
                dep
                for dep in (
                    list(modules[module_name].dependencies)
                    + [
                        opt
                        for opt in (
                            getattr(modules[module_name], "optional_dependencies", None)
                            or []
                        )
                        if opt in module_set
                    ]
                )
                if dep in module_set
            }
            for module_name in module_names
            if module_name in modules
        }
        result: List[str] = []
        remaining = set(module_names)
        executed: set[str] = set()
        while remaining:
            ready = [
                mod
                for mod in remaining
                if mod in modules and dep_graph.get(mod, set()).issubset(executed)
            ]
            if not ready:
                result.extend([m for m in module_names if m in remaining])
                break
            ready_sorted = sorted(
                ready,
                key=lambda m: (category_order.get(modules[m].category, 2), m),
            )
            result.extend(ready_sorted)
            executed.update(ready_sorted)
            remaining -= set(ready_sorted)
        return result
