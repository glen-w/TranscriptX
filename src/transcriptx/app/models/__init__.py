"""Application layer models: requests, results, errors, metadata."""

from transcriptx.app.models.errors import (
    ArtifactReadError,
    DependencyError,
    ModuleExecutionError,
    PathConfigError,
    ValidationError,
    WorkflowExecutionError,
)
from transcriptx.app.models.metadata import TranscriptMetadata
from transcriptx.app.models.requests import (
    AnalysisRequest,
    BatchAnalysisRequest,
    PreprocessRequest,
    SpeakerIdentificationRequest,
)
from transcriptx.app.models.results import (
    AnalysisResult,
    BatchAnalysisResult,
    PreprocessResult,
    RunSummary,
    SpeakerIdentificationResult,
)

__all__ = [
    "AnalysisRequest",
    "AnalysisResult",
    "BatchAnalysisRequest",
    "BatchAnalysisResult",
    "PreprocessRequest",
    "PreprocessResult",
    "SpeakerIdentificationRequest",
    "SpeakerIdentificationResult",
    "RunSummary",
    "TranscriptMetadata",
    "ValidationError",
    "DependencyError",
    "PathConfigError",
    "WorkflowExecutionError",
    "ModuleExecutionError",
    "ArtifactReadError",
]
