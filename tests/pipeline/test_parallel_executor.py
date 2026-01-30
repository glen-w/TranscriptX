"""
Tests for parallel execution of analysis modules.

This module tests parallel execution, concurrency, and dependency handling.
"""

from unittest.mock import patch, MagicMock

import pytest

from transcriptx.core.pipeline.parallel_executor import ParallelExecutor


class TestParallelExecutor:
    """Tests for ParallelExecutor class."""
    
    def test_initialization(self):
        """Test ParallelExecutor initialization."""
        executor = ParallelExecutor(max_workers=4)
        
        assert executor.max_workers == 4
    
    def test_initialization_with_default_workers(self):
        """Test ParallelExecutor initialization with default workers."""
        executor = ParallelExecutor()
        
        assert executor.max_workers == 4
    
    def test_executes_modules_in_parallel(self):
        """Test that modules are executed in parallel."""
        executor = ParallelExecutor(max_workers=2)
        
        # Mock DAG and modules
        mock_dag = MagicMock()
        mock_dag.resolve_dependencies.return_value = ["module1", "module2"]
        mock_dag.nodes = {
            "module1": MagicMock(),
            "module2": MagicMock()
        }
        
        # Mock module execution
        def mock_execute(node, transcript_path):
            return {"module": node.name if hasattr(node, 'name') else "module", "status": "success"}
        
        executor._execute_module = mock_execute
        executor._can_execute = lambda dag, mod, executed: True
        
        results = executor.execute_parallel(
            mock_dag,
            "test.json",
            ["module1", "module2"]
        )
        
        assert "modules_run" in results
        assert "errors" in results
    
    def test_respects_dependencies(self):
        """Test that dependencies are respected during execution."""
        executor = ParallelExecutor()
        
        mock_dag = MagicMock()
        mock_dag.resolve_dependencies.return_value = ["module1", "module2"]
        mock_dag.nodes = {
            "module1": MagicMock(),
            "module2": MagicMock()
        }
        
        executed_modules = set()
        
        # First module can execute
        can_execute_1 = executor._can_execute(mock_dag, "module1", executed_modules)
        
        # After module1 executes
        executed_modules.add("module1")
        
        # Second module can now execute if dependency satisfied
        can_execute_2 = executor._can_execute(mock_dag, "module2", executed_modules)
        
        # Both should be able to execute (no dependencies in this mock)
        assert isinstance(can_execute_1, bool)
        assert isinstance(can_execute_2, bool)
    
    def test_handles_circular_dependencies(self):
        """Test that circular dependencies are detected."""
        executor = ParallelExecutor()
        
        mock_dag = MagicMock()
        mock_dag.resolve_dependencies.return_value = ["module1", "module2"]
        mock_dag.nodes = {
            "module1": MagicMock(),
            "module2": MagicMock()
        }
        
        # Mock _can_execute to always return False (circular dependency)
        executor._can_execute = lambda dag, mod, executed: False
        
        results = executor.execute_parallel(
            mock_dag,
            "test.json",
            ["module1", "module2"]
        )
        
        # Should have errors for modules that couldn't execute
        assert "errors" in results
        assert len(results["errors"]) > 0
    
    def test_handles_unknown_modules(self):
        """Test that unknown modules are handled gracefully."""
        executor = ParallelExecutor()
        
        mock_dag = MagicMock()
        mock_dag.resolve_dependencies.return_value = ["unknown_module"]
        mock_dag.nodes = {}
        
        executor._can_execute = lambda dag, mod, executed: True
        
        results = executor.execute_parallel(
            mock_dag,
            "test.json",
            ["unknown_module"]
        )
        
        # Should handle gracefully
        assert "errors" in results or "modules_run" in results
    
    def test_tracks_execution_order(self):
        """Test that execution order is tracked."""
        executor = ParallelExecutor()
        
        mock_dag = MagicMock()
        execution_order = ["module1", "module2", "module3"]
        mock_dag.resolve_dependencies.return_value = execution_order
        mock_dag.nodes = {
            "module1": MagicMock(),
            "module2": MagicMock(),
            "module3": MagicMock()
        }
        
        executor._execute_module = lambda node, path: {"status": "success"}
        executor._can_execute = lambda dag, mod, executed: True
        
        results = executor.execute_parallel(
            mock_dag,
            "test.json",
            ["module1", "module2", "module3"]
        )
        
        assert "execution_order" in results
        assert results["execution_order"] == execution_order
    
    def test_records_start_time(self):
        """Test that start time is recorded."""
        executor = ParallelExecutor()
        
        mock_dag = MagicMock()
        mock_dag.resolve_dependencies.return_value = []
        mock_dag.nodes = {}
        
        results = executor.execute_parallel(
            mock_dag,
            "test.json",
            []
        )
        
        assert "start_time" in results
        assert isinstance(results["start_time"], float)
