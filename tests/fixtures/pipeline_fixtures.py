"""
Pipeline fixtures for testing.

This module provides fixtures for pipeline-related testing, including
PipelineContext, DAG pipeline, and module execution.
"""

from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch


def create_mock_pipeline_context(
    transcript_path: str,
    segments: List[Dict[str, Any]] = None,
    speaker_map: Dict[str, str] = None,
    base_name: str = None
):
    """
    Create a mock PipelineContext for testing.
    
    Note: speaker_map parameter is deprecated. Segments should include
    speaker_db_id for database-driven identification.
    
    Args:
        transcript_path: Path to transcript file
        segments: List of transcript segments (should include speaker_db_id)
        speaker_map: Deprecated - Speaker mapping dictionary (kept for backward compatibility)
        base_name: Base name for transcript
        
    Returns:
        Mock PipelineContext object
    """
    if segments is None:
        segments = [
            {
                "speaker": "Speaker 1",
                "original_speaker_id": "SPEAKER_00",
                "speaker_db_id": 1,
                "text": "Test segment",
                "start": 0.0,
                "end": 1.0
            }
        ]
    
    # Extract speaker_map from segments if not provided (for backward compatibility)
    if speaker_map is None:
        from transcriptx.core.utils.speaker_extraction import get_unique_speakers
        speaker_map = get_unique_speakers(segments)
    
    if base_name is None:
        base_name = Path(transcript_path).stem
    
    mock_context = MagicMock()
    mock_context.transcript_path = transcript_path
    mock_context.segments = segments
    mock_context.speaker_map = speaker_map  # Deprecated but kept for backward compatibility
    mock_context.base_name = base_name
    mock_context.transcript_dir = str(Path(transcript_path).parent)
    mock_context._analysis_results = {}
    mock_context._computed_values = {}
    
    # Mock methods
    mock_context.get_segments.return_value = segments
    mock_context.get_speaker_map.return_value = speaker_map
    mock_context.get_base_name.return_value = base_name
    mock_context.store_analysis_result = MagicMock()
    mock_context.get_analysis_result = MagicMock(return_value=None)
    
    return mock_context


def create_mock_dag_pipeline():
    """Create a mock DAGPipeline for testing."""
    mock_pipeline = MagicMock()
    mock_pipeline.nodes = {}
    mock_pipeline.execution_order = []
    mock_pipeline.results = {}
    mock_pipeline.errors = []
    
    # Mock methods
    mock_pipeline.add_module = MagicMock()
    mock_pipeline.resolve_dependencies = MagicMock(return_value=[])
    mock_pipeline.execute_pipeline = MagicMock(return_value={
        "transcript_path": "test_transcript.json",
        "modules_requested": [],
        "modules_run": [],
        "errors": [],
        "execution_order": []
    })
    
    return mock_pipeline


def create_mock_module_info(
    name: str = "test_module",
    description: str = "Test Module",
    category: str = "medium",
    dependencies: List[str] = None
):
    """Create a mock ModuleInfo for testing."""
    if dependencies is None:
        dependencies = []
    
    mock_info = MagicMock()
    mock_info.name = name
    mock_info.description = description
    mock_info.category = category
    mock_info.dependencies = dependencies
    mock_info.timeout_seconds = 600
    mock_info.function = None
    
    return mock_info
