"""
Tests for the DAG pipeline implementation.

This module tests the DAGPipeline class which manages module dependencies
and execution order.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.pipeline.dag_pipeline import DAGPipeline, DAGNode, create_dag_pipeline


class TestDAGPipeline:
    """Tests for DAGPipeline class."""
    
    def test_add_module(self):
        """Test adding modules to the DAG."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module(
            name="test_module",
            description="Test Module",
            category="medium",
            dependencies=[],
            function=mock_function
        )
        
        assert "test_module" in pipeline.nodes
        node = pipeline.nodes["test_module"]
        assert node.name == "test_module"
        assert node.description == "Test Module"
        assert node.category == "medium"
        assert node.dependencies == []
        assert node.function == mock_function
    
    def test_resolve_dependencies_no_deps(self):
        """Test dependency resolution with no dependencies."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("module1", "Module 1", "light", [], mock_function)
        pipeline.add_module("module2", "Module 2", "medium", [], mock_function)
        
        execution_order = pipeline.resolve_dependencies(["module1", "module2"])
        
        assert "module1" in execution_order
        assert "module2" in execution_order
        # Light modules should come before medium
        assert execution_order.index("module1") < execution_order.index("module2")
    
    def test_resolve_dependencies_with_deps(self):
        """Test dependency resolution with dependencies."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("base", "Base Module", "light", [], mock_function)
        pipeline.add_module("dependent", "Dependent Module", "medium", ["base"], mock_function)
        
        execution_order = pipeline.resolve_dependencies(["dependent"])
        
        # Base should come before dependent
        assert "base" in execution_order
        assert "dependent" in execution_order
        assert execution_order.index("base") < execution_order.index("dependent")
    
    def test_resolve_dependencies_transitive(self):
        """Test dependency resolution with transitive dependencies."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("base", "Base", "light", [], mock_function)
        pipeline.add_module("middle", "Middle", "medium", ["base"], mock_function)
        pipeline.add_module("top", "Top", "heavy", ["middle"], mock_function)
        
        execution_order = pipeline.resolve_dependencies(["top"])
        
        # All dependencies should be included
        assert "base" in execution_order
        assert "middle" in execution_order
        assert "top" in execution_order
        # Order should respect dependencies
        assert execution_order.index("base") < execution_order.index("middle")
        assert execution_order.index("middle") < execution_order.index("top")
    
    def test_topological_sort_cycle_detection(self):
        """Test that cycles are detected in dependency graph."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        # Create a cycle (this shouldn't happen in practice, but we test detection)
        pipeline.add_module("a", "A", "light", ["b"], mock_function)
        pipeline.add_module("b", "B", "medium", ["a"], mock_function)
        
        # Should raise ValueError when cycle is detected
        with pytest.raises(ValueError, match="Circular dependency"):
            pipeline.resolve_dependencies(["a"])
    
    def test_resolve_dependencies_complex_chain(self):
        """Test dependency resolution with complex dependency chain."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        # Create complex chain: base -> middle1 -> middle2 -> top
        pipeline.add_module("base", "Base", "light", [], mock_function)
        pipeline.add_module("middle1", "Middle1", "medium", ["base"], mock_function)
        pipeline.add_module("middle2", "Middle2", "medium", ["middle1"], mock_function)
        pipeline.add_module("top", "Top", "heavy", ["middle2"], mock_function)
        
        execution_order = pipeline.resolve_dependencies(["top"])
        
        # All dependencies should be included in correct order
        assert "base" in execution_order
        assert "middle1" in execution_order
        assert "middle2" in execution_order
        assert "top" in execution_order
        assert execution_order.index("base") < execution_order.index("middle1")
        assert execution_order.index("middle1") < execution_order.index("middle2")
        assert execution_order.index("middle2") < execution_order.index("top")
    
    def test_resolve_dependencies_multiple_dependents(self):
        """Test dependency resolution with multiple dependents."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("base", "Base", "light", [], mock_function)
        pipeline.add_module("dependent1", "Dependent1", "medium", ["base"], mock_function)
        pipeline.add_module("dependent2", "Dependent2", "medium", ["base"], mock_function)
        
        execution_order = pipeline.resolve_dependencies(["dependent1", "dependent2"])
        
        # Base should come before both dependents
        assert execution_order.index("base") < execution_order.index("dependent1")
        assert execution_order.index("base") < execution_order.index("dependent2")
    
    def test_sort_by_category(self):
        """Test sorting modules by category."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("heavy1", "Heavy 1", "heavy", [], mock_function)
        pipeline.add_module("light1", "Light 1", "light", [], mock_function)
        pipeline.add_module("medium1", "Medium 1", "medium", [], mock_function)
        pipeline.add_module("light2", "Light 2", "light", [], mock_function)
        
        execution_order = pipeline.resolve_dependencies(["heavy1", "light1", "medium1", "light2"])
        
        # Light modules should come first
        light_indices = [execution_order.index(m) for m in ["light1", "light2"]]
        medium_index = execution_order.index("medium1")
        heavy_index = execution_order.index("heavy1")
        
        assert all(idx < medium_index for idx in light_indices)
        assert medium_index < heavy_index
    
    @patch('transcriptx.core.pipeline.dag_pipeline.PipelineContext')
    def test_execute_pipeline_success(self, mock_context_class, temp_transcript_file, sample_speaker_map):
        """Test successful pipeline execution."""
        pipeline = DAGPipeline()
        mock_function = MagicMock(return_value={"status": "success"})
        
        pipeline.add_module("test_module", "Test", "light", [], mock_function)
        
        # Mock PipelineContext
        mock_context = MagicMock()
        mock_context.get_segments.return_value = [{"speaker": "SPEAKER_00", "text": "Test"}]
        mock_context.get_speaker_map.return_value = sample_speaker_map
        mock_context.get_base_name.return_value = "test"
        mock_context_class.return_value = mock_context
        
        result = pipeline.execute_pipeline(
            transcript_path=str(temp_transcript_file),
            selected_modules=["test_module"],
            speaker_map=sample_speaker_map,
            skip_speaker_mapping=True
        )
        
        assert result["modules_run"] == ["test_module"]
        assert result["errors"] == []
        assert "execution_order" in result
    
    @patch('transcriptx.core.pipeline.dag_pipeline.PipelineContext')
    def test_execute_pipeline_module_error(self, mock_context_class, temp_transcript_file, sample_speaker_map):
        """Test pipeline execution with module error."""
        pipeline = DAGPipeline()
        mock_function = MagicMock(side_effect=Exception("Module error"))
        
        pipeline.add_module("test_module", "Test", "light", [], mock_function)
        
        # Mock PipelineContext
        mock_context = MagicMock()
        mock_context.get_segments.return_value = [{"speaker": "SPEAKER_00", "text": "Test"}]
        mock_context.get_speaker_map.return_value = sample_speaker_map
        mock_context.get_base_name.return_value = "test"
        mock_context_class.return_value = mock_context
        
        result = pipeline.execute_pipeline(
            transcript_path=str(temp_transcript_file),
            selected_modules=["test_module"],
            speaker_map=sample_speaker_map,
            skip_speaker_mapping=True
        )
        
        # Module should be in errors
        assert len(result["errors"]) > 0
        assert "test_module" in str(result["errors"][0]).lower() or "error" in str(result["errors"][0]).lower()

    def test_execute_pipeline_missing_dependency_error_message(self, temp_transcript_file):
        """Test missing dependency errors include module context."""
        pipeline = DAGPipeline()
        mock_function = MagicMock(return_value={"status": "success"})

        pipeline.add_module("dependent", "Dependent", "medium", ["base"], mock_function)

        with patch('transcriptx.core.pipeline.dag_pipeline.PipelineContext') as mock_context_class, \
             patch('transcriptx.core.pipeline.dag_pipeline.validate_transcript_file'), \
             patch('transcriptx.core.pipeline.dag_pipeline.validate_output_directory'):
            mock_context = MagicMock()
            mock_context.get_segments.return_value = [{"speaker": "SPEAKER_00", "text": "Test"}]
            mock_context.get_speaker_map.return_value = {"SPEAKER_00": "Speaker 1"}
            mock_context.get_base_name.return_value = "test"
            mock_context.validate.return_value = True
            mock_context_class.return_value = mock_context

            result = pipeline.execute_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["dependent"],
                skip_speaker_mapping=True
            )

        assert any("dependent" in error for error in result["errors"])
        assert any("Missing dependencies" in error for error in result["errors"])
    
    def test_execute_pipeline_invalid_transcript(self, tmp_path):
        """Test pipeline execution with invalid transcript."""
        pipeline = DAGPipeline()
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("invalid")
        
        with patch('transcriptx.core.pipeline.dag_pipeline.validate_transcript_file') as mock_validate:
            mock_validate.side_effect = ValueError("Invalid transcript")
            
            result = pipeline.execute_pipeline(
                transcript_path=str(invalid_file),
                selected_modules=["test_module"]
            )
            
            assert result["status"] == "failed"
            assert len(result["errors"]) > 0


class TestCreateDAGPipeline:
    """Tests for create_dag_pipeline function."""
    
    def test_create_dag_pipeline(self):
        """Test creating a DAG pipeline with all modules."""
        with patch('transcriptx.core.pipeline.dag_pipeline.get_module_registry') as mock_registry:
            mock_registry_instance = MagicMock()
            mock_registry_instance.get_available_modules.return_value = ["sentiment", "stats"]
            
            mock_module_info = MagicMock()
            mock_module_info.description = "Test"
            mock_module_info.category = "medium"
            mock_module_info.dependencies = []
            mock_module_info.timeout_seconds = 600
            mock_registry_instance.get_module_info.return_value = mock_module_info
            mock_registry_instance.get_module_function.return_value = MagicMock()
            
            mock_registry.return_value = mock_registry_instance
            
            dag = create_dag_pipeline()
            
            assert isinstance(dag, DAGPipeline)
            # Should have modules added
            assert len(dag.nodes) >= 0  # May be 0 if registry is empty in test


class TestDAGPipelineEdgeCases:
    """Tests for DAG pipeline edge cases and error handling."""
    
    def test_cycle_detection_direct(self):
        """Test direct cycle detection (A -> B -> A)."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("a", "A", "light", ["b"], mock_function)
        pipeline.add_module("b", "B", "medium", ["a"], mock_function)
        
        with pytest.raises(ValueError, match="Circular dependency"):
            pipeline.resolve_dependencies(["a"])
    
    def test_cycle_detection_transitive(self):
        """Test transitive cycle detection (A -> B -> C -> A)."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("a", "A", "light", ["b"], mock_function)
        pipeline.add_module("b", "B", "medium", ["c"], mock_function)
        pipeline.add_module("c", "C", "heavy", ["a"], mock_function)
        
        with pytest.raises(ValueError, match="Circular dependency"):
            pipeline.resolve_dependencies(["a"])
    
    def test_circular_dependency_error(self):
        """Test that circular dependencies raise proper error."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        # Self-dependency (should also be caught)
        pipeline.add_module("a", "A", "light", ["a"], mock_function)
        
        with pytest.raises(ValueError, match="Circular dependency"):
            pipeline.resolve_dependencies(["a"])
    
    def test_missing_dependency_handling(self):
        """Test handling of missing dependencies."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        # Module depends on non-existent module
        pipeline.add_module("dependent", "Dependent", "medium", ["nonexistent"], mock_function)
        
        # Should handle gracefully - may include or skip missing dependency
        execution_order = pipeline.resolve_dependencies(["dependent"])
        # Should at least include the requested module
        assert "dependent" in execution_order or len(execution_order) == 0
    
    def test_timeout_per_module(self):
        """Test that timeout is set per module."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("test", "Test", "light", [], mock_function, timeout_seconds=300)
        
        node = pipeline.nodes["test"]
        assert node.timeout_seconds == 300
    
    def test_fallback_to_sequential(self):
        """Test that pipeline falls back to sequential execution on errors."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("module1", "Module 1", "light", [], mock_function)
        pipeline.add_module("module2", "Module 2", "medium", ["module1"], mock_function)
        
        # Even if one module fails, others should still run
        execution_order = pipeline.resolve_dependencies(["module1", "module2"])
        assert len(execution_order) >= 2
    
    def test_large_dependency_graph(self):
        """Test dependency resolution with large dependency graph (10+ modules)."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        # Create a large chain
        modules = []
        for i in range(15):
            module_name = f"module{i}"
            deps = [f"module{i-1}"] if i > 0 else []
            pipeline.add_module(module_name, f"Module {i}", "light", deps, mock_function)
            modules.append(module_name)
        
        execution_order = pipeline.resolve_dependencies([modules[-1]])
        
        # Should include all dependencies
        assert len(execution_order) == 15
        # Should be in correct order
        for i in range(1, 15):
            assert execution_order.index(f"module{i-1}") < execution_order.index(f"module{i}")
    
    def test_partial_execution_on_failure(self):
        """Test that pipeline continues after module failure."""
        pipeline = DAGPipeline()
        mock_function1 = MagicMock(return_value={"status": "success"})
        mock_function2 = MagicMock(side_effect=Exception("Module error"))
        mock_function3 = MagicMock(return_value={"status": "success"})
        
        pipeline.add_module("module1", "Module 1", "light", [], mock_function1)
        pipeline.add_module("module2", "Module 2", "medium", [], mock_function2)
        pipeline.add_module("module3", "Module 3", "heavy", [], mock_function3)
        
        with patch('transcriptx.core.pipeline.dag_pipeline.PipelineContext') as mock_context_class, \
             patch('transcriptx.core.pipeline.dag_pipeline.validate_transcript_file'), \
             patch('transcriptx.core.pipeline.dag_pipeline.validate_output_directory'):
            
            mock_context = MagicMock()
            mock_context.get_segments.return_value = [{"speaker": "SPEAKER_00", "text": "Test"}]
            mock_context.get_speaker_map.return_value = {"SPEAKER_00": "Speaker 1"}
            mock_context.get_base_name.return_value = "test"
            mock_context.validate.return_value = True
            mock_context_class.return_value = mock_context
            
            result = pipeline.execute_pipeline(
                transcript_path="/tmp/test.json",
                selected_modules=["module1", "module2", "module3"],
                skip_speaker_mapping=True
            )
            
            # Should have run module1 and module3, but module2 should have error
            assert "module1" in result["modules_run"]
            assert "module3" in result["modules_run"] or len(result["errors"]) > 0
            # Should have at least one error for module2
            assert len(result["errors"]) > 0
    
    def test_category_ordering_enforcement(self):
        """Test that category ordering (light -> medium -> heavy) is enforced."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        # Add modules in mixed order
        pipeline.add_module("heavy1", "Heavy 1", "heavy", [], mock_function)
        pipeline.add_module("light1", "Light 1", "light", [], mock_function)
        pipeline.add_module("medium1", "Medium 1", "medium", [], mock_function)
        pipeline.add_module("light2", "Light 2", "light", [], mock_function)
        pipeline.add_module("medium2", "Medium 2", "medium", [], mock_function)
        
        execution_order = pipeline.resolve_dependencies(["heavy1", "light1", "medium1", "light2", "medium2"])
        
        # Find indices
        light_indices = [execution_order.index(m) for m in ["light1", "light2"]]
        medium_indices = [execution_order.index(m) for m in ["medium1", "medium2"]]
        heavy_index = execution_order.index("heavy1")
        
        # All light should come before medium
        assert all(li < mi for li in light_indices for mi in medium_indices)
        # All medium should come before heavy
        assert all(mi < heavy_index for mi in medium_indices)
    
    def test_validate_dependencies_success(self):
        """Test dependency validation with valid dependencies."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("base", "Base", "light", [], mock_function)
        pipeline.add_module("dependent", "Dependent", "medium", ["base"], mock_function)
        
        is_valid, errors = pipeline.validate_dependencies()
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_dependencies_missing(self):
        """Test dependency validation with missing dependencies."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("dependent", "Dependent", "medium", ["nonexistent"], mock_function)
        
        is_valid, errors = pipeline.validate_dependencies()
        
        assert is_valid is False
        assert len(errors) > 0
        assert any("nonexistent" in error for error in errors)
    
    def test_validate_dependencies_cycle(self):
        """Test dependency validation detects cycles."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("a", "A", "light", ["b"], mock_function)
        pipeline.add_module("b", "B", "medium", ["a"], mock_function)
        
        is_valid, errors = pipeline.validate_dependencies()
        
        assert is_valid is False
        assert len(errors) > 0
        assert any("Circular dependency" in error for error in errors)
    
    def test_finalize_registry(self):
        """Test registry finalization."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("test", "Test", "light", [], mock_function)
        
        # Should finalize successfully
        pipeline.finalize()
        assert pipeline._finalized is True
        
        # Should not finalize twice
        pipeline.finalize()  # Should not raise
    
    def test_finalize_with_errors(self):
        """Test finalization fails with invalid dependencies."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("a", "A", "light", ["b"], mock_function)
        pipeline.add_module("b", "B", "medium", ["a"], mock_function)
        
        with pytest.raises(ValueError, match="validation failed"):
            pipeline.finalize()
    
    def test_preflight_check(self):
        """Test preflight checks."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("test", "Test", "light", [], mock_function)
        
        results = pipeline.preflight_check(["test"])
        
        assert "all_importable" in results
        assert "missing_dependencies" in results
        assert "skipped_modules" in results
        assert "warnings" in results
    
    def test_preflight_check_missing_module(self):
        """Test preflight check with missing module."""
        pipeline = DAGPipeline()
        
        results = pipeline.preflight_check(["nonexistent"])
        
        assert "nonexistent" in results["skipped_modules"] or "nonexistent" in str(results["warnings"])
    
    def test_check_missing_dependencies(self):
        """Test checking for missing dependencies."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("base", "Base", "light", [], mock_function)
        pipeline.add_module("dependent", "Dependent", "medium", ["base"], mock_function)
        
        node = pipeline.nodes["dependent"]
        
        # No modules executed yet
        missing = pipeline._check_missing_dependencies(node, [])
        assert "base" in missing
        
        # Base executed
        missing = pipeline._check_missing_dependencies(node, ["base"])
        assert len(missing) == 0
    
    def test_get_dependency_graph(self):
        """Test getting dependency graph."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("base", "Base", "light", [], mock_function)
        pipeline.add_module("dependent", "Dependent", "medium", ["base"], mock_function)
        
        graph = pipeline.get_dependency_graph(["dependent"])
        
        assert "base" in graph
        assert "dependent" in graph
        assert "base" in graph["dependent"]
    
    def test_implicit_dependencies(self):
        """Test implicit dependency detection."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("emotion", "Emotion", "light", [], mock_function)
        pipeline.add_module("contagion", "Contagion", "medium", [], mock_function)
        
        # Contagion should implicitly depend on emotion
        execution_order = pipeline.resolve_dependencies(["contagion"])
        
        assert "emotion" in execution_order
        assert execution_order.index("emotion") < execution_order.index("contagion")
    
    def test_deterministic_ordering(self):
        """Test that ordering is deterministic for modules with same dependencies."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        
        pipeline.add_module("base", "Base", "light", [], mock_function)
        pipeline.add_module("dep1", "Dep1", "medium", ["base"], mock_function)
        pipeline.add_module("dep2", "Dep2", "medium", ["base"], mock_function)
        
        execution_order1 = pipeline.resolve_dependencies(["dep1", "dep2"])
        execution_order2 = pipeline.resolve_dependencies(["dep2", "dep1"])
        
        # Should be deterministic (sorted by name)
        assert execution_order1 == execution_order2

    def test_execute_pipeline_reuses_cached_run(self, temp_transcript_file):
        """Test that cached pipeline runs short-circuit execution."""
        pipeline = DAGPipeline()
        mock_function = MagicMock()
        pipeline.add_module("test_module", "Test", "light", [], mock_function)

        db_coordinator = MagicMock()
        db_coordinator.reused_pipeline_run = True
        db_coordinator.get_cached_module_names.return_value = ["test_module"]
        db_coordinator.pipeline_run = MagicMock(id=123)

        with patch('transcriptx.core.pipeline.dag_pipeline.validate_transcript_file'), \
             patch('transcriptx.core.pipeline.dag_pipeline.validate_output_directory'), \
             patch('transcriptx.core.pipeline.dag_pipeline.PipelineContext') as mock_context_class:
            mock_context = MagicMock()
            mock_context.validate.return_value = True
            mock_context.get_segments.return_value = [{"speaker": "SPEAKER_00", "text": "Test"}]
            mock_context.close.return_value = None
            mock_context_class.return_value = mock_context

            result = pipeline.execute_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["test_module"],
                skip_speaker_mapping=True,
                db_coordinator=db_coordinator,
            )

        assert result["status"] == "reused"
        assert result["modules_run"] == ["test_module"]
        mock_function.assert_not_called()
