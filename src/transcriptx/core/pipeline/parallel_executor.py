"""
Parallel execution of analysis modules with dependency awareness.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Set
from transcriptx.core.pipeline.dag_pipeline import DAGPipeline, DAGNode
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


class ParallelExecutor:
    """
    Execute analysis modules in parallel while respecting dependencies.
    """

    def __init__(self, max_workers: int = 4):
        """
        Initialize parallel executor.

        Args:
            max_workers: Maximum number of parallel workers
        """
        self.max_workers = max_workers

    def execute_parallel(
        self,
        dag: DAGPipeline,
        transcript_path: str,
        selected_modules: List[str],
        speaker_map: Dict[str, str] = None,
        skip_speaker_mapping: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute modules in parallel where dependencies allow.

        Args:
            dag: DAG pipeline instance
            transcript_path: Path to transcript
            selected_modules: Modules to execute
            speaker_map: Speaker mapping
            skip_speaker_mapping: Skip speaker mapping

        Returns:
            Execution results
        """
        # Resolve dependencies and get execution order
        execution_order = dag.resolve_dependencies(selected_modules)

        import time

        results = {
            "transcript_path": transcript_path,
            "modules_requested": selected_modules,
            "modules_run": [],
            "errors": [],
            "execution_order": execution_order,
            "start_time": time.time(),
        }

        # Track executed modules
        executed_modules: Set[str] = set()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Execute modules level by level (respecting dependencies)
            remaining_modules = set(execution_order)

            while remaining_modules:
                # Find modules ready to execute (dependencies satisfied)
                ready_modules = [
                    mod
                    for mod in remaining_modules
                    if self._can_execute(dag, mod, executed_modules)
                ]

                if not ready_modules:
                    # No modules ready, check for circular dependencies
                    logger.warning(
                        "No modules ready to execute, possible circular dependency"
                    )
                    # Add remaining modules to errors
                    for mod in remaining_modules:
                        results["errors"].append(f"{mod}: Dependencies not satisfied")
                    break

                # Execute ready modules in parallel
                futures = {}
                for module_name in ready_modules:
                    if module_name not in dag.nodes:
                        logger.warning(f"Unknown module: {module_name}")
                        remaining_modules.remove(module_name)
                        continue

                    node = dag.nodes[module_name]
                    future = executor.submit(
                        self._execute_module, node, transcript_path
                    )
                    futures[future] = module_name

                # Collect results
                for future in as_completed(futures):
                    module_name = futures[future]
                    try:
                        future.result()  # Wait for completion
                        executed_modules.add(module_name)
                        results["modules_run"].append(module_name)
                        remaining_modules.remove(module_name)
                    except Exception as e:
                        error_msg = f"Error in {module_name}: {str(e)}"
                        results["errors"].append(error_msg)
                        if module_name in dag.nodes:
                            dag.nodes[module_name].error = str(e)
                        remaining_modules.remove(module_name)

        # Add execution metadata
        import time

        results["end_time"] = time.time()
        results["duration"] = results["end_time"] - results.get(
            "start_time", results["end_time"]
        )

        return results

    def _can_execute(
        self, dag: DAGPipeline, module_name: str, executed: Set[str]
    ) -> bool:
        """Check if module can execute (dependencies satisfied)."""
        if module_name not in dag.nodes:
            return False

        node = dag.nodes[module_name]
        return all(dep in executed for dep in node.dependencies)

    def _execute_module(self, node: DAGNode, transcript_path: str) -> None:
        """Execute a single module."""
        from transcriptx.core.utils.logger import (
            log_analysis_start,
            log_analysis_complete,
            log_analysis_error,
        )
        from transcriptx.core.utils.notifications import notify_user

        try:
            logger.info(f"Running {node.name} analysis (parallel)")
            notify_user(
                f"🔍 Running {node.description}...", technical=False, section=node.name
            )
            log_analysis_start(node.name, transcript_path)

            node.function(transcript_path)
            node.executed = True

            notify_user(
                f"✅ Completed {node.description}", technical=False, section=node.name
            )
            log_analysis_complete(node.name, transcript_path)
        except Exception as e:
            node.error = str(e)
            error_msg = f"Error in {node.name} analysis: {str(e)}"
            logger.error(error_msg)
            notify_user(
                f"❌ Failed {node.description}: {str(e)}",
                technical=True,
                section=node.name,
            )
            log_analysis_error(node.name, transcript_path, e)
            raise
