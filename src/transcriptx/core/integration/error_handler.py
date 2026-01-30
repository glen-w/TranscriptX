"""
Error handler for TranscriptX integration processes.

This module provides the IntegrationErrorHandler class that handles errors
during data integration processes and provides recovery mechanisms.
"""

import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    """Custom exception for integration errors."""

    def __init__(
        self,
        message: str,
        error_type: str = "general",
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the integration error.

        Args:
            message: Error message
            error_type: Type of error
            context: Additional context information
        """
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.context = context or {}
        self.timestamp = datetime.now()


class IntegrationErrorHandler:
    """
    Error handler for integration processes.

    This class provides comprehensive error handling and recovery mechanisms
    for data integration processes in TranscriptX.
    """

    def __init__(self):
        """Initialize the error handler."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.error_history = []
        self.recovery_strategies = {
            "data_validation": self._handle_data_validation_error,
            "database_connection": self._handle_database_connection_error,
            "data_extraction": self._handle_data_extraction_error,
            "profile_aggregation": self._handle_profile_aggregation_error,
            "persistence": self._handle_persistence_error,
        }

    def handle_error(
        self, error: Exception, context: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Handle an error during integration process.

        Args:
            error: The exception that occurred
            context: Context where the error occurred

        Returns:
            Dictionary containing error handling results
        """
        error_info = {
            "timestamp": datetime.now(),
            "context": context,
            "error_type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
            "handled": False,
            "recovery_attempted": False,
            "recovery_successful": False,
        }

        self.logger.error(f"Integration error in {context}: {str(error)}")

        # Determine error type and apply recovery strategy
        error_type = self._classify_error(error)
        error_info["error_type"] = error_type

        if error_type in self.recovery_strategies:
            error_info["recovery_attempted"] = True
            try:
                recovery_result = self.recovery_strategies[error_type](error, context)
                error_info["recovery_successful"] = recovery_result.get(
                    "success", False
                )
                error_info["recovery_message"] = recovery_result.get("message", "")
            except Exception as recovery_error:
                self.logger.error(f"Recovery failed: {str(recovery_error)}")
                error_info["recovery_message"] = (
                    f"Recovery failed: {str(recovery_error)}"
                )
        else:
            error_info["recovery_message"] = (
                f"No recovery strategy for error type: {error_type}"
            )

        # Store error in history
        self.error_history.append(error_info)

        # Limit history size
        if len(self.error_history) > 100:
            self.error_history = self.error_history[-50:]

        error_info["handled"] = True
        return error_info

    def _classify_error(self, error: Exception) -> str:
        """
        Classify the type of error for appropriate handling.

        Args:
            error: The exception to classify

        Returns:
            Error type string
        """
        error_message = str(error).lower()

        if any(
            keyword in error_message
            for keyword in ["validation", "validate", "invalid"]
        ):
            return "data_validation"
        elif any(
            keyword in error_message for keyword in ["connection", "database", "sql"]
        ):
            return "database_connection"
        elif any(
            keyword in error_message for keyword in ["extract", "extraction", "parse"]
        ):
            return "data_extraction"
        elif any(
            keyword in error_message
            for keyword in ["aggregate", "aggregation", "profile"]
        ):
            return "profile_aggregation"
        elif any(
            keyword in error_message
            for keyword in ["persist", "store", "save", "commit"]
        ):
            return "persistence"
        else:
            return "general"

    def _handle_data_validation_error(
        self, error: Exception, context: str
    ) -> Dict[str, Any]:
        """
        Handle data validation errors.

        Args:
            error: The validation error
            context: Context where error occurred

        Returns:
            Recovery result dictionary
        """
        self.logger.warning(f"Data validation error in {context}: {str(error)}")

        # For validation errors, we can often continue with default values
        return {
            "success": True,
            "message": "Using default values for validation errors",
            "action": "continue_with_defaults",
        }

    def _handle_database_connection_error(
        self, error: Exception, context: str
    ) -> Dict[str, Any]:
        """
        Handle database connection errors.

        Args:
            error: The connection error
            context: Context where error occurred

        Returns:
            Recovery result dictionary
        """
        self.logger.error(f"Database connection error in {context}: {str(error)}")

        # Connection errors are critical and usually require manual intervention
        return {
            "success": False,
            "message": "Database connection error requires manual intervention",
            "action": "manual_intervention_required",
        }

    def _handle_data_extraction_error(
        self, error: Exception, context: str
    ) -> Dict[str, Any]:
        """
        Handle data extraction errors.

        Args:
            error: The extraction error
            context: Context where error occurred

        Returns:
            Recovery result dictionary
        """
        self.logger.warning(f"Data extraction error in {context}: {str(error)}")

        # For extraction errors, we can skip the problematic data
        return {
            "success": True,
            "message": "Skipping problematic data and continuing",
            "action": "skip_and_continue",
        }

    def _handle_profile_aggregation_error(
        self, error: Exception, context: str
    ) -> Dict[str, Any]:
        """
        Handle profile aggregation errors.

        Args:
            error: The aggregation error
            context: Context where error occurred

        Returns:
            Recovery result dictionary
        """
        self.logger.warning(f"Profile aggregation error in {context}: {str(error)}")

        # For aggregation errors, we can use partial data
        return {
            "success": True,
            "message": "Using partial data for aggregation",
            "action": "use_partial_data",
        }

    def _handle_persistence_error(
        self, error: Exception, context: str
    ) -> Dict[str, Any]:
        """
        Handle persistence errors.

        Args:
            error: The persistence error
            context: Context where error occurred

        Returns:
            Recovery result dictionary
        """
        self.logger.error(f"Persistence error in {context}: {str(error)}")

        # Persistence errors are critical but we can retry
        return {
            "success": False,
            "message": "Persistence error - retry recommended",
            "action": "retry_operation",
        }

    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary of recent errors.

        Args:
            hours: Number of hours to look back

        Returns:
            Error summary dictionary
        """
        cutoff_time = datetime.now().replace(hour=datetime.now().hour - hours)

        recent_errors = [
            error for error in self.error_history if error["timestamp"] > cutoff_time
        ]

        error_types = {}
        contexts = {}

        for error in recent_errors:
            error_type = error["error_type"]
            context = error["context"]

            error_types[error_type] = error_types.get(error_type, 0) + 1
            contexts[context] = contexts.get(context, 0) + 1

        return {
            "total_errors": len(recent_errors),
            "error_types": error_types,
            "contexts": contexts,
            "recovery_success_rate": self._calculate_recovery_success_rate(
                recent_errors
            ),
            "most_common_error": (
                max(error_types.items(), key=lambda x: x[1])[0] if error_types else None
            ),
            "most_common_context": (
                max(contexts.items(), key=lambda x: x[1])[0] if contexts else None
            ),
        }

    def _calculate_recovery_success_rate(self, errors: List[Dict[str, Any]]) -> float:
        """
        Calculate the success rate of recovery attempts.

        Args:
            errors: List of error dictionaries

        Returns:
            Success rate as a float between 0 and 1
        """
        if not errors:
            return 0.0

        recovery_attempts = [e for e in errors if e.get("recovery_attempted", False)]

        if not recovery_attempts:
            return 0.0

        successful_recoveries = [
            e for e in recovery_attempts if e.get("recovery_successful", False)
        ]

        return len(successful_recoveries) / len(recovery_attempts)

    def clear_error_history(self) -> None:
        """Clear the error history."""
        self.error_history.clear()
        self.logger.info("Error history cleared")

    def get_recommendations(self) -> List[str]:
        """
        Get recommendations based on error patterns.

        Returns:
            List of recommendations
        """
        recommendations = []
        summary = self.get_error_summary()

        if summary["total_errors"] > 10:
            recommendations.append("High error rate detected - review system stability")

        if summary["recovery_success_rate"] < 0.5:
            recommendations.append("Low recovery success rate - improve error handling")

        most_common_error = summary["most_common_error"]
        if most_common_error == "database_connection":
            recommendations.append(
                "Frequent database connection issues - check database health"
            )
        elif most_common_error == "data_validation":
            recommendations.append("Frequent validation errors - review data quality")
        elif most_common_error == "persistence":
            recommendations.append(
                "Frequent persistence errors - check database permissions"
            )

        return recommendations
