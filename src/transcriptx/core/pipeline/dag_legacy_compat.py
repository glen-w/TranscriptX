"""Legacy compatibility helpers retained for DAG pipeline callers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class DAGLegacyCompatHelpers:
    """Legacy DAG helper surface retained for compatibility callers/tests."""

    def resolve_dependencies(
        self, pipeline: Any, selected_modules: List[str]
    ) -> List[str]:
        modules_to_run = {
            module for module in selected_modules if module in pipeline.nodes
        }
        modules_to_process = set(modules_to_run)

        while modules_to_process:
            new_modules = set()
            for module_name in modules_to_process:
                if module_name in pipeline.nodes:
                    node = pipeline.nodes[module_name]
                    for dep in node.dependencies:
                        if dep in pipeline.nodes and dep not in modules_to_run:
                            modules_to_run.add(dep)
                            new_modules.add(dep)
                    implicit_deps = pipeline.check_implicit_dependencies(module_name)
                    for dep in implicit_deps:
                        if dep in pipeline.nodes and dep not in modules_to_run:
                            modules_to_run.add(dep)
                            new_modules.add(dep)
            modules_to_process = new_modules

        missing_deps: Dict[str, List[str]] = {}
        for module_name in modules_to_run:
            if module_name not in pipeline.nodes:
                continue
            node = pipeline.nodes[module_name]
            deps = list(node.dependencies)
            deps.extend(pipeline.check_implicit_dependencies(module_name))
            missing = [dep for dep in deps if dep not in pipeline.nodes]
            if missing:
                missing_deps[module_name] = missing
        if missing_deps:
            details = "; ".join(
                f"{module}: {', '.join(deps)}"
                for module, deps in sorted(missing_deps.items())
            )
            raise ValueError(f"Missing dependencies for module(s): {details}")

        execution_order = pipeline.topological_sort(list(modules_to_run))
        execution_order = self._make_deterministic(execution_order)
        return pipeline.sort_by_category(execution_order)

    def validate_dependencies(
        self, pipeline: Any, modules: Optional[List[str]] = None
    ) -> tuple[bool, List[str]]:
        errors: List[str] = []
        if modules is None:
            modules = list(pipeline.nodes.keys())
        for module_name in modules:
            if module_name not in pipeline.nodes:
                errors.append(f"Module '{module_name}' not found in registry")
                continue
            node = pipeline.nodes[module_name]
            for dep in node.dependencies:
                if dep not in pipeline.nodes:
                    errors.append(
                        f"Module '{module_name}' depends on '{dep}' which is not registered"
                    )
        try:
            test_order = pipeline.topological_sort(modules)
            if len(test_order) != len(modules):
                errors.append("Circular dependency detected in module graph")
        except ValueError:
            errors.append("Circular dependency detected in module graph")
        except Exception as e:
            errors.append(f"Circular dependency check failed: {e}")
        return len(errors) == 0, errors

    def preflight_check(
        self, pipeline: Any, selected_modules: List[str]
    ) -> Dict[str, Any]:
        results = {
            "all_importable": True,
            "missing_dependencies": [],
            "skipped_modules": [],
            "warnings": [],
        }
        for name in selected_modules:
            if name not in pipeline.nodes:
                results["skipped_modules"].append(name)
                results["warnings"].append(f"Module '{name}' not in registry")
        try:
            all_modules = self.resolve_dependencies(pipeline, selected_modules)
        except Exception as e:
            results["all_importable"] = False
            results["warnings"].append(f"Failed to resolve dependencies: {e}")
            return results
        for module_name in all_modules:
            if module_name not in pipeline.nodes:
                results["skipped_modules"].append(module_name)
                results["warnings"].append(f"Module '{module_name}' not in registry")
                continue
            node = pipeline.nodes[module_name]
            try:
                func = node.function
                if func is None:
                    results["missing_dependencies"].append(module_name)
                    results["warnings"].append(
                        f"Module '{module_name}' function is None"
                    )
            except ImportError as e:
                results["missing_dependencies"].append(module_name)
                results["warnings"].append(f"Module '{module_name}' import failed: {e}")
            except Exception as e:
                results["warnings"].append(f"Module '{module_name}' check failed: {e}")
        results["all_importable"] = len(results["missing_dependencies"]) == 0
        return results

    def get_dependency_graph(
        self, pipeline: Any, selected_modules: List[str]
    ) -> Dict[str, List[str]]:
        execution_order = self.resolve_dependencies(pipeline, selected_modules)
        graph: Dict[str, List[str]] = {}
        for module_name in execution_order:
            if module_name in pipeline.nodes:
                graph[module_name] = pipeline.nodes[module_name].dependencies.copy()
        return graph

    def compute_review_before_run(
        self,
        pipeline: Any,
        *,
        transcript_path: str,
        selected_modules: List[str],
        output_dir: str,
        requirements_resolver: Optional[Any] = None,
        speaker_options: Optional[Any] = None,
        transcript_key: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        from transcriptx.core.pipeline.dag_pipeline_planning import (
            compute_review_before_run_for_pipeline,
        )

        return compute_review_before_run_for_pipeline(
            pipeline,
            transcript_path=transcript_path,
            selected_modules=selected_modules,
            output_dir=output_dir,
            requirements_resolver=requirements_resolver,
            speaker_options=speaker_options,
            transcript_key=transcript_key,
            run_id=run_id,
        )

    def _make_deterministic(self, modules: List[str]) -> List[str]:
        return sorted(modules)
