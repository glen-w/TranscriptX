"""
Base classes and interfaces for TranscriptX analysis modules.

This module provides base classes and protocols that define the standard
interface for all analysis modules, ensuring consistency and making it
easier to add new modules or modify existing ones.

Key Features:
- Abstract base class for analysis modules
- Standard interface definition
- Common error handling patterns
- Validation utilities
- Configuration management
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.analysis.common import (
    validate_segments,
    log_analysis_start,
    log_analysis_complete,
    log_analysis_error,
)
from transcriptx.core.utils.module_result import (
    build_module_result,
    capture_exception,
    now_iso,
)

logger = get_logger()

# Optional imports for new service-based interface
try:
    from transcriptx.core.pipeline.pipeline_context import PipelineContext
    from transcriptx.core.output.output_service import (
        OutputService,
        create_output_service,
    )
except ImportError:
    # Fallback for modules that haven't been migrated yet
    PipelineContext = None
    OutputService = None
    create_output_service = None


class AnalysisModule(ABC):
    """
    Abstract base class for all TranscriptX analysis modules.

    This class defines the standard interface that all analysis modules
    must implement, ensuring consistency across the codebase.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the analysis module.

        Args:
            config: Optional configuration dictionary
        """
        # Validate config type - must be None or a dict
        if config is not None and not isinstance(config, dict):
            raise TypeError(
                f"config must be None or a dict, got {type(config).__name__}"
            )
        self.config = config or {}
        self.module_name = self.__class__.__name__.lower().replace("analyzer", "")
        self.supports_aggregation = False

    @abstractmethod
    def analyze(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Perform the core analysis on transcript segments.

        This is the main analysis method that must be implemented by all modules.

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility.
                        Modules should use extract_speaker_info() from speaker_extraction instead)

        Returns:
            Dictionary containing analysis results
        """
        pass

    def save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save analysis results to files.

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        self._save_results(results, output_service)

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save results using OutputService (canonical interface).

        Subclasses should override this method to implement their specific saving logic.
        Default implementation saves results as JSON.

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        # Default implementation: save as JSON
        output_service.save_data(results, "results", format_type="json")

    def validate_input(self, segments: List[Dict[str, Any]]) -> bool:
        """
        Validate input segments before analysis.

        Args:
            segments: List of transcript segments

        Returns:
            True if valid, False otherwise
        """
        return validate_segments(segments)

    def get_module_info(self) -> Dict[str, Any]:
        """
        Get information about this analysis module.

        Returns:
            Dictionary containing module information
        """
        return {
            "name": self.module_name,
            "description": self.__doc__ or "No description available",
            "version": "1.0.0",  # Could be made configurable
            "dependencies": self.get_dependencies(),
        }

    def get_dependencies(self) -> List[str]:
        """
        Get list of other modules this module depends on.

        Returns:
            List of module names that must run before this one
        """
        return []

    def run_from_context(self, context: "PipelineContext") -> Dict[str, Any]:
        """
        Run analysis using a PipelineContext (preferred method).

        This method extracts data from the context, performs analysis, and saves
        results using OutputService. It also stores results in the context for
        reuse by other modules.

        Args:
            context: PipelineContext containing transcript data and cached results

        Returns:
            Dictionary containing analysis results and metadata
        """
        import time

        started_at = now_iso()
        start_time = time.time()
        try:
            log_analysis_start(self.module_name, context.transcript_path)

            # Extract data from context
            segments = context.get_segments()
            speaker_map = context.get_speaker_map()
            base_name = context.get_base_name()

            # Validate input
            if not self.validate_input(segments):
                raise ValueError(f"Invalid input segments for {self.module_name}")

            # Perform analysis (pure logic, no I/O)
            results = self.analyze(segments, speaker_map)

            # Create output service and save results
            output_service = create_output_service(
                context.transcript_path,
                self.module_name,
                output_dir=context.get_transcript_dir(),
                run_id=context.get_run_id(),
                runtime_flags=context.get_runtime_flags(),
            )
            self.save_results(results, output_service=output_service)

            # Store result in context for reuse by other modules
            context.store_analysis_result(self.module_name, results)

            log_analysis_complete(self.module_name, context.transcript_path)

            finished_at = now_iso()
            duration_seconds = time.time() - start_time
            output_structure = output_service.get_output_structure()
            if hasattr(output_structure, "module_dir"):
                output_directory = str(output_structure.module_dir)
            elif isinstance(output_structure, dict):
                output_directory = str(output_structure.get("module_dir", ""))
            else:
                output_directory = ""

            module_result = build_module_result(
                module_name=self.module_name,
                status="success",
                started_at=started_at,
                finished_at=finished_at,
                artifacts=output_service.get_artifacts(),
                metrics={
                    "duration_seconds": duration_seconds,
                    "output_directory": output_directory,
                },
                payload_type="analysis_results",
                payload=results,
            )
            module_result["output_directory"] = output_directory
            return module_result

        except Exception as e:
            log_analysis_error(self.module_name, context.transcript_path, str(e))
            if isinstance(e, ValueError):
                raise
            finished_at = now_iso()
            duration_seconds = time.time() - start_time
            return build_module_result(
                module_name=self.module_name,
                status="error",
                started_at=started_at,
                finished_at=finished_at,
                artifacts=[],
                metrics={"duration_seconds": duration_seconds},
                payload_type="analysis_results",
                payload={},
                error=capture_exception(e),
            )

    def run_from_file(self, transcript_path: str) -> Dict[str, Any]:
        """
        Run analysis from a transcript file path.

        This method creates a PipelineContext and delegates to run_from_context().

        Args:
            transcript_path: Path to the transcript JSON file

        Returns:
            Dictionary containing analysis results and metadata
        """
        if PipelineContext is None:
            raise ImportError("PipelineContext is required but not available")
        context = PipelineContext(transcript_path)
        return self.run_from_context(context)

    def aggregate(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Optional aggregation hook for group analysis.

        Subclasses can override when supports_aggregation is True.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support aggregation."
        )


class AnalysisModuleProtocol(Protocol):
    """
    Protocol defining the interface for analysis modules.

    This can be used for type hints when you need to work with
    analysis modules without knowing their specific type.
    """

    def run_from_file(self, transcript_path: str) -> Dict[str, Any]:
        """Run analysis from a transcript file path."""
        ...

    def get_module_info(self) -> Dict[str, Any]:
        """Get information about this analysis module."""
        ...


class AnalysisResult:
    """
    Standardized analysis result container.

    This class provides a consistent way to structure analysis results
    across all modules.
    """

    def __init__(
        self,
        module_name: str,
        transcript_path: str,
        status: str = "success",
        results: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize analysis result.

        Args:
            module_name: Name of the analysis module
            transcript_path: Path to the analyzed transcript
            status: Analysis status ("success", "error", "partial")
            results: Analysis results dictionary
            errors: List of errors (if any)
            metadata: Additional metadata
        """
        self.module_name = module_name
        self.transcript_path = transcript_path
        self.status = status
        self.results = results or {}
        self.errors = errors or []
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "module": self.module_name,
            "transcript_path": self.transcript_path,
            "status": self.status,
            "results": self.results,
            "errors": self.errors,
            "metadata": self.metadata,
        }

    def is_successful(self) -> bool:
        """Check if analysis was successful."""
        return self.status == "success" and not self.errors

    def has_errors(self) -> bool:
        """Check if analysis had errors."""
        return bool(self.errors) or self.status == "error"


def create_analysis_module(
    module_class: type, config: Optional[Dict[str, Any]] = None
) -> AnalysisModule:
    """
    Factory function to create analysis modules.

    Args:
        module_class: Analysis module class
        config: Optional configuration

    Returns:
        Configured analysis module instance
    """
    return module_class(config)


def validate_module_interface(module: AnalysisModule) -> bool:
    """
    Validate that a module implements the required interface.

    Args:
        module: Analysis module instance

    Returns:
        True if valid, False otherwise
    """
    required_methods = ["analyze", "save_results", "run_from_file"]

    for method_name in required_methods:
        if not hasattr(module, method_name):
            logger.error(
                f"Module {module.__class__.__name__} missing required method: {method_name}"
            )
            return False

        if not callable(getattr(module, method_name)):
            logger.error(
                f"Module {module.__class__.__name__} method {method_name} is not callable"
            )
            return False

    return True


# Example implementation for reference
class ExampleAnalysisModule(AnalysisModule):
    """
    Example analysis module showing the standard implementation pattern.

    This class demonstrates how to implement a new analysis module
    following the standard interface.
    """

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """Perform example analysis."""
        # Example analysis logic
        total_segments = len(segments)
        total_speakers = len(speaker_map)

        return {
            "total_segments": total_segments,
            "total_speakers": total_speakers,
            "analysis_type": "example",
        }

    def save_results(
        self,
        results: Dict[str, Any],
        output_service: Optional["OutputService"] = None,
        output_structure: Optional[Dict[str, str]] = None,
        base_name: Optional[str] = None,
    ) -> None:
        """Save example results."""
        if output_service is not None:
            # Use new interface
            output_service.save_data(results, "example_results", format_type="json")
        else:
            # Use legacy interface
            from transcriptx.core.analysis.common import save_analysis_data

            save_analysis_data(
                results, output_structure, base_name, "example_results", "json"
            )

    def get_dependencies(self) -> List[str]:
        """This module has no dependencies."""
        return []
