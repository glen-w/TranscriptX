"""
Fixtures for DAG pipeline testing.

This module provides reusable fixtures for testing DAG pipeline functionality.
"""

from unittest.mock import MagicMock

import pytest

from transcriptx.core.pipeline.dag_pipeline import DAGPipeline, DAGNode


@pytest.fixture
def empty_dag_pipeline():
    """Create an empty DAG pipeline."""
    return DAGPipeline()


@pytest.fixture
def simple_dag_pipeline():
    """Create a simple DAG pipeline with basic modules."""
    pipeline = DAGPipeline()
    mock_function = MagicMock(return_value={"status": "success"})
    
    pipeline.add_module("module1", "Module 1", "light", [], mock_function)
    pipeline.add_module("module2", "Module 2", "medium", [], mock_function)
    
    return pipeline


@pytest.fixture
def dependency_dag_pipeline():
    """Create a DAG pipeline with dependencies."""
    pipeline = DAGPipeline()
    mock_function = MagicMock(return_value={"status": "success"})
    
    pipeline.add_module("base", "Base Module", "light", [], mock_function)
    pipeline.add_module("dependent", "Dependent Module", "medium", ["base"], mock_function)
    
    return pipeline


@pytest.fixture
def complex_dag_pipeline():
    """Create a complex DAG pipeline with multiple dependency levels."""
    pipeline = DAGPipeline()
    mock_function = MagicMock(return_value={"status": "success"})
    
    # Level 1
    pipeline.add_module("level1", "Level 1", "light", [], mock_function)
    
    # Level 2 (depends on level1)
    pipeline.add_module("level2a", "Level 2A", "medium", ["level1"], mock_function)
    pipeline.add_module("level2b", "Level 2B", "medium", ["level1"], mock_function)
    
    # Level 3 (depends on level2)
    pipeline.add_module("level3", "Level 3", "heavy", ["level2a", "level2b"], mock_function)
    
    return pipeline


@pytest.fixture
def mock_module_function():
    """Create a mock module function."""
    return MagicMock(return_value={"status": "success", "data": {"test": "value"}})


@pytest.fixture
def mock_module_function_with_error():
    """Create a mock module function that raises an error."""
    return MagicMock(side_effect=Exception("Module error"))


@pytest.fixture
def sample_transcript_data():
    """Create sample transcript data with database-driven speaker identification."""
    return {
        "segments": [
            {
                "speaker": "Alice",
                "original_speaker_id": "SPEAKER_00",
                "speaker_db_id": 1,
                "text": "Hello world",
                "start": 0.0,
                "end": 2.0
            },
            {
                "speaker": "Bob",
                "original_speaker_id": "SPEAKER_01",
                "speaker_db_id": 2,
                "text": "Hi there",
                "start": 2.5,
                "end": 4.0
            }
        ]
    }


@pytest.fixture
def sample_speaker_map():
    """
    Create sample speaker map (DEPRECATED).
    
    Returns empty dict. Use segments with speaker_db_id instead.
    """
    import warnings
    warnings.warn(
        "sample_speaker_map fixture is deprecated. Use segments with speaker_db_id instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return {}  # Return empty dict for backward compatibility
