"""
Lightweight DAG-based pipeline for TranscriptX.

This module provides a simple, effective DAG implementation for managing
module dependencies without the overhead of complex workflow engines like Prefect.
It's designed for standard CPU setups and handles dependencies automatically.
"""

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.utils.logger import (
    get_logger,
    log_analysis_complete,
    log_analysis_error,
    log_analysis_start,
)
from transcriptx.core.utils.validation import (
    validate_transcript_file,
    validate_output_directory,
)
from transcriptx.core.utils.notifications import notify_user
from transcriptx.core.utils.performance_logger import TimedJob
from transcriptx.core.utils.performance_estimator import (
    PerformanceEstimator,
    format_time_estimate,
)
from transcriptx.core.pipeline.pipeline_context import PipelineContext, ReadOnlyPipelineContext


def get_module_registry():
    from transcriptx.core.pipeline.module_registry import ModuleRegistry

    return ModuleRegistry()

# Note: load_or_create_speaker_map is imported lazily inside functions to avoid circular dependency


@dataclass
class DAGNode:
    """Represents a module in the DAG."""

    name: str
    description: str
    category: str  # light, medium, heavy
    dependencies: List[str]
    function: Any  # The actual module function
    timeout_seconds: int = 600
    requirements: List[Any] = None
    enhancements: List[Any] = None
    executed: bool = False
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class DAGPipeline:
    """
    Lightweight DAG-based analysis pipeline.

    This class manages module dependencies using a proper DAG structure,
    automatically resolving dependencies and executing modules in the correct order.

    The pipeline now supports:
    - Explicit module registration
    - Deterministic execution ordering
    - Preflight dependency checks
    - Execution plan logging
    - Read-only context for parallel execution
    """

    def __init__(self):
        """Initialize the DAG pipeline."""
        self.logger = get_logger()
        self.nodes: Dict[str, DAGNode] = {}
        self.execution_order: List[str] = []
        self.results: Dict[str, Any] = {}
        self.errors: List[str] = []
        self._finalized: bool = False  # Track if registry is finalized

    def add_module(
        self,
        name: str,
        description: str,
        category: str,
        dependencies: List[str],
        function: Any,
        timeout_seconds: int = 600,
        requirements: Optional[List[Any]] = None,
        enhancements: Optional[List[Any]] = None,
    ):
        """Add a module to the DAG."""
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

    def resolve_dependencies(self, selected_modules: List[str]) -> List[str]:
        """
        Resolve dependencies and return execution order.

        Args:
            selected_modules: List of modules to run

        Returns:
            List of modules in execution order with dependencies included
        """
        # Add all dependencies for selected modules (recursively)
        modules_to_run = {module for module in selected_modules if module in self.nodes}
        modules_to_process = set(modules_to_run)

        # Recursively resolve all transitive dependencies
        while modules_to_process:
            new_modules = set()
            for module_name in modules_to_process:
                if module_name in self.nodes:
                    node = self.nodes[module_name]
                    # Add explicit dependencies
                    for dep in node.dependencies:
                        if dep in self.nodes and dep not in modules_to_run:
                            modules_to_run.add(dep)
                            new_modules.add(dep)
                    # Add implicit dependencies
                    implicit_deps = self._check_implicit_dependencies(module_name)
                    for dep in implicit_deps:
                        if dep in self.nodes and dep not in modules_to_run:
                            modules_to_run.add(dep)
                            new_modules.add(dep)
            modules_to_process = new_modules

        # Build execution order using topological sort
        execution_order = self._topological_sort(list(modules_to_run))

        # Ensure deterministic ordering (sort by name when dependencies are equal)
        execution_order = self._make_deterministic(execution_order)

        # Sort by category within dependency constraints
        execution_order = self._sort_by_category(execution_order)

        return execution_order

    def _check_implicit_dependencies(self, module_name: str) -> List[str]:
        """Check for implicit dependencies based on module requirements."""
        implicit_deps = []

        # Known implicit dependencies
        if module_name == "contagion":
            # Contagion needs emotion data
            implicit_deps.append("emotion")
        elif module_name == "stats":
            # Stats aggregates data from other modules, but doesn't strictly depend on them
            # It can run with partial data
            pass

        return implicit_deps

    def _topological_sort(self, modules: List[str]) -> List[str]:
        """
        Perform topological sort to determine execution order.

        Args:
            modules: List of module names to sort

        Returns:
            List of modules in dependency order
        """
        # Build adjacency list
        graph = defaultdict(list)
        in_degree = defaultdict(int)

        for module_name in modules:
            if module_name in self.nodes:
                node = self.nodes[module_name]
                in_degree[module_name] = len(node.dependencies)

                for dep in node.dependencies:
                    if dep in modules:
                        graph[dep].append(module_name)

        # Topological sort using Kahn's algorithm
        queue = deque([module for module in modules if in_degree[module] == 0])
        result = []

        while queue:
            current = queue.popleft()
            result.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(result) != len(modules):
            cycle_msg = "Circular dependency detected in modules"
            self.logger.error(cycle_msg)
            raise ValueError(cycle_msg)

        return result

    def _make_deterministic(self, modules: List[str]) -> List[str]:
        """
        Ensure deterministic ordering by sorting modules with equal dependencies.

        Args:
            modules: List of modules in dependency order

        Returns:
            List with deterministic ordering (sorted by name when dependencies equal)
        """
        # For modules with the same dependency level, sort by name
        # This ensures consistent ordering across runs
        return sorted(modules)

    def validate_dependencies(
        self, modules: Optional[List[str]] = None
    ) -> tuple[bool, List[str]]:
        """
        Validate that all declared dependencies exist and there are no circular dependencies.

        Args:
            modules: List of modules to validate (default: all registered modules)

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        if modules is None:
            modules = list(self.nodes.keys())

        # Check all dependencies exist
        for module_name in modules:
            if module_name not in self.nodes:
                errors.append(f"Module '{module_name}' not found in registry")
                continue

            node = self.nodes[module_name]
            for dep in node.dependencies:
                if dep not in self.nodes:
                    errors.append(
                        f"Module '{module_name}' depends on '{dep}' which is not registered"
                    )

        # Check for circular dependencies
        try:
            # Try topological sort - if it fails, there's a cycle
            test_order = self._topological_sort(modules)
            if len(test_order) != len(modules):
                errors.append("Circular dependency detected in module graph")
        except ValueError:
            errors.append("Circular dependency detected in module graph")
        except Exception as e:
            errors.append(f"Circular dependency check failed: {e}")

        return len(errors) == 0, errors

    def finalize(self) -> None:
        """
        Finalize the module registry.

        This method validates all modules are registered, checks for circular dependencies,
        and locks the registry to prevent further modifications.

        Should be called before pipeline execution.
        """
        if self._finalized:
            self.logger.warning("Registry already finalized")
            return

        # Validate dependencies
        is_valid, errors = self.validate_dependencies()
        if not is_valid:
            error_msg = "Module registry validation failed:\n" + "\n".join(errors)
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        self._finalized = True
        self.logger.info("Module registry finalized and locked")

    def preflight_check(self, selected_modules: List[str]) -> Dict[str, Any]:
        """
        Perform preflight checks before pipeline execution.

        Checks:
        - All modules can be imported
        - All dependencies are available
        - Missing optional dependencies are reported

        Args:
            selected_modules: List of modules to check

        Returns:
            Dictionary with check results
        """
        results = {
            "all_importable": True,
            "missing_dependencies": [],
            "skipped_modules": [],
            "warnings": [],
        }

        # Resolve all modules including dependencies
        try:
            all_modules = self.resolve_dependencies(selected_modules)
        except Exception as e:
            results["all_importable"] = False
            results["warnings"].append(f"Failed to resolve dependencies: {e}")
            return results

        # Check each module can be imported
        for module_name in all_modules:
            if module_name not in self.nodes:
                results["skipped_modules"].append(module_name)
                results["warnings"].append(f"Module '{module_name}' not in registry")
                continue

            node = self.nodes[module_name]
            try:
                # Try to get the module function (this will import it)
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

    def _create_execution_plan(
        self,
        requested_modules: List[str],
        execution_order: List[str],
        preflight: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create execution plan for logging and reproducibility.

        Args:
            requested_modules: Modules requested by user
            execution_order: Resolved execution order with dependencies
            preflight: Preflight check results

        Returns:
            Dictionary with execution plan details
        """
        # Build dependency graph visualization
        dependency_graph = {}
        for module_name in execution_order:
            if module_name in self.nodes:
                node = self.nodes[module_name]
                dependency_graph[module_name] = {
                    "dependencies": node.dependencies,
                    "category": node.category,
                    "included_reason": (
                        "requested"
                        if module_name in requested_modules
                        else f"dependency of {self._find_requester(module_name, requested_modules)}"
                    ),
                }

        # Determine which modules were added as dependencies
        explicit_deps = set()
        for module_name in requested_modules:
            if module_name in self.nodes:
                explicit_deps.update(self.nodes[module_name].dependencies)

        return {
            "requested_modules": requested_modules,
            "resolved_modules": execution_order,
            "execution_order": execution_order,
            "dependency_graph": dependency_graph,
            "modules_added_as_dependencies": list(explicit_deps),
            "skipped_modules": preflight.get("skipped_modules", []),
            "missing_dependencies": preflight.get("missing_dependencies", []),
            "warnings": preflight.get("warnings", []),
        }

    def _find_requester(
        self, module_name: str, requested_modules: List[str]
    ) -> Optional[str]:
        """Find which requested module requires this dependency."""
        for req_module in requested_modules:
            if req_module in self.nodes:
                if module_name in self.nodes[req_module].dependencies:
                    return req_module
        return None

    def _log_execution_plan(self, plan: Dict[str, Any], output_dir: str) -> None:
        """
        Log execution plan to file and console.

        Args:
            plan: Execution plan dictionary
            output_dir: Output directory for this run
        """
        try:
            manifest_dir = Path(output_dir) / ".transcriptx"
            manifest_dir.mkdir(parents=True, exist_ok=True)

            # Save execution plan
            from transcriptx.core.utils.artifact_writer import write_json

            plan_path = manifest_dir / "execution_plan.json"
            write_json(plan_path, plan, indent=2, ensure_ascii=False)

            self.logger.info(f"Execution plan saved to {plan_path}")

            # Log summary to console
            self.logger.info(
                f"Execution plan: {len(plan['requested_modules'])} requested, "
                f"{len(plan['resolved_modules'])} total (including {len(plan['modules_added_as_dependencies'])} dependencies)"
            )
        except Exception as e:
            self.logger.warning(f"Failed to log execution plan: {e}")

    def _sort_by_category(self, modules: List[str]) -> List[str]:
        """
        Sort modules by category (light -> medium -> heavy) while preserving dependencies.

        This method maintains the topological order from dependencies while preferring
        to execute lighter modules first when dependencies allow.

        Args:
            modules: List of modules in dependency order

        Returns:
            List of modules sorted by category within dependency constraints
        """
        category_order = {"light": 0, "medium": 1, "heavy": 2}

        # Build dependency graph for reference (only consider dependencies in modules list)
        modules_set = set(modules)
        dep_graph = {}
        for module_name in modules:
            if module_name in self.nodes:
                node = self.nodes[module_name]
                # Only track dependencies that are in the modules list
                dep_graph[module_name] = set(dep for dep in node.dependencies if dep in modules_set)

        # Stable sort: maintain topological order, but prefer category ordering
        # when dependencies are satisfied
        result = []
        remaining = set(modules)
        executed: set[str] = set()

        while remaining:
            # Find modules ready to execute (all dependencies satisfied)
            ready = [
                mod for mod in remaining
                if mod in self.nodes and dep_graph.get(mod, set()).issubset(executed)
            ]

            if not ready:
                # No modules ready - this shouldn't happen if topological sort worked
                # but handle gracefully by adding remaining modules in order
                result.extend([m for m in modules if m in remaining])
                break

            # Sort ready modules by category, then by name for determinism
            ready_sorted = sorted(
                ready,
                key=lambda m: (
                    category_order.get(self.nodes[m].category if m in self.nodes else "heavy", 2),
                    m
                )
            )

            # Add to result and mark as executed
            result.extend(ready_sorted)
            executed.update(ready_sorted)
            remaining -= set(ready_sorted)

        return result

    def execute_pipeline(
        self,
        transcript_path: str,
        selected_modules: List[str],
        speaker_map: Optional[Dict[str, str]] = None,
        skip_speaker_mapping: bool = False,
        speaker_options: "SpeakerRunOptions | None" = None,
        parallel: bool = False,
        max_workers: int = 4,
        db_coordinator: Optional[Any] = None,
        output_dir: Optional[str] = None,
        transcript_key: Optional[str] = None,
        run_id: Optional[str] = None,
        run_report: Optional[Any] = None,
        requirements_resolver: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Execute the analysis pipeline using DAG dependency resolution.

        Args:
            transcript_path: Path to transcript file
            selected_modules: List of modules to run
            skip_speaker_mapping: Skip speaker mapping if already done (deprecated, kept for compatibility)
            parallel: If True, execute modules in parallel where possible
            max_workers: Maximum parallel workers (if parallel=True)

        Returns:
            Dictionary with execution results
        """
        from transcriptx.core.pipeline.run_options import SpeakerRunOptions

        speaker_options = speaker_options or SpeakerRunOptions()
        self.logger.info(
            f"Starting DAG pipeline for {transcript_path} (parallel={parallel})"
        )

        if output_dir is None:
            from transcriptx.core.utils.path_utils import get_transcript_dir

            output_dir = get_transcript_dir(transcript_path)

        if parallel:
            self.logger.warning(
                "Parallel execution disabled; falling back to sequential execution"
            )
            parallel = False

        # Initialize results early to allow graceful validation failures
        results: Dict[str, Any] = {
            "transcript_path": transcript_path,
            "modules_requested": selected_modules,
            "selected_modules": selected_modules,  # Alias for compatibility
            "modules_run": [],
            "skipped_modules": [],
            "errors": [],
            "start_time": time.time(),
            "execution_order": [],
            "cache_hits": [],
            "module_results": {},
        }

        # Validate inputs
        try:
            validate_transcript_file(transcript_path)
            validate_output_directory(
                os.path.dirname(transcript_path), create_if_missing=True
            )
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            results["errors"].append(str(e))
            results["status"] = "failed"
            results["end_time"] = time.time()
            results["duration"] = results["end_time"] - results["start_time"]
            return results

        # Finalize registry if not already done
        if not self._finalized:
            try:
                self.finalize()
            except ValueError as e:
                self.logger.error(f"Registry finalization failed: {e}")
                # Continue anyway for backward compatibility

        # Perform preflight checks
        preflight = self.preflight_check(selected_modules)
        if preflight["warnings"]:
            for warning in preflight["warnings"]:
                self.logger.warning(f"Preflight warning: {warning}")

        if not preflight["all_importable"]:
            missing = ", ".join(preflight["missing_dependencies"])
            self.logger.error(
                f"Preflight check failed: modules cannot be imported: {missing}"
            )
            # Continue anyway - modules may have optional dependencies

        # Resolve dependencies and get execution order
        execution_order = self.resolve_dependencies(selected_modules)
        self.logger.info(f"Execution order: {', '.join(execution_order)}")

        # Create and log execution plan
        execution_plan = self._create_execution_plan(
            selected_modules, execution_order, preflight
        )
        self._log_execution_plan(execution_plan, output_dir)

        # Update execution order in results
        results["execution_order"] = execution_order

        # Create PipelineContext for efficient data passing
        # This loads transcript data once and caches it for all modules
        context = None
        try:
            from transcriptx.core.pipeline.pipeline_context import PipelineContext

            context = PipelineContext(
                transcript_path,
                speaker_map=speaker_map,
                skip_speaker_mapping=skip_speaker_mapping,
                include_unidentified_speakers=speaker_options.include_unidentified,
                anonymise_speakers=speaker_options.anonymise,
                batch_mode=True,
                use_db=bool(db_coordinator),
                output_dir=output_dir,
                transcript_key=transcript_key,
                run_id=run_id,
            )

            # Validate context
            if not context.validate():
                self.logger.warning(
                    "PipelineContext validation failed, falling back to legacy mode"
                )
                context.close()
                context = None
            else:
                self.logger.debug(
                    f"Created PipelineContext with {len(context.get_segments())} segments"
                )
        except Exception as e:
            self.logger.warning(
                f"Failed to create PipelineContext, falling back to legacy mode: {e}"
            )
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            context = None

        # Reuse mode: return existing results without re-running
        if db_coordinator and getattr(db_coordinator, "reused_pipeline_run", False):
            cached_modules = db_coordinator.get_cached_module_names()
            results["modules_run"] = cached_modules
            results["status"] = "reused"
            results["end_time"] = time.time()
            results["duration"] = results["end_time"] - results["start_time"]
            self.logger.info(
                f"Reused PipelineRun {db_coordinator.pipeline_run.id} with {len(cached_modules)} modules"
            )
            return results

        # Use parallel execution if requested
        if parallel:
            from transcriptx.core.pipeline.parallel_executor import ParallelExecutor

            executor = ParallelExecutor(max_workers=max_workers)
            parallel_results = executor.execute_parallel(
                self,
                transcript_path,
                selected_modules,
                speaker_map,
                skip_speaker_mapping,
            )
            # Merge parallel results
            results.update(parallel_results)
            self.logger.info(
                f"Parallel pipeline completed. Ran {len(results['modules_run'])} modules with {len(results['errors'])} errors"
            )

            # Clean up context
            if context:
                try:
                    context.close()
                except Exception as e:
                    self.logger.warning(f"Error closing PipelineContext: {e}")

            return results

        # Execute modules in order (sequential)
        for module_name in execution_order:
            if module_name not in self.nodes:
                self.logger.warning(f"Unknown module: {module_name}")
                continue

            node = self.nodes[module_name]

            # Check if dependencies are satisfied
            missing_deps = self._check_missing_dependencies(
                node, results["modules_run"]
            )
            if missing_deps:
                # Check if any missing dependencies themselves have missing dependencies
                dep_chain = []
                for dep in missing_deps:
                    if dep in self.nodes:
                        dep_node = self.nodes[dep]
                        missing_dep_deps = self._check_missing_dependencies(
                            dep_node, results["modules_run"]
                        )
                        if missing_dep_deps:
                            dep_chain.append(f"{dep} (which requires {missing_dep_deps})")
                        else:
                            dep_chain.append(dep)
                    else:
                        dep_chain.append(dep)
                
                error_msg = f"{module_name}: Missing dependencies {missing_deps}"
                if dep_chain != missing_deps:
                    error_msg += f" ({', '.join(dep_chain)})"
                
                self.logger.warning(
                    f"Module '{module_name}' missing dependencies: {missing_deps}"
                )
                results["errors"].append(error_msg)
                continue

            if requirements_resolver:
                should_skip, reasons = requirements_resolver.should_skip(
                    node.requirements
                )
                if should_skip:
                    reason_text = "; ".join(reasons)
                    results["skipped_modules"].append(
                        {"module": module_name, "reason": reason_text}
                    )
                    if run_report:
                        from transcriptx.core.utils.run_report import ModuleResult

                        run_report.record_module(
                            module_name=module_name,
                            status=ModuleResult.SKIP,
                            reason=reason_text,
                        )
                    continue

            # Execute module
            try:
                self.logger.info(f"Running {module_name} analysis")
                notify_user(
                    f"🔍 Running {node.description}...",
                    technical=False,
                    section=module_name,
                )
                log_analysis_start(module_name, transcript_path)

                # Get transcript metrics for logging and estimation
                transcript_segments_count = None
                transcript_word_count = None
                try:
                    from transcriptx.io import load_segments

                    segments = load_segments(transcript_path)
                    transcript_segments_count = len(segments)
                    transcript_word_count = sum(
                        len(seg.get("text", "").split()) for seg in segments
                    )
                except Exception:
                    pass

                # Show time estimate
                try:
                    estimator = PerformanceEstimator()
                    estimate = estimator.estimate_analysis_time(
                        module_name=module_name,
                        transcript_segments=transcript_segments_count,
                        transcript_words=transcript_word_count,
                    )
                    if estimate.get("estimated_seconds") is not None:
                        estimate_str = format_time_estimate(estimate)
                        self.logger.info(
                            f"Estimated {module_name} time: {estimate_str}"
                        )
                except Exception:
                    pass  # Don't fail if estimation fails

                # Determine module cache config
                module_run = None
                cached = False
                if db_coordinator:
                    from transcriptx.core.utils.module_cache_config import (
                        get_cache_affecting_config,
                    )
                    from transcriptx.core.utils.config import get_config

                    module_config = get_cache_affecting_config(
                        module_name, get_config()
                    )
                    module_run, cached = db_coordinator.begin_module_run(
                        module_name=module_name,
                        module_config=module_config,
                        dependency_names=node.dependencies,
                    )
                    if cached:
                        results["modules_run"].append(module_name)
                        results["cache_hits"].append(module_name)
                        if run_report:
                            from transcriptx.core.utils.run_report import ModuleResult

                            run_report.record_module(
                                module_name=module_name,
                                status=ModuleResult.RUN,
                                duration_seconds=0.0,
                                reason="cache_hit",
                            )
                        continue

                module_start = time.time()
                module_result = None
                from transcriptx.core.utils.module_result import (
                    build_module_result,
                    capture_exception,
                    now_iso,
                )

                module_started_at = now_iso()
                # Wrap module execution with performance logging
                file_name = Path(transcript_path).name
                pipeline_run_id = (
                    db_coordinator.pipeline_run.id
                    if db_coordinator and getattr(db_coordinator, "pipeline_run", None)
                    else None
                )
                transcript_file_id = (
                    db_coordinator.transcript_file.id
                    if db_coordinator
                    and getattr(db_coordinator, "transcript_file", None)
                    else None
                )
                module_run_id = module_run.id if module_run else None
                span_name = f"module.{module_name}.run"
                with TimedJob(
                    span_name,
                    file_name,
                    pipeline_run_id=pipeline_run_id,
                    module_run_id=module_run_id,
                    transcript_file_id=transcript_file_id,
                ) as job:
                    job.add_metadata(
                        {"module_name": module_name, "transcript_path": transcript_path}
                    )
                    if transcript_segments_count is not None:
                        job.add_metadata(
                            {"transcript_segments_count": transcript_segments_count}
                        )
                    if transcript_word_count is not None:
                        job.add_metadata(
                            {"transcript_word_count": transcript_word_count}
                        )

                    # Execute module function
                    # Try to use new interface (PipelineContext) if available
                    if context is not None:
                        # For parallel execution, use read-only context wrapper
                        from transcriptx.core.pipeline.pipeline_context import (
                            ReadOnlyPipelineContext,
                        )

                        if parallel:
                            # Freeze context and wrap in read-only wrapper for parallel execution
                            context.freeze()
                            read_only_context = ReadOnlyPipelineContext(context)
                            execution_context = read_only_context
                        else:
                            execution_context = context

                        # Check if function is an AnalysisModule class or instance
                        if isinstance(node.function, type) and hasattr(
                            node.function, "run_from_context"
                        ):
                            # It's an AnalysisModule class, instantiate it
                            module_instance = node.function()
                            module_result = module_instance.run_from_context(
                                execution_context
                            )
                            if module_result.get("status") == "error":
                                raise RuntimeError(
                                    module_result.get("error", "Unknown error")
                                )
                        elif hasattr(
                            type(node.function), "run_from_context"
                        ) and not isinstance(node.function, type):
                            # It's an AnalysisModule instance
                            module_result = node.function.run_from_context(
                                execution_context
                            )
                            if module_result.get("status") == "error":
                                raise RuntimeError(
                                    module_result.get("error", "Unknown error")
                                )
                        else:
                            # Fall back to legacy function call
                            node.function(transcript_path)
                    else:
                        # No context available, use legacy function call
                        node.function(transcript_path)

                module_duration = time.time() - module_start
                if module_result is None:
                    module_result = build_module_result(
                        module_name=module_name,
                        status="success",
                        started_at=module_started_at,
                        finished_at=now_iso(),
                        artifacts=[],
                        metrics={"duration_seconds": module_duration},
                        payload_type="analysis_results",
                        payload={},
                    )

                # Record module result payload for aggregation
                results["module_results"][module_name] = module_result

                # Mark as executed
                node.executed = True
                results["modules_run"].append(module_name)

                notify_user(
                    f"✅ Completed {node.description}",
                    technical=False,
                    section=module_name,
                )
                log_analysis_complete(module_name, transcript_path)

                if db_coordinator and module_run:
                    db_coordinator.complete_module_run(
                        module_run=module_run,
                        module_name=module_name,
                        duration_seconds=module_duration,
                        module_failed=False,
                        module_result=module_result,
                    )
                if run_report:
                    from transcriptx.core.utils.run_report import ModuleResult

                    run_report.record_module(
                        module_name=module_name,
                        status=ModuleResult.RUN,
                        duration_seconds=module_duration,
                    )

            except Exception as e:
                error_msg = f"Error in {module_name} analysis: {str(e)}"
                self.logger.error(error_msg)
                results["errors"].append(error_msg)
                node.error = str(e)
                notify_user(
                    f"❌ Failed {node.description}: {str(e)}",
                    technical=True,
                    section=module_name,
                )
                if run_report:
                    from transcriptx.core.utils.run_report import ModuleResult

                    run_report.record_module(
                        module_name=module_name,
                        status=ModuleResult.FAIL,
                        error=str(e),
                    )
                log_analysis_error(module_name, transcript_path, e)
                module_result = build_module_result(
                    module_name=module_name,
                    status="error",
                    started_at=(
                        module_started_at
                        if "module_started_at" in locals()
                        else now_iso()
                    ),
                    finished_at=now_iso(),
                    artifacts=[],
                    metrics=(
                        {"duration_seconds": time.time() - module_start}
                        if "module_start" in locals()
                        else {}
                    ),
                    payload_type="analysis_results",
                    payload={},
                    error=capture_exception(e),
                )
                results["module_results"][module_name] = module_result

                # Check if this is a critical error that should stop the pipeline
                error_str = str(e).lower()
                if any(
                    keyword in error_str
                    for keyword in [
                        "speaker map",
                        "speaker mapping",
                        "no speaker map",
                        "speaker mapping required",
                        "speaker identification",
                    ]
                ):
                    self.logger.error(
                        "Critical error: Speaker mapping required. Stopping pipeline."
                    )
                    results["status"] = "failed"
                    break

                if db_coordinator and module_run:
                    db_coordinator.complete_module_run(
                        module_run=module_run,
                        module_name=module_name,
                        duration_seconds=0.0,
                        module_failed=True,
                        module_result=module_result,
                    )

        # Add execution metadata
        results["end_time"] = time.time()
        results["duration"] = results["end_time"] - results["start_time"]

        # Ensure execution_order is always present (even if empty)
        if "execution_order" not in results:
            results["execution_order"] = execution_order

        self.logger.info(
            f"Pipeline completed. Ran {len(results['modules_run'])} modules with {len(results['errors'])} errors"
        )

        # Clean up context
        if context:
            try:
                context.close()
            except Exception as e:
                self.logger.warning(f"Error closing PipelineContext: {e}")

        return results

    def _check_missing_dependencies(
        self, node: DAGNode, executed_modules: List[str]
    ) -> List[str]:
        """Check which dependencies are missing for a module."""
        missing = []
        for dep in node.dependencies:
            if dep not in executed_modules:
                missing.append(dep)
        return missing

    def get_dependency_graph(self, selected_modules: List[str]) -> Dict[str, List[str]]:
        """
        Get the dependency graph for visualization or debugging.

        Args:
            selected_modules: List of modules to include

        Returns:
            Dictionary mapping modules to their dependencies
        """
        execution_order = self.resolve_dependencies(selected_modules)
        graph = {}

        for module_name in execution_order:
            if module_name in self.nodes:
                graph[module_name] = self.nodes[module_name].dependencies.copy()

        return graph


def create_dag_pipeline() -> DAGPipeline:
    """
    Create a DAG pipeline with all available modules.

    Returns:
        Configured DAG pipeline
    """
    dag = DAGPipeline()
    registry = get_module_registry()

    # Add all modules to the DAG
    for module_name in registry.get_available_modules():
        module_info = registry.get_module_info(module_name)
        module_function = registry.get_module_function(module_name)

        if module_info and module_function:
            dag.add_module(
                name=module_name,
                description=module_info.description,
                category=module_info.category,
                dependencies=module_info.dependencies,
                function=module_function,
                timeout_seconds=module_info.timeout_seconds,
                requirements=module_info.requirements,
                enhancements=module_info.enhancements,
            )

    return dag


def run_dag_pipeline(
    transcript_path: str,
    selected_modules: List[str],
    skip_speaker_mapping: bool = False,
    speaker_options: "SpeakerRunOptions | None" = None,
) -> Dict[str, Any]:
    """
    Convenience function to run the DAG pipeline.

    Note: Speaker information is extracted directly from segments.

    Args:
        transcript_path: Path to transcript file
        selected_modules: List of modules to run
        skip_speaker_mapping: Skip speaker mapping if already done (kept for compatibility)

    Returns:
        Pipeline execution results
    """
    dag = create_dag_pipeline()
    return dag.execute_pipeline(
        transcript_path=transcript_path,
        selected_modules=selected_modules,
        skip_speaker_mapping=skip_speaker_mapping,
        speaker_options=speaker_options,
    )
