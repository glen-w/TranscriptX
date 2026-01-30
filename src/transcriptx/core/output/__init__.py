"""
Output services and utilities for TranscriptX.

This module provides centralized output handling for all analysis modules.
"""

from .output_service import OutputService, create_output_service

__all__ = [
    "OutputService",
    "create_output_service",
]
