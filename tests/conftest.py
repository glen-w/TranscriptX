"""
Shared pytest fixtures and configuration for TranscriptX tests.

This module provides common fixtures used across the test suite, including
sample transcript data, temporary files, and mocks for external dependencies.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

# Ensure local repo paths win for imports.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# If a different `tests` package is already imported (e.g., from another checkout),
# purge it so pytest imports this workspace's `tests/*`.
_repo_tests_dir = (_REPO_ROOT / "tests").resolve()
_loaded_tests = sys.modules.get("tests")
try:
    loaded_tests_file = getattr(_loaded_tests, "__file__", None)
    loaded_tests_paths = list(getattr(_loaded_tests, "__path__", []))  # namespace pkgs

    is_ours = False
    if loaded_tests_file:
        is_ours = str(Path(loaded_tests_file).resolve()).startswith(str(_repo_tests_dir))
    elif loaded_tests_paths:
        is_ours = any(str(Path(p).resolve()).startswith(str(_repo_tests_dir)) for p in loaded_tests_paths)

    if _loaded_tests is not None and not is_ours:
        for name in list(sys.modules.keys()):
            if name == "tests" or name.startswith("tests."):
                sys.modules.pop(name, None)
except Exception:
    pass

from tests.capabilities import has_convokit, has_docker, has_ffmpeg, has_models

# Put `src/` first so `import transcriptx` uses workspace code.
sys.path.insert(0, str(_REPO_ROOT / "src"))
# Put repo root early so `import tests.*` resolves locally.
sys.path.insert(1, str(_REPO_ROOT))

# Force-import local `tests` package after sys.path ordering is corrected.
try:
    import importlib

    importlib.invalidate_caches()
    importlib.import_module("tests")
except Exception:
    pass


# ============================================================================
# Transcript Data Fixtures
# ============================================================================

@pytest.fixture
def sample_transcript_data() -> Dict[str, Any]:
    """Minimal valid transcript data for testing with database-driven speaker identification."""
    return {
        "segments": [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Hello, welcome to our meeting today.",
                "start": 0.0,
                "end": 3.5
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Thank you for having me. I'm excited to discuss the project.",
                "start": 4.0,
                "end": 8.2
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Great! Let's start with the overview.",
                "start": 8.5,
                "end": 11.0
            }
        ]
    }


@pytest.fixture
def multi_speaker_transcript_data() -> Dict[str, Any]:
    """Transcript data with multiple speakers using database-driven identification."""
    return {
        "segments": [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Good morning everyone, let's begin our weekly standup.",
                "start": 0.0,
                "end": 4.0
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Morning! I completed the user authentication module yesterday.",
                "start": 4.5,
                "end": 8.0
            },
            {
                "speaker": "Charlie",
                "speaker_db_id": 3,
                "text": "That's great! I'm still working on the database optimization.",
                "start": 8.5,
                "end": 12.0
            }
        ]
    }


@pytest.fixture
def sample_speaker_map() -> Dict[str, str]:
    """
    Sample speaker mapping for testing (deprecated).
    
    This fixture is kept for backward compatibility with tests that still
    pass speaker_map to analyze() methods. New tests should use segments
    with speaker_db_id instead.
    """
    return {}


# ============================================================================
# File System Fixtures
# ============================================================================

@pytest.fixture
def temp_transcript_file(tmp_path: Path, sample_transcript_data: Dict[str, Any]) -> Path:
    """Create a temporary transcript JSON file for testing."""
    file_path = tmp_path / "test_transcript.json"
    file_path.write_text(json.dumps(sample_transcript_data, indent=2))
    return file_path


@pytest.fixture
def temp_speaker_map_file(tmp_path: Path, sample_speaker_map: Dict[str, str]) -> Path:
    """Create a temporary speaker map JSON file for testing."""
    file_path = tmp_path / "speaker_map.json"
    file_path.write_text(json.dumps(sample_speaker_map, indent=2))
    return file_path


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for testing."""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    return output_dir


# ============================================================================
# Pipeline Fixtures
# ============================================================================

@pytest.fixture
def mock_transcript_service():
    """Mock TranscriptService to avoid actual file I/O during tests."""
    with patch('transcriptx.io.transcript_service.TranscriptService') as mock_service_class:
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        # Default return values with database-driven speaker identification
        mock_service.load_transcript_data.return_value = (
            [{"speaker": "Alice", "speaker_db_id": 1, "text": "Test", "start": 0.0, "end": 1.0}],
            "test_transcript",
            str(Path("/tmp")),
            {}  # Empty speaker_map - using database-driven approach
        )
        mock_service.load_segments.return_value = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Test", "start": 0.0, "end": 1.0}
        ]
        
        yield mock_service


@pytest.fixture
def pipeline_context_factory(mock_transcript_service, temp_transcript_file):
    """Factory for creating PipelineContext instances in tests."""
    def _create_context(
        transcript_path: str = None,
        speaker_map: Dict[str, str] = None,
        skip_speaker_mapping: bool = False,
        batch_mode: bool = False
    ):
        if transcript_path is None:
            transcript_path = str(temp_transcript_file)
        
        # Configure mock to return appropriate data with database-driven speaker identification
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Test segment", "start": 0.0, "end": 1.0}
        ]
        base_name = Path(transcript_path).stem
        transcript_dir = str(Path(transcript_path).parent)
        default_speaker_map = speaker_map or {}  # Empty by default - using database-driven approach
        
        mock_transcript_service.load_transcript_data.return_value = (
            segments, base_name, transcript_dir, default_speaker_map
        )
        
        # Patch TranscriptService at the module level where it's imported
        with patch('transcriptx.core.pipeline.pipeline_context.TranscriptService', return_value=mock_transcript_service):
            from transcriptx.core.pipeline.pipeline_context import PipelineContext
            return PipelineContext(
                transcript_path=transcript_path,
                speaker_map=speaker_map,
                skip_speaker_mapping=skip_speaker_mapping,
                batch_mode=batch_mode
            )
    
    return _create_context


# ============================================================================
# Module Registry Fixtures
# ============================================================================

@pytest.fixture
def mock_module_registry():
    """Mock module registry for testing."""
    with patch('transcriptx.core.pipeline.module_registry._module_registry') as mock_registry:
        mock_registry.get_available_modules.return_value = [
            'sentiment', 'ner', 'emotion', 'stats'
        ]
        mock_registry.get_module_info.return_value = MagicMock(
            name='sentiment',
            description='Sentiment Analysis',
            category='medium',
            dependencies=[],
            timeout_seconds=600
        )
        mock_registry.get_dependencies.return_value = []
        yield mock_registry


@pytest.fixture
def mock_analysis_module():
    """Mock analysis module function for testing."""
    def _mock_module(transcript_path: str) -> Dict[str, Any]:
        return {
            "module": "test_module",
            "transcript_path": transcript_path,
            "status": "success",
            "results": {"test": "data"}
        }
    return _mock_module


# ============================================================================
# CLI Fixtures
# ============================================================================

@pytest.fixture
def typer_test_client():
    """Typer test client for CLI testing."""
    from typer.testing import CliRunner
    return CliRunner()


@pytest.fixture(autouse=True)
def mock_questionary():
    """Mock questionary for all tests to prevent interactive prompts."""
    # Create mock objects that return values without prompting
    mock_confirm_instance = MagicMock()
    mock_confirm_instance.ask.return_value = True  # Default to yes
    
    mock_text_instance = MagicMock()
    mock_text_instance.ask.return_value = "Test Speaker"  # Default name
    
    mock_select_instance = MagicMock()
    mock_select_instance.ask.return_value = None
    
    mock_path_instance = MagicMock()
    mock_path_instance.ask.return_value = ""
    
    # Patch questionary at all import locations
    with patch('transcriptx.io.tag_management.questionary') as mock_q_tm, \
         patch('questionary.confirm') as mock_confirm, \
         patch('questionary.text') as mock_text, \
         patch('questionary.select') as mock_select, \
         patch('questionary.path') as mock_path:
        
        # Setup module-level mocks
        mock_q_tm.confirm.return_value = mock_confirm_instance
        mock_q_tm.text.return_value = mock_text_instance
        mock_q_tm.select.return_value = mock_select_instance
        mock_q_tm.path.return_value = mock_path_instance
        
        # Setup package-level mocks
        mock_confirm.return_value = mock_confirm_instance
        mock_text.return_value = mock_text_instance
        mock_select.return_value = mock_select_instance
        mock_path.return_value = mock_path_instance
        
        yield {
            'confirm': mock_confirm,
            'text': mock_text,
            'select': mock_select,
            'path': mock_path
        }


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    from transcriptx.core.utils.config import TranscriptXConfig
    
    config = TranscriptXConfig()
    config.output.base_output_dir = "/tmp/test_outputs"
    config.output.default_audio_folder = "/tmp/test_recordings"
    config.output.default_transcript_folder = "/tmp/test_transcripts"
    
    with patch('transcriptx.core.utils.config.get_config', return_value=config):
        yield config


# ============================================================================
# ML Model Mocks
# ============================================================================

@pytest.fixture
def mock_nlp_model():
    """Mock spaCy NLP model to avoid loading real models during tests."""
    with patch('spacy.load') as mock_load:
        mock_model = MagicMock()
        mock_doc = MagicMock()
        mock_doc.ents = []
        mock_doc.sents = []
        mock_doc.__iter__ = lambda x: iter([])
        mock_model.return_value = mock_doc
        mock_load.return_value = mock_model
        yield mock_model


@pytest.fixture
def mock_transformers_model():
    """Mock transformers model for emotion/sentiment analysis tests."""
    with patch('transformers.pipeline') as mock_pipeline:
        mock_emotion_pipeline = MagicMock()
        mock_emotion_pipeline.return_value = [{"label": "joy", "score": 0.95}]
        mock_pipeline.return_value = mock_emotion_pipeline
        yield mock_emotion_pipeline


@pytest.fixture
def mock_geocoding_api():
    """Mock geocoding API calls for NER tests."""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{
                "formatted_address": "New York, NY, USA",
                "geometry": {
                    "location": {"lat": 40.7128, "lng": -74.0060}
                }
            }]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        yield mock_get


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def mock_database():
    """Mock database connection for integration tests."""
    with patch('transcriptx.database.get_database_manager') as mock_db_manager:
        mock_manager = MagicMock()
        mock_db_manager.return_value = mock_manager
        yield mock_manager


# ============================================================================
# Logging Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def suppress_logging():
    """Suppress logging output during tests to keep output clean."""
    with patch('transcriptx.core.utils.logger.get_logger') as mock_logger:
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        yield mock_log


# ============================================================================
# Environment Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def clean_environment():
    """Clean environment variables before each test."""
    original_env = os.environ.copy()
    
    # Clean up any test-specific environment variables
    test_vars = [key for key in os.environ.keys() if key.startswith('TEST_')]
    for var in test_vars:
        del os.environ[var]

    # Default to offline-safe behavior in tests (no implicit model/resource downloads).
    os.environ.setdefault("TRANSCRIPTX_DISABLE_DOWNLOADS", "1")
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "smoke: fast, deterministic, no external services/models; required for CI",
    )
    config.addinivalue_line("markers", "unit: Unit tests for individual functions/classes")
    config.addinivalue_line("markers", "integration: Integration tests for workflows and pipelines")
    config.addinivalue_line("markers", "slow: Tests that take longer to run")
    config.addinivalue_line("markers", "requires_models: Tests that require downloaded ML models")
    config.addinivalue_line("markers", "requires_docker: Tests that require Docker")
    config.addinivalue_line("markers", "requires_ffmpeg: Tests that require ffmpeg/ffprobe")
    config.addinivalue_line("markers", "requires_api: Tests that require external API access")
    config.addinivalue_line("markers", "database: Tests that require database setup")
    config.addinivalue_line("markers", "performance: Performance and benchmark tests")
    config.addinivalue_line(
        "markers", "timeout: Tests that may legitimately take longer than 5 minutes"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test paths and names."""
    has_models_enabled = has_models()
    has_docker_enabled = has_docker()
    has_ffmpeg_enabled = has_ffmpeg()
    has_convokit_enabled = has_convokit()

    for item in items:
        path_str = str(item.fspath).lower()
        
        # Add integration markers by path
        if "/tests/integration/core/" in path_str:
            if not any(marker.name == "integration" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.integration)
            if not any(marker.name == "integration_core" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.integration_core)
        elif "/tests/integration/extended/" in path_str or "/tests/integration/" in path_str:
            if not any(marker.name == "integration" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.integration)
            if not any(marker.name == "integration_extended" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.integration_extended)

        # Treat CLI workflow tests as integration-level by default (they exercise orchestration).
        if "/tests/cli/" in path_str:
            if not any(marker.name == "integration" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.integration)
        
        # Add database marker to tests in database/ directory
        if "database" in path_str:
            if not any(marker.name == "database" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.database)

        # Add smoke marker for tests in tests/smoke
        if "/tests/smoke/" in path_str:
            if not any(marker.name == "smoke" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.smoke)

        # Treat archived tests as slow/non-gating
        if "/scripts/archived/" in path_str:
            if not any(marker.name == "slow" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.slow)
        
        # Add slow marker to tests with "slow" in the name (if not already marked)
        if "slow" in item.name.lower():
            if not any(marker.name == "slow" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.slow)
        
        # Contract tests are offline/deterministic by path (no name heuristics).
        is_contract_path = "/tests/contracts/" in path_str
        if is_contract_path and not any(marker.name == "contract" for marker in item.iter_markers()):
            item.add_marker(pytest.mark.contract)

        # Add requires_models marker for model-heavy areas (skip for contract path)
        if any(keyword in path_str for keyword in [
            "ner",
            "topic_modeling",
            "emotion",
            "contagion",
            "entity_sentiment",
            "semantic_similarity_advanced",
            "convokit",
        ]) and not is_contract_path:
            if not any(marker.name == "requires_models" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.requires_models)

        # Add requires_docker marker for Docker/WhisperX tests
        if any(keyword in path_str for keyword in ["whisperx", "docker", "compose"]):
            if not any(marker.name == "requires_docker" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.requires_docker)

        # Add requires_ffmpeg marker for audio/WAV/ffmpeg paths
        if any(keyword in path_str for keyword in ["audio", "wav", "ffmpeg", "ffprobe", "playback"]):
            if "/tests/cli/" in path_str or "/tests/analysis/" in path_str:
                if not any(marker.name == "requires_ffmpeg" for marker in item.iter_markers()):
                    item.add_marker(pytest.mark.requires_ffmpeg)
        
        # Add performance marker to tests with "performance" or "benchmark" in the name
        if any(keyword in item.name.lower() for keyword in ["performance", "benchmark", "speed"]):
            if not any(marker.name == "performance" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.performance)

        # Apply skips for missing capabilities
        if item.get_closest_marker("requires_models") and not has_models_enabled:
            reason = "requires_models: set TRANSCRIPTX_TEST_MODELS=1 and install models"
            item.add_marker(pytest.mark.skip(reason=reason))

        if item.get_closest_marker("requires_docker") and not has_docker_enabled:
            item.add_marker(pytest.mark.skip(reason="requires_docker: Docker not available"))

        if item.get_closest_marker("requires_ffmpeg") and not has_ffmpeg_enabled:
            item.add_marker(pytest.mark.skip(reason="requires_ffmpeg: ffmpeg/ffprobe not available"))

        if item.get_closest_marker("requires_models") and "convokit" in path_str and not has_convokit_enabled:
            item.add_marker(pytest.mark.skip(reason="requires_models: convokit not installed"))


# ============================================================================
# Regression Test Fixtures
# ============================================================================

# Import regression test fixtures to make them available to all tests
from tests.fixtures.path_resolution_fixtures import (
    fixture_ambiguous_duplicates,
    fixture_relative_vs_absolute,
    fixture_stale_state_pointers,
    fixture_moved_outputs,
)
from tests.fixtures.state_recovery_fixtures import (
    fixture_corrupt_json,
    fixture_corrupt_json_missing_fields,
    fixture_corrupt_json_invalid_types,
    fixture_backup_chain,
    fixture_concurrent_writers,
)
from tests.fixtures.cli_fixtures import (
    cli_runner,
    non_interactive_env,
)
from tests.fixtures.database_fixtures import (
    test_database_url,
    test_database_engine,
    db_session,
    sample_speaker,
    sample_speaker_profile,
    sample_conversation,
    sample_analysis_result,
    multiple_speakers,
    mock_database_manager,
    isolated_database,
)
from tests.fixtures.edge_transcript_fixtures import (
    edge_transcript_empty,
    edge_transcript_ultrashort,
    edge_transcript_overlapping,
    edge_transcript_weird_timestamps,
    edge_transcript_unknown_speaker,
    edge_transcript_weird_punctuation,
    edge_transcript_large,
    edge_transcript_file_factory,
)
