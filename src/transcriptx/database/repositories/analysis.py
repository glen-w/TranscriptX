"""
Repository classes for TranscriptX database operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func

from transcriptx.core.utils.logger import get_logger
from ..models import AnalysisResult

logger = get_logger()


from .base import BaseRepository


class AnalysisRepository(BaseRepository):
    """
    Repository for analysis result database operations.

    This repository provides methods for:
    - Storing analysis results
    - Retrieving analysis results by type
    - Managing analysis status and metadata
    - Querying analysis performance metrics
    """

    def create_analysis_result(
        self,
        conversation_id: int,
        analysis_type: str,
        results_data: Dict[str, Any],
        summary_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        analysis_config: Optional[Dict[str, Any]] = None,
        processing_time_seconds: Optional[float] = None,
        memory_usage_mb: Optional[float] = None,
        status: str = "completed",
        error_message: Optional[str] = None,
    ) -> AnalysisResult:
        """
        Create or update an analysis result.

        If a result already exists for this conversation and analysis type,
        it will be updated instead of creating a new one.

        Args:
            conversation_id: Conversation ID
            analysis_type: Type of analysis (sentiment, topic_modeling, etc.)
            results_data: Complete analysis results
            summary_data: Summary statistics
            metadata: Additional metadata
            analysis_config: Analysis configuration used
            processing_time_seconds: Processing time
            memory_usage_mb: Memory usage
            status: Analysis status
            error_message: Error message if failed

        Returns:
            Created or updated analysis result instance
        """
        try:
            # Check if result already exists
            existing_result = self.get_analysis_result(conversation_id, analysis_type)

            if existing_result:
                # Update existing result
                existing_result.results_data = results_data
                existing_result.summary_data = summary_data or {}
                existing_result.analysis_metadata = metadata or {}
                existing_result.analysis_config = analysis_config or {}
                existing_result.processing_time_seconds = processing_time_seconds
                existing_result.memory_usage_mb = memory_usage_mb
                existing_result.status = status
                existing_result.error_message = error_message
                existing_result.updated_at = datetime.utcnow()

                self.session.commit()

                logger.info(
                    f"✅ Updated analysis result: {analysis_type} for conversation {conversation_id}"
                )
                return existing_result
            else:
                # Create new result
                analysis_result = AnalysisResult(
                    conversation_id=conversation_id,
                    analysis_type=analysis_type,
                    results_data=results_data,
                    summary_data=summary_data or {},
                    analysis_metadata=metadata or {},
                    analysis_config=analysis_config or {},
                    processing_time_seconds=processing_time_seconds,
                    memory_usage_mb=memory_usage_mb,
                    status=status,
                    error_message=error_message,
                )

                self.session.add(analysis_result)
                self.session.commit()

                logger.info(
                    f"✅ Created analysis result: {analysis_type} for conversation {conversation_id}"
                )
                return analysis_result

        except Exception as e:
            self.session.rollback()
            self._handle_error("create_analysis_result", e)

    def get_analysis_result(
        self, conversation_id: int, analysis_type: str
    ) -> Optional[AnalysisResult]:
        """Get analysis result by conversation and type."""
        try:
            return (
                self.session.query(AnalysisResult)
                .filter(
                    and_(
                        AnalysisResult.conversation_id == conversation_id,
                        AnalysisResult.analysis_type == analysis_type,
                    )
                )
                .first()
            )
        except Exception as e:
            self._handle_error("get_analysis_result", e)

    def get_conversation_analysis_results(
        self, conversation_id: int, status: Optional[str] = None
    ) -> List[AnalysisResult]:
        """Get all analysis results for a conversation."""
        try:
            query = self.session.query(AnalysisResult).filter(
                AnalysisResult.conversation_id == conversation_id
            )

            if status:
                query = query.filter(AnalysisResult.status == status)

            return query.order_by(AnalysisResult.created_at).all()

        except Exception as e:
            self._handle_error("get_conversation_analysis_results", e)

    def get_analysis_results_by_conversation(
        self, conversation_id: int, status: Optional[str] = None
    ) -> List[AnalysisResult]:
        """
        Get all analysis results for a conversation.

        Alias for get_conversation_analysis_results for backward compatibility.
        """
        return self.get_conversation_analysis_results(conversation_id, status)

    def update_analysis_status(
        self, analysis_result_id: int, status: str, error_message: Optional[str] = None
    ) -> Optional[AnalysisResult]:
        """Update analysis result status."""
        try:
            analysis_result = (
                self.session.query(AnalysisResult)
                .filter(AnalysisResult.id == analysis_result_id)
                .first()
            )

            if not analysis_result:
                return None

            analysis_result.status = status
            analysis_result.error_message = error_message
            analysis_result.updated_at = datetime.utcnow()

            self.session.commit()

            logger.info(f"✅ Updated analysis status: {status}")
            return analysis_result

        except Exception as e:
            self.session.rollback()
            self._handle_error("update_analysis_status", e)

    def get_analysis_performance_stats(
        self,
        analysis_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get performance statistics for analysis operations."""
        try:
            query = self.session.query(AnalysisResult)

            if analysis_type:
                query = query.filter(AnalysisResult.analysis_type == analysis_type)

            if date_from:
                query = query.filter(AnalysisResult.created_at >= date_from)

            if date_to:
                query = query.filter(AnalysisResult.created_at <= date_to)

            # Calculate statistics
            total_count = query.count()
            completed_count = query.filter(AnalysisResult.status == "completed").count()
            failed_count = query.filter(AnalysisResult.status == "failed").count()

            avg_processing_time = (
                query.filter(AnalysisResult.processing_time_seconds.isnot(None))
                .with_entities(func.avg(AnalysisResult.processing_time_seconds))
                .scalar()
            )

            avg_memory_usage = (
                query.filter(AnalysisResult.memory_usage_mb.isnot(None))
                .with_entities(func.avg(AnalysisResult.memory_usage_mb))
                .scalar()
            )

            return {
                "total_count": total_count,
                "completed_count": completed_count,
                "failed_count": failed_count,
                "success_rate": completed_count / total_count if total_count > 0 else 0,
                "avg_processing_time_seconds": avg_processing_time,
                "avg_memory_usage_mb": avg_memory_usage,
            }

        except Exception as e:
            self._handle_error("get_analysis_performance_stats", e)
