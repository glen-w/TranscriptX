"""
Database integration pipeline for TranscriptX.

This module provides the DatabaseIntegrationPipeline class that orchestrates
the complete process of extracting speaker data from analysis results and
storing it in the database.
"""

import logging
from typing import Any, Dict, List

from ..data_extraction import (
    SentimentDataExtractor,
    EmotionDataExtractor,
    TopicDataExtractor,
    EntityDataExtractor,
    TicDataExtractor,
    SemanticDataExtractor,
    InteractionDataExtractor,
    PerformanceDataExtractor,
)
from .profile_aggregator import SpeakerProfileAggregator
from .persistence_service import PersistenceService
from .error_handler import IntegrationErrorHandler

logger = logging.getLogger(__name__)


class DatabaseIntegrationPipeline:
    """
    Main database integration pipeline for TranscriptX.

    This pipeline orchestrates the complete process of extracting speaker-level
    data from analysis results and storing it in the database. It coordinates
    data extraction, validation, transformation, and persistence.
    """

    def __init__(self, database_session=None):
        """
        Initialize the database integration pipeline.

        Args:
            database_session: SQLAlchemy database session
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize extractors
        self.extractors = {
            "sentiment": SentimentDataExtractor(),
            "emotion": EmotionDataExtractor(),
            "topic": TopicDataExtractor(),
            "entity": EntityDataExtractor(),
            "tic": TicDataExtractor(),
            "semantic": SemanticDataExtractor(),
            "interaction": InteractionDataExtractor(),
            "performance": PerformanceDataExtractor(),
        }

        # Initialize services
        self.profile_aggregator = SpeakerProfileAggregator()
        self.persistence_service = PersistenceService(database_session)
        self.error_handler = IntegrationErrorHandler()

        self.logger.info("Database integration pipeline initialized")

    def process_analysis_results(
        self,
        analysis_results: Dict[str, Any],
        conversation_id: int,
        speaker_ids: List[int],
    ) -> Dict[str, Any]:
        """
        Process analysis results and store speaker data in database.

        Args:
            analysis_results: Complete analysis results for the conversation
            conversation_id: ID of the conversation
            speaker_ids: List of speaker IDs to process

        Returns:
            Dictionary containing processing results and statistics

        Raises:
            ValueError: If required data is missing
            IntegrationError: If processing fails
        """
        self.logger.info(
            f"Processing analysis results for conversation {conversation_id}"
        )

        try:
            # Validate input data
            self._validate_input_data(analysis_results, conversation_id, speaker_ids)

            # Process each speaker
            processing_results = {
                "conversation_id": conversation_id,
                "speakers_processed": 0,
                "speakers_failed": 0,
                "errors": [],
                "speaker_results": {},
            }

            for speaker_id in speaker_ids:
                try:
                    self.logger.info(f"Processing speaker {speaker_id}")
                    speaker_result = self._process_speaker_data(
                        analysis_results, conversation_id, speaker_id
                    )
                    processing_results["speaker_results"][speaker_id] = speaker_result
                    processing_results["speakers_processed"] += 1

                except Exception as e:
                    error_msg = f"Failed to process speaker {speaker_id}: {str(e)}"
                    self.logger.error(error_msg)
                    processing_results["errors"].append(error_msg)
                    processing_results["speakers_failed"] += 1

            # Aggregate speaker profiles
            if processing_results["speakers_processed"] > 0:
                self.logger.info("Aggregating speaker profiles")
                self.profile_aggregator.aggregate_profiles(conversation_id)

            # Log processing summary
            self.logger.info(
                f"Processing complete: {processing_results['speakers_processed']} "
                f"speakers processed, {processing_results['speakers_failed']} failed"
            )

            return processing_results

        except Exception as e:
            self.error_handler.handle_error(e, "process_analysis_results")
            raise

    def _process_speaker_data(
        self, analysis_results: Dict[str, Any], conversation_id: int, speaker_id: int
    ) -> Dict[str, Any]:
        """
        Process data for a single speaker.

        Args:
            analysis_results: Complete analysis results
            conversation_id: ID of the conversation
            speaker_id: ID of the speaker to process

        Returns:
            Dictionary containing processing results for the speaker
        """
        speaker_result = {
            "speaker_id": speaker_id,
            "analysis_types_processed": [],
            "analysis_types_failed": [],
            "errors": [],
        }

        # Process each analysis type
        for analysis_type, extractor in self.extractors.items():
            try:
                self.logger.debug(
                    f"Processing {analysis_type} for speaker {speaker_id}"
                )

                # Extract speaker data
                extracted_data = extractor.process_analysis_results(
                    analysis_results, speaker_id
                )

                # Store data in database
                self.persistence_service.store_speaker_data(
                    analysis_type, speaker_id, extracted_data
                )

                speaker_result["analysis_types_processed"].append(analysis_type)

            except Exception as e:
                error_msg = f"Failed to process {analysis_type} for speaker {speaker_id}: {str(e)}"
                self.logger.error(error_msg)
                speaker_result["analysis_types_failed"].append(analysis_type)
                speaker_result["errors"].append(error_msg)

        return speaker_result

    def _validate_input_data(
        self,
        analysis_results: Dict[str, Any],
        conversation_id: int,
        speaker_ids: List[int],
    ) -> None:
        """
        Validate input data for processing.

        Args:
            analysis_results: Analysis results to validate
            conversation_id: Conversation ID to validate
            speaker_ids: Speaker IDs to validate

        Raises:
            ValueError: If validation fails
        """
        if not isinstance(analysis_results, dict):
            raise ValueError("Analysis results must be a dictionary")

        if not isinstance(conversation_id, int) or conversation_id <= 0:
            raise ValueError("Conversation ID must be a positive integer")

        if not isinstance(speaker_ids, list) or not speaker_ids:
            raise ValueError("Speaker IDs must be a non-empty list")

        for speaker_id in speaker_ids:
            if not isinstance(speaker_id, int) or speaker_id <= 0:
                raise ValueError(f"Invalid speaker ID: {speaker_id}")

    def get_processing_status(self, conversation_id: int) -> Dict[str, Any]:
        """
        Get processing status for a conversation.

        Args:
            conversation_id: ID of the conversation

        Returns:
            Dictionary containing processing status
        """
        try:
            return self.persistence_service.get_processing_status(conversation_id)
        except Exception as e:
            self.error_handler.handle_error(e, "get_processing_status")
            raise

    def reprocess_speaker(
        self, conversation_id: int, speaker_id: int, analysis_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Reprocess data for a specific speaker.

        Args:
            conversation_id: ID of the conversation
            speaker_id: ID of the speaker to reprocess
            analysis_results: Analysis results to process

        Returns:
            Dictionary containing reprocessing results
        """
        self.logger.info(
            f"Reprocessing speaker {speaker_id} for conversation {conversation_id}"
        )

        try:
            # Clear existing data for the speaker
            self.persistence_service.clear_speaker_data(conversation_id, speaker_id)

            # Reprocess the speaker
            result = self._process_speaker_data(
                analysis_results, conversation_id, speaker_id
            )

            # Update speaker profile
            self.profile_aggregator.aggregate_speaker_profile(speaker_id)

            return result

        except Exception as e:
            self.error_handler.handle_error(e, "reprocess_speaker")
            raise

    def get_extractor_status(self) -> Dict[str, Any]:
        """
        Get status of all data extractors.

        Returns:
            Dictionary containing extractor status information
        """
        status = {}

        for analysis_type, extractor in self.extractors.items():
            status[analysis_type] = {
                "class_name": extractor.__class__.__name__,
                "available": True,
                "version": getattr(extractor, "version", "1.0"),
            }

        return status
