"""
Database backend for TranscriptX.

This package provides a robust, extensible database backend for TranscriptX,
supporting speaker profiling, conversation analysis, and long-term data persistence.

Key Features:
- SQLAlchemy-based ORM with support for multiple database backends
- Speaker profiling and behavioral fingerprinting
- Conversation and session management
- Analysis results storage and retrieval
- Migration system for schema evolution
- Caching layer for performance optimization

The database system is designed to be:
- Extensible: Easy to add new models and relationships
- Future-proof: Supports schema migrations and versioning
- Performant: Includes caching and query optimization
- Flexible: Supports multiple database backends (SQLite, PostgreSQL, etc.)
"""

from .models import (
    Base,
    Speaker,
    Conversation,
    Session,
    AnalysisResult,
    SpeakerProfile,
    BehavioralFingerprint,
    EntityMention,
    TopicModel,
    SentimentAnalysis,
    EmotionAnalysis,
    InteractionPattern,
    SpeakerStats,
    ConversationMetadata,
    SpeakerCluster,
    SpeakerClusterMember,
    SpeakerLink,
    SpeakerSession,
    PatternEvolution,
    BehavioralAnomaly,
    TranscriptFile,
    TranscriptSpeaker,
    TranscriptSegment,
    TranscriptSentence,
    SpeakerVocabularyWord,
    SpeakerResolutionEvent,
    FileEntity,
    FileArtifact,
    FileProcessingEvent,
    FilePreprocessingRecord,
    FileRenameHistory,
    PipelineRun,
    ModuleRun,
    ArtifactIndex,
    PerformanceSpan,
)
from .database import (
    DatabaseManager,
    get_database_url,
    get_database_manager,
    init_database,
    get_session,
)
from .migrations import (
    run_migrations,
    create_migration,
    get_migration_manager,
    check_migration_status,
    get_migration_history,
)
from .repositories import (
    SpeakerRepository,
    ConversationRepository,
    AnalysisRepository,
    ProfileRepository,
    TranscriptFileRepository,
    TranscriptSegmentRepository,
    FileEntityRepository,
    FileArtifactRepository,
    FileProcessingEventRepository,
    FileHistoryRepository,
)
from .transcript_manager import TranscriptManager
from .pipeline_integration import (
    PipelineDatabaseIntegration,
    get_pipeline_integration,
    reset_pipeline_integration,
)
from .segment_storage import SegmentStorageService
from .sentence_storage import SentenceStorageService
from .vocabulary_storage import VocabularyStorageService
from .speaker_profiling import SpeakerIdentityService
from .transcript_ingestion import TranscriptIngestionService
from .transcript_adapter import TranscriptDbAdapter
from .pipeline_run_service import PipelineRunCoordinator
from .artifact_registry import ArtifactRegistry
from .export_service import TranscriptExportService
from .segment_queries import (
    get_segments_for_file,
    get_segments_for_speaker,
    search_segments_by_text,
    get_segments_in_time_range,
    get_transcript_file_by_path,
)
from .file_tracking import FileTrackingService

__all__ = [
    # Models
    "Base",
    "Speaker",
    "Conversation",
    "Session",
    "AnalysisResult",
    "SpeakerProfile",
    "BehavioralFingerprint",
    "EntityMention",
    "TopicModel",
    "SentimentAnalysis",
    "EmotionAnalysis",
    "InteractionPattern",
    "SpeakerStats",
    "ConversationMetadata",
    "SpeakerCluster",
    "SpeakerClusterMember",
    "SpeakerLink",
    "SpeakerSession",
    "PatternEvolution",
    "BehavioralAnomaly",
    "TranscriptFile",
    "TranscriptSpeaker",
    "TranscriptSegment",
    "TranscriptSentence",
    "SpeakerVocabularyWord",
    "SpeakerResolutionEvent",
    "FileEntity",
    "FileArtifact",
    "FileProcessingEvent",
    "FilePreprocessingRecord",
    "FileRenameHistory",
    "PipelineRun",
    "ModuleRun",
    "ArtifactIndex",
    "PerformanceSpan",
    # Database management
    "DatabaseManager",
    "get_database_url",
    "get_database_manager",
    "init_database",
    "get_session",
    # Migrations
    "run_migrations",
    "create_migration",
    "get_migration_manager",
    "check_migration_status",
    "get_migration_history",
    # Repositories
    "SpeakerRepository",
    "ConversationRepository",
    "AnalysisRepository",
    "ProfileRepository",
    "TranscriptFileRepository",
    "TranscriptSegmentRepository",
    "FileEntityRepository",
    "FileArtifactRepository",
    "FileProcessingEventRepository",
    "FileHistoryRepository",
    # Transcript management
    "TranscriptManager",
    "PipelineDatabaseIntegration",
    "get_pipeline_integration",
    "reset_pipeline_integration",
    # Segment storage and queries
    "SegmentStorageService",
    "SentenceStorageService",
    "VocabularyStorageService",
    "SpeakerIdentityService",
    "TranscriptIngestionService",
    "TranscriptDbAdapter",
    "PipelineRunCoordinator",
    "ArtifactRegistry",
    "TranscriptExportService",
    "get_segments_for_file",
    "get_segments_for_speaker",
    "search_segments_by_text",
    "get_segments_in_time_range",
    "get_transcript_file_by_path",
    # File tracking
    "FileTrackingService",
]
