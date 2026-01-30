"""
Test utilities for regression tests.

This module provides utility functions for regression testing,
including trace capture, CLI execution, output hashing, and
execution plan comparison.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.utils.path_resolver import (
    PathResolver,
    PathResolutionResult,
    ResolutionConfidence,
)


@dataclass
class ResolutionTrace:
    """Trace of path resolution attempt."""
    file_path: str
    file_type: str
    strategies_tried: List[str]
    candidates_found: Dict[str, List[str]]  # strategy -> [candidates]
    final_result: Optional[PathResolutionResult]
    execution_time_ms: float


def capture_resolution_trace(
    resolver: PathResolver,
    file_path: str,
    file_type: str = "transcript",
    validate_state: bool = True
) -> ResolutionTrace:
    """
    Capture full resolution trace for debugging.
    
    Args:
        resolver: PathResolver instance
        file_path: File path to resolve
        file_type: Type of file
        validate_state: Whether to validate state
        
    Returns:
        ResolutionTrace with full resolution details
    """
    start_time = time.time()
    strategies_tried = []
    candidates_found = {}
    
    # Try each strategy and capture results
    for strategy in resolver.strategies:
        strategy_name = strategy.name
        strategies_tried.append(strategy_name)
        
        try:
            result = strategy.resolve(file_path, file_type)
            if result and result.found:
                candidates_found[strategy_name] = [result.path]
            else:
                candidates_found[strategy_name] = []
        except Exception as e:
            candidates_found[strategy_name] = []
    
    # Get final result
    try:
        final_result = resolver.resolve_with_result(file_path, file_type, validate_state)
    except FileNotFoundError:
        final_result = None
    
    execution_time_ms = (time.time() - start_time) * 1000
    
    return ResolutionTrace(
        file_path=file_path,
        file_type=file_type,
        strategies_tried=strategies_tried,
        candidates_found=candidates_found,
        final_result=final_result,
        execution_time_ms=execution_time_ms
    )


def run_cli_with_capture(
    command: str,
    args: List[str],
    stdin=None,
    timeout: Optional[int] = None,
    env: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Run CLI command and capture stdout/stderr.
    
    Args:
        command: CLI command name
        args: Command arguments
        stdin: stdin input
        timeout: Timeout in seconds
        env: Environment variables
        
    Returns:
        Dict with returncode, stdout, stderr, success
    """
    import subprocess
    import os
    
    cmd = ["python", "-m", "transcriptx.cli.main", command] + args
    
    if env:
        full_env = os.environ.copy()
        full_env.update(env)
    else:
        full_env = None
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        stdin=stdin or subprocess.DEVNULL,
        timeout=timeout,
        env=full_env,
    )
    
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.returncode == 0,
    }


def hash_outputs(outputs: Dict[str, Any]) -> str:
    """
    Hash pipeline outputs for comparison.
    
    Args:
        outputs: Pipeline output dictionary
        
    Returns:
        SHA256 hash hexdigest
    """
    # Sort keys for deterministic hashing
    sorted_outputs = json.dumps(outputs, sort_keys=True, default=str)
    return hashlib.sha256(sorted_outputs.encode()).hexdigest()


def compare_execution_plans(plan1: Dict[str, Any], plan2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two execution plans for differences.
    
    Args:
        plan1: First execution plan
        plan2: Second execution plan
        
    Returns:
        Dict with differences found
    """
    differences = {
        "execution_order_diff": [],
        "dependency_graph_diff": {},
        "modules_added_diff": [],
        "warnings_diff": [],
    }
    
    # Compare execution order
    order1 = plan1.get("execution_order", [])
    order2 = plan2.get("execution_order", [])
    if order1 != order2:
        differences["execution_order_diff"] = {
            "plan1": order1,
            "plan2": order2,
        }
    
    # Compare dependency graphs
    graph1 = plan1.get("dependency_graph", {})
    graph2 = plan2.get("dependency_graph", {})
    
    all_modules = set(graph1.keys()) | set(graph2.keys())
    for module in all_modules:
        deps1 = graph1.get(module, {}).get("dependencies", [])
        deps2 = graph2.get(module, {}).get("dependencies", [])
        if deps1 != deps2:
            differences["dependency_graph_diff"][module] = {
                "plan1": deps1,
                "plan2": deps2,
            }
    
    # Compare modules added
    added1 = set(plan1.get("modules_added_as_dependencies", []))
    added2 = set(plan2.get("modules_added_as_dependencies", []))
    if added1 != added2:
        differences["modules_added_diff"] = {
            "plan1": list(added1),
            "plan2": list(added2),
        }
    
    # Compare warnings
    warnings1 = plan1.get("warnings", [])
    warnings2 = plan2.get("warnings", [])
    if warnings1 != warnings2:
        differences["warnings_diff"] = {
            "plan1": warnings1,
            "plan2": warnings2,
        }
    
    return differences


def save_resolution_trace_snapshot(trace: ResolutionTrace, snapshot_path: Path) -> None:
    """
    Save resolution trace as snapshot for golden test comparison.
    
    Args:
        trace: ResolutionTrace to save
        snapshot_path: Path to save snapshot
    """
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to dict for JSON serialization
    trace_dict = {
        "file_path": trace.file_path,
        "file_type": trace.file_type,
        "strategies_tried": trace.strategies_tried,
        "candidates_found": trace.candidates_found,
        "final_result": {
            "path": trace.final_result.path if trace.final_result else None,
            "confidence": (
                trace.final_result.confidence.value
                if trace.final_result and trace.final_result.confidence
                else None
            ),
            "strategy": trace.final_result.strategy if trace.final_result else None,
            "message": trace.final_result.message if trace.final_result else None,
        } if trace.final_result else None,
        "execution_time_ms": trace.execution_time_ms,
    }
    
    with open(snapshot_path, 'w') as f:
        json.dump(trace_dict, f, indent=2)


def load_resolution_trace_snapshot(snapshot_path: Path) -> Dict[str, Any]:
    """
    Load resolution trace snapshot.
    
    Args:
        snapshot_path: Path to snapshot file
        
    Returns:
        Dict with trace data
    """
    with open(snapshot_path, 'r') as f:
        return json.load(f)
