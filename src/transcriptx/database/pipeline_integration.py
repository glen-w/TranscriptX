"""
Pipeline Integration for TranscriptX Database.

This module provides integration between the analysis pipeline and the database,
automatically storing transcript data, speakers, and analysis results during
processing. It hooks into the existing pipeline to provide persistent storage
without disrupting the current workflow.

Key Features:
- Automatic transcript storage during analysis
- Speaker profile creation and tracking
- Analysis result storage
- Cross-session speaker identification
- Pipeline status tracking
- Batch processing support

The integration is designed to be transparent to existing pipeline modules
while providing comprehensive database storage capabilities.
"""

import time
from typing import Any, Dict, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.database.transcript_manager import TranscriptManager
from transcriptx.database import init_database

logger = get_logger()


class PipelineDatabaseIntegration:
    """
    Database integration for the analysis pipeline.

    This class provides seamless integration between the analysis pipeline
    and the database, automatically storing transcript data and analysis
    results during processing.
    """

    def __init__(self, enable_storage: bool = True):
        """
        Initialize the pipeline database integration.

        Args:
            enable_storage: Whether to enable database storage (default: True)
        """
        self.enable_storage = enable_storage
        self.transcript_manager = None
        self.current_conversation = None
        self.current_speakers = []

        if self.enable_storage:
            try:
                # Initialize database if not already done
                init_database()
                self.transcript_manager = TranscriptManager()
                logger.info("✅ Database integration initialized")
            except Exception as e:
                logger.warning(f"⚠️ Database integration failed to initialize: {e}")
                self.enable_storage = False

    def start_transcript_processing(
        self,
        transcript_path: str,
        analysis_config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        Start processing a transcript and store it in the database.

        Args:
            transcript_path: Path to the transcript file
            analysis_config: Analysis configuration
            metadata: Additional metadata

        Returns:
            Conversation ID if successful, None otherwise
        """
        if not self.enable_storage or not self.transcript_manager:
            return None

        try:
            logger.info(
                f"🔧 Starting database storage for transcript: {transcript_path}"
            )

            # Check if conversation already exists
            existing_conversation = (
                self.transcript_manager.get_conversation_by_transcript_path(
                    transcript_path
                )
            )
            if existing_conversation:
                logger.info(
                    f"📋 Found existing conversation for transcript: {existing_conversation.id}"
                )
                self.current_conversation = existing_conversation
                self.current_speakers = (
                    self.transcript_manager.get_speakers_for_conversation(
                        existing_conversation.id
                    )
                )
                return existing_conversation.id

            # Store transcript in database
            conversation, speakers = self.transcript_manager.store_transcript(
                transcript_path=transcript_path,
                analysis_config=analysis_config,
                metadata=metadata,
            )

            self.current_conversation = conversation
            self.current_speakers = speakers

            logger.info(f"✅ Stored transcript in database: {conversation.id}")
            return conversation.id

        except Exception as e:
            logger.error(f"❌ Failed to start transcript processing: {e}")
            return None

    def store_analysis_result(
        self,
        analysis_type: str,
        results_data: Dict[str, Any],
        summary_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        processing_time: Optional[float] = None,
    ) -> Optional[Any]:
        """
        Store analysis results in the database.

        Args:
            analysis_type: Type of analysis (sentiment, emotion, etc.)
            results_data: Complete analysis results
            summary_data: Summary statistics
            metadata: Additional metadata
            processing_time: Processing time in seconds

        Returns:
            Analysis result instance if successful, None otherwise
        """
        if (
            not self.enable_storage
            or not self.transcript_manager
            or not self.current_conversation
        ):
            return None

        try:
            analysis_result = self.transcript_manager.store_analysis_result(
                conversation_id=self.current_conversation.id,
                analysis_type=analysis_type,
                results_data=results_data,
                summary_data=summary_data,
                metadata=metadata,
                processing_time=processing_time,
            )

            logger.info(f"✅ Stored {analysis_type} analysis result")
            return analysis_result

        except Exception as e:
            logger.error(f"❌ Failed to store {analysis_type} analysis result: {e}")
            return None

    def update_analysis_status(
        self, status: str, error_message: Optional[str] = None
    ) -> None:
        """Update the analysis status of the current conversation."""
        if (
            not self.enable_storage
            or not self.transcript_manager
            or not self.current_conversation
        ):
            return

        try:
            self.transcript_manager.update_conversation_analysis_status(
                conversation_id=self.current_conversation.id,
                status=status,
                error_message=error_message,
            )

            logger.info(f"✅ Updated analysis status to: {status}")

        except Exception as e:
            logger.error(f"❌ Failed to update analysis status: {e}")

    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get summary of the current conversation."""
        if (
            not self.enable_storage
            or not self.transcript_manager
            or not self.current_conversation
        ):
            return {}

        try:
            return self.transcript_manager.get_conversation_summary(
                self.current_conversation.id
            )
        except Exception as e:
            logger.error(f"❌ Failed to get conversation summary: {e}")
            return {}

    def finish_processing(self) -> Dict[str, Any]:
        """
        Finish processing and return summary.

        Returns:
            Dictionary with processing summary
        """
        if (
            not self.enable_storage
            or not self.transcript_manager
            or not self.current_conversation
        ):
            return {"database_storage": False}

        try:
            # Update status to completed
            self.update_analysis_status("completed")

            # Get final summary
            summary = self.get_conversation_summary()

            # Reset current state
            conversation_id = self.current_conversation.id
            self.current_conversation = None
            self.current_speakers = []

            logger.info(f"✅ Finished processing conversation: {conversation_id}")

            return {
                "database_storage": True,
                "conversation_id": conversation_id,
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"❌ Failed to finish processing: {e}")
            return {"database_storage": False, "error": str(e)}

    def close(self):
        """Close the database integration."""
        if self.transcript_manager:
            self.transcript_manager.close()


# Global instance for pipeline integration
_pipeline_integration = None


def get_pipeline_integration(
    enable_storage: bool = True,
) -> PipelineDatabaseIntegration:
    """
    Get the global pipeline integration instance.

    Args:
        enable_storage: Whether to enable database storage

    Returns:
        PipelineDatabaseIntegration instance
    """
    global _pipeline_integration

    if _pipeline_integration is None:
        _pipeline_integration = PipelineDatabaseIntegration(
            enable_storage=enable_storage
        )

    return _pipeline_integration


def reset_pipeline_integration():
    """Reset the global pipeline integration instance."""
    global _pipeline_integration

    if _pipeline_integration:
        _pipeline_integration.close()
        _pipeline_integration = None


# Decorator for pipeline modules to automatically store results
def with_database_storage(analysis_type: str):
    """
    Decorator to automatically store analysis results in the database.

    Args:
        analysis_type: Type of analysis being performed

    Returns:
        Decorated function that stores results in database
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get pipeline integration
            integration = get_pipeline_integration()

            # Record start time
            start_time = time.time()

            try:
                # Call the original function
                result = func(*args, **kwargs)

                # Calculate processing time
                processing_time = time.time() - start_time

                # Store results in database if available
                if integration.enable_storage and integration.current_conversation:
                    try:
                        # Extract results data from the function result
                        results_data = (
                            result if isinstance(result, dict) else {"result": result}
                        )

                        integration.store_analysis_result(
                            analysis_type=analysis_type,
                            results_data=results_data,
                            processing_time=processing_time,
                        )
                    except Exception as e:
                        logger.warning(
                            f"⚠️ Failed to store {analysis_type} results in database: {e}"
                        )

                return result

            except Exception as e:
                # Update status to failed
                integration.update_analysis_status("failed", str(e))
                raise

        return wrapper

    return decorator
