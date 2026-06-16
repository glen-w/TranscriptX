"""
Lightweight DAG-based pipeline for TranscriptX.

This module provides a simple, effective DAG implementation for managing
module dependencies without the overhead of complex workflow engines like Prefect.
It's designed for standard CPU setups and handles dependencies automatically.
"""

import time
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.validation import (
    validate_transcript_file,
    validate_output_directory,
)
from transcriptx.core.pipeline.dag_pipeline_execution import (
    run_sequential_execution_phase,
)
from transcriptx.core.pipeline.dag_pipeline_engine import execute_pipeline_runtime
from transcriptx.core.pipeline.dag_pipeline_run import (
    build_execute_pipeline_context,
    resolve_output_dir_for_run,
)
from transcriptx.core.utils.config_provider import get_config
from transcriptx.core.pipeline.contracts import RegistryModuleSnapshot, RegistrySnapshot
from transcriptx.core.pipeline.dag_planner import DAGPlanner
from transcriptx.core.pipeline.dag_executor import DAGExecutor, ExecutorState
from transcriptx.core.pipeline.contracts import ModuleOutcome
from transcriptx.core.pipeline.ports import CallbackEventSink
from transcriptx.core.pipeline.run_options import SpeakerRunOptions
from transcriptx.core.pipeline.dag_pipeline_types import ModuleExecOutcome
from transcriptx.core.pipeline.dag_pipeline_errors import PipelineSetupError
from transcriptx.core.pipeline.dag_legacy_compat import DAGLegacyCompatHelpers
from transcriptx.core.pipeline.dag_registry import (
    DAGNode,
    DAGRegistry,
)
from transcriptx.core.pipeline.module_registry import get_module_registry
from transcriptx.core.pipeline.dag_execution_adapter import (
    apply_module_side_effects as apply_module_side_effects_compat,
    execute_single_module as execute_single_module_compat,
)

# Note: load_or_create_speaker_map is imported lazily inside functions to avoid circular dependency


# Backward-compatible no-op hooks kept for legacy tests/patches.
def notify_user(*_args: Any, **_kwargs: Any) -> None:
    return None


def log_analysis_complete(*_args: Any, **_kwargs: Any) -> None:
    return None


def log_analysis_error(*_args: Any, **_kwargs: Any) -> None:
    return None


class DAGPipeline:
    PipelineSetupError = PipelineSetupError
    """
    Lightweight DAG-based analysis pipeline.

    This class manages module dependencies using a proper DAG structure,
    automatically resolving dependencies and executing modules in the correct order.

    The pipeline now supports:
    - Explicit module registration
    - Deterministic execution ordering
    - Preflight dependency checks
    - Planner-based deterministic execution plans
    - Read-only context for parallel execution
    """

    def __init__(
        self,
        *,
        registry: Optional[DAGRegistry] = None,
        planner: Optional[DAGPlanner] = None,
        engine: Optional[Callable[..., Dict[str, Any]]] = None,
        compat_helpers: Optional[DAGLegacyCompatHelpers] = None,
    ):
        """Initialize the DAG pipeline."""
        self.logger = get_logger()
        self._registry = registry or DAGRegistry(nodes={})
        self.nodes: Dict[str, DAGNode] = self._registry.nodes
        self.execution_order: List[str] = []
        self.results: Dict[str, Any] = {}
        self.errors: List[str] = []
        self._finalized: bool = False  # Track if registry is finalized
        self.module_progress_log_interval_seconds: float = max(
            float(
                getattr(
                    get_config().analysis,
                    "module_progress_log_interval_seconds",
                    60.0,
                )
            ),
            1.0,
        )
        self._planner = planner or DAGPlanner()
        self._engine = engine or execute_pipeline_runtime
        self._executor = DAGExecutor()
        self._compat_helpers = compat_helpers or DAGLegacyCompatHelpers()

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
        self._registry.add_module(
            name=name,
            description=description,
            category=category,
            dependencies=dependencies,
            function=function,
            timeout_seconds=timeout_seconds,
            requirements=requirements,
            enhancements=enhancements,
        )

    def resolve_dependencies(self, selected_modules: List[str]) -> List[str]:
        """
        Resolve dependencies and return execution order.

        Args:
            selected_modules: List of modules to run

        Returns:
            List of modules in execution order with dependencies included
        """
        return self._compat_helpers.resolve_dependencies(self, selected_modules)

    def check_implicit_dependencies(self, module_name: str) -> List[str]:
        return self._planner.check_implicit_dependencies(module_name)

    def topological_sort(self, modules: List[str]) -> List[str]:
        return self._planner.topological_sort(modules, self._registry_snapshot())

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
        return self._compat_helpers.validate_dependencies(self, modules)

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
        return self._compat_helpers.preflight_check(self, selected_modules)

    def _plan_execution(self, selected_modules: List[str]):
        return self._planner.plan(selected_modules, self._registry_snapshot())

    def get_execution_plan(self, selected_modules: List[str]):
        return self._plan_execution(selected_modules)

    def _create_execution_plan(
        self,
        requested_modules: List[str],
        execution_order: List[str],
        preflight: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Backward-compatible execution plan payload for regression tests/logging.
        """
        return {
            "requested_modules": list(requested_modules),
            "execution_order": list(execution_order),
            "dependency_graph": self.get_dependency_graph(requested_modules),
            "preflight": dict(preflight),
        }

    def compute_review_before_run(
        self,
        transcript_path: str,
        selected_modules: List[str],
        output_dir: str,
        requirements_resolver: Optional[Any] = None,
        speaker_options: Optional[Any] = None,
        transcript_key: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._compat_helpers.compute_review_before_run(
            self,
            transcript_path=transcript_path,
            selected_modules=selected_modules,
            output_dir=output_dir,
            requirements_resolver=requirements_resolver,
            speaker_options=speaker_options,
            transcript_key=transcript_key,
            run_id=run_id,
        )

    def sort_by_category(self, modules: List[str]) -> List[str]:
        return self._planner.sort_by_category(modules, self._registry_snapshot())

    def _pipeline_emit(
        self,
        event_collector: Optional[List[Dict[str, Any]]],
        on_event: Optional[Any],
        event_dict: Dict[str, Any],
    ) -> None:
        sink = CallbackEventSink(on_event=on_event, event_collector=event_collector)
        sink.emit(event_dict)

    def _registry_snapshot(self) -> RegistrySnapshot:
        return RegistrySnapshot(
            modules={
                name: RegistryModuleSnapshot(
                    name=name,
                    dependencies=list(node.dependencies),
                    category=node.category,
                )
                for name, node in sorted(self.nodes.items())
            }
        )

    def _new_pipeline_results(
        self, transcript_path: str, selected_modules: List[str]
    ) -> Dict[str, Any]:
        return {
            "transcript_path": transcript_path,
            "modules_requested": selected_modules,
            "selected_modules": selected_modules,
            "modules_run": [],
            "skipped_modules": [],
            "errors": [],
            "start_time": time.time(),
            "execution_order": [],
            "cache_hits": [],
            "module_results": {},
        }

    def _new_executor_state(self, results: Dict[str, Any]) -> ExecutorState:
        return ExecutorState(
            module_results=results["module_results"],
            modules_run=results["modules_run"],
            skipped_modules=results["skipped_modules"],
            errors=results["errors"],
            cache_hits=results["cache_hits"],
        )

    def _validate_pipeline_io(
        self, transcript_path: str, output_dir: str, results: Dict[str, Any]
    ) -> bool:
        try:
            validate_transcript_file(transcript_path)
            validate_output_directory(output_dir, create_if_missing=True)
            return True
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            results["errors"].append(str(e))
            results["status"] = "failed"
            results["end_time"] = time.time()
            results["duration"] = results["end_time"] - results["start_time"]
            return False

    def _run_sequential_execution_phase(
        self,
        *,
        execution_order: List[str],
        results: Dict[str, Any],
        context: Any,
        transcript_path: str,
        run_report: Optional[Any],
        requirements_resolver: Optional[Any],
        named_speaker_count_ref: List[Optional[int]],
        emit: Callable[[Dict[str, Any]], None],
    ) -> Tuple[bool, int, int, int, int]:
        """Execute modules in order. Mutates results and named_speaker_count_ref[0]."""
        return run_sequential_execution_phase(
            self,
            execution_order=execution_order,
            results=results,
            context=context,
            transcript_path=transcript_path,
            run_report=run_report,
            requirements_resolver=requirements_resolver,
            named_speaker_count_ref=named_speaker_count_ref,
            emit=emit,
        )

    def execute_pipeline(
        self,
        transcript_path: str,
        selected_modules: List[str],
        speaker_options: "SpeakerRunOptions | None" = None,
        output_dir: Optional[str] = None,
        transcript_key: Optional[str] = None,
        run_id: Optional[str] = None,
        run_report: Optional[Any] = None,
        requirements_resolver: Optional[Any] = None,
        event_collector: Optional[List[Dict[str, Any]]] = None,
        on_event: Optional[Any] = None,
        context: Optional[Any] = None,
        named_speaker_count: Optional[int] = None,
        execution_plan: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Execute the analysis pipeline using DAG dependency resolution.

        Args:
            transcript_path: Path to transcript file
            selected_modules: List of modules to run
            event_collector: Optional list that receives structured event dicts (legacy).
            on_event: Optional callable(event_dict) invoked synchronously on each
                event. Receives the same structured dict that goes into
                event_collector.  Best-effort — exceptions are swallowed.

        Returns:
            Dictionary with execution results
        """
        resolved_speaker_options = speaker_options or SpeakerRunOptions()
        owned_context = False
        runtime_context = context
        runtime_named_speaker_count = named_speaker_count

        # Backward compatibility: direct DAG callers may not inject context.
        # New orchestrator paths still provide context explicitly.
        if runtime_context is None:
            runtime_context, runtime_named_speaker_count = (
                build_execute_pipeline_context(
                    self.logger,
                    transcript_path=transcript_path,
                    speaker_options=resolved_speaker_options,
                    output_dir=resolve_output_dir_for_run(transcript_path, output_dir),
                    transcript_key=transcript_key,
                    run_id=run_id,
                )
            )
            owned_context = True

        try:
            return self._engine(
                self,
                transcript_path=transcript_path,
                selected_modules=selected_modules,
                speaker_options=resolved_speaker_options,
                output_dir=output_dir,
                transcript_key=transcript_key,
                run_id=run_id,
                run_report=run_report,
                requirements_resolver=requirements_resolver,
                event_collector=event_collector,
                on_event=on_event,
                context=runtime_context,
                named_speaker_count=runtime_named_speaker_count,
                execution_plan=execution_plan,
            )
        finally:
            if owned_context and runtime_context is not None:
                try:
                    runtime_context.close()
                except Exception:
                    pass

    def _should_abort_pipeline(
        self, outcome: ModuleExecOutcome, results: Dict[str, Any]
    ) -> bool:
        """Centralizes critical-error / stop logic. No side effects."""
        if outcome.status != "failed" or not outcome.error:
            return False
        error_str = outcome.error.lower()
        critical_keywords = [
            "speaker map",
            "speaker mapping",
            "no speaker map",
            "speaker mapping required",
            "speaker identification",
        ]
        if any(kw in error_str for kw in critical_keywords):
            self.logger.error(
                "Critical error: Speaker mapping required. Stopping pipeline."
            )
            results["status"] = "failed"
            return True
        return False

    def _reduce_module_outcome(
        self,
        module_name: str,
        outcome: ModuleExecOutcome,
        results: Dict[str, Any],
    ) -> None:
        state = ExecutorState(
            module_results=results["module_results"],
            modules_run=results["modules_run"],
            skipped_modules=results["skipped_modules"],
            errors=results["errors"],
            cache_hits=results["cache_hits"],
        )
        status = "failed"
        if outcome.status == "success":
            status = "succeeded"
        elif outcome.status == "skipped":
            status = "skipped"
        module_outcome = ModuleOutcome(
            module=module_name,
            status=status,  # type: ignore[arg-type]
            reason=outcome.skip_reason or outcome.error,
            duration_ms=outcome.duration_ms,
        )
        self._executor.reduce_outcome(
            state,
            module_name,
            module_outcome,
            module_result=outcome.module_result,
        )

    def _apply_module_side_effects(
        self,
        module_name: str,
        node: DAGNode,
        outcome: ModuleExecOutcome,
        transcript_path: str,
        run_report: Optional[Any],
    ) -> None:
        apply_module_side_effects_compat(
            self,
            module_name=module_name,
            node=node,
            outcome=outcome,
            transcript_path=transcript_path,
            run_report=run_report,
        )

    def _execute_single_module(
        self,
        module_name: str,
        node: DAGNode,
        transcript_path: str,
        context: Optional[Any],
        run_report: Optional[Any],
        requirements_resolver: Optional[Any],
        named_speaker_count: Optional[int],
    ) -> ModuleExecOutcome:
        return execute_single_module_compat(
            self,
            module_name=module_name,
            node=node,
            transcript_path=transcript_path,
            context=context,
            requirements_resolver=requirements_resolver,
            named_speaker_count=named_speaker_count,
        )

    def _module_progress_heartbeat(
        self, module_name: str, module_start: float, stop_event: threading.Event
    ) -> None:
        interval = max(float(self.module_progress_log_interval_seconds), 1.0)
        while not stop_event.wait(interval):
            elapsed_seconds = time.time() - module_start
            self.logger.info(
                f"{module_name} still running... {elapsed_seconds:.1f}s elapsed"
            )

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
        return self._compat_helpers.get_dependency_graph(self, selected_modules)


def create_dag_pipeline() -> DAGPipeline:
    module_registry = get_module_registry()
    registry = DAGRegistry(nodes={})
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
    return DAGPipeline(registry=registry)


def run_dag_pipeline(
    transcript_path: str,
    selected_modules: List[str],
    speaker_options: "SpeakerRunOptions | None" = None,
) -> Dict[str, Any]:
    dag = create_dag_pipeline()
    resolved_speaker_options = speaker_options or SpeakerRunOptions()
    context = None
    try:
        context, named_speaker_count = build_execute_pipeline_context(
            dag.logger,
            transcript_path=transcript_path,
            speaker_options=resolved_speaker_options,
            output_dir=resolve_output_dir_for_run(transcript_path, None),
            transcript_key=None,
            run_id=None,
        )
        return dag.execute_pipeline(
            transcript_path=transcript_path,
            selected_modules=selected_modules,
            speaker_options=resolved_speaker_options,
            context=context,
            named_speaker_count=named_speaker_count,
        )
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
