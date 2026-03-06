"""
Database integration services for TranscriptX.

This module provides services to integrate analysis results with the database,
including data extraction, profile aggregation, and persistence.

Available Components:
- DatabaseIntegrationPipeline: Main pipeline for processing analysis results
- ProfileAggregator: Logic to aggregate data into comprehensive speaker profiles
- PersistenceService: Service for storing data in the database
- ErrorHandler: Error handling and recovery for integration processes
"""

from .database_pipeline import DatabaseIntegrationPipeline
from .profile_aggregator import SpeakerProfileAggregator
from .persistence_service import PersistenceService
from .error_handler import IntegrationErrorHandler

__all__ = [
    "DatabaseIntegrationPipeline",
    "SpeakerProfileAggregator",
    "PersistenceService",
    "IntegrationErrorHandler",
]
