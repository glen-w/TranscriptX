"""
Repository classes for TranscriptX database operations.
"""

from sqlalchemy.orm import Session

from transcriptx.core.utils.logger import get_logger

logger = get_logger()


class BaseRepository:
    """Base repository class with common operations."""

    def __init__(self, session: Session):
        self.session = session

    def _handle_error(self, operation: str, error: Exception) -> None:
        """Handle database errors with logging."""
        logger.error(f"❌ Database error during {operation}: {error}")
        raise error
