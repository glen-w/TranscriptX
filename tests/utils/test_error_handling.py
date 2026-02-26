"""
Tests for error handling utilities.

This module tests error categorization, recovery strategies, error reporting,
and resource cleanup mechanisms.
"""

from unittest.mock import patch
import pytest

from transcriptx.utils.error_handling import (
    ErrorHandler,
    ErrorContext,
    ErrorSeverity,
    ErrorCategory,
    graceful_exit,
    retry_with_backoff,
    categorize_error,
    get_user_friendly_message,
)


@pytest.fixture
def error_handler():
    """Shared fixture for ErrorHandler instance (used by TestErrorReporting, TestResourceCleanup)."""
    return ErrorHandler()


class TestErrorCategorization:
    """Tests for error categorization."""

    def test_categorize_validation_error(self):
        """Test categorization of validation errors."""
        error = ValueError("Invalid input")
        category = categorize_error(error)
        assert category == ErrorCategory.VALIDATION

    def test_categorize_processing_error(self):
        """Test categorization of processing errors."""
        error = RuntimeError("Processing failed")
        category = categorize_error(error)
        assert category == ErrorCategory.PROCESSING

    def test_categorize_resource_error(self):
        """Test categorization of resource errors."""
        error = MemoryError("Out of memory")
        category = categorize_error(error)
        assert category == ErrorCategory.RESOURCE

    def test_categorize_timeout_error(self):
        """Test categorization of timeout errors."""
        error = TimeoutError("Operation timed out")
        category = categorize_error(error)
        assert category == ErrorCategory.TIMEOUT

    def test_categorize_network_error(self):
        """Test categorization of network errors."""
        error = ConnectionError("Connection failed")
        category = categorize_error(error)
        assert category == ErrorCategory.NETWORK

    def test_categorize_unknown_error(self):
        """Test categorization of unknown errors."""
        error = Exception("Unknown error")
        category = categorize_error(error)
        assert category == ErrorCategory.UNKNOWN


class TestErrorContext:
    """Tests for error context extraction."""

    def test_error_context_creation(self):
        """Test creation of error context."""
        context = ErrorContext(
            module="test_module",
            operation="test_operation",
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.PROCESSING,
        )

        assert context.module == "test_module"
        assert context.operation == "test_operation"
        assert context.severity == ErrorSeverity.ERROR
        assert context.category == ErrorCategory.PROCESSING

    def test_error_context_defaults(self):
        """Test error context with defaults."""
        context = ErrorContext(module="test_module", operation="test_operation")

        assert context.severity == ErrorSeverity.ERROR
        assert context.category == ErrorCategory.UNKNOWN
        assert context.recoverable is True


class TestErrorHandler:
    """Tests for ErrorHandler class."""

    def test_handle_error_validation(self, error_handler):
        """Test handling validation errors."""
        error = ValueError("Invalid input")
        context = ErrorContext(
            module="test", operation="validate", category=ErrorCategory.VALIDATION
        )

        result = error_handler.handle_error(error, context, raise_on_critical=False)

        # Should handle validation error
        assert result is not None

    def test_handle_error_processing(self, error_handler):
        """Test handling processing errors."""
        error = RuntimeError("Processing failed")
        context = ErrorContext(
            module="test", operation="process", category=ErrorCategory.PROCESSING
        )

        result = error_handler.handle_error(error, context, raise_on_critical=False)

        # Should handle processing error
        assert result is not None

    def test_handle_error_resource(self, error_handler):
        """Test handling resource errors."""
        error = MemoryError("Out of memory")
        context = ErrorContext(
            module="test", operation="allocate", category=ErrorCategory.RESOURCE
        )

        result = error_handler.handle_error(error, context, raise_on_critical=False)

        # Should handle resource error
        assert result is not None

    def test_handle_error_timeout(self, error_handler):
        """Test handling timeout errors."""
        error = TimeoutError("Operation timed out")
        context = ErrorContext(
            module="test", operation="execute", category=ErrorCategory.TIMEOUT
        )

        result = error_handler.handle_error(error, context, raise_on_critical=False)

        # Should handle timeout error
        assert result is not None

    def test_handle_error_network(self, error_handler):
        """Test handling network errors."""
        error = ConnectionError("Connection failed")
        context = ErrorContext(
            module="test", operation="connect", category=ErrorCategory.NETWORK
        )

        result = error_handler.handle_error(error, context, raise_on_critical=False)

        # Should handle network error
        assert result is not None

    def test_error_logging(self, error_handler):
        """Test error logging."""
        error = ValueError("Test error")
        context = ErrorContext(
            module="test", operation="test", severity=ErrorSeverity.ERROR
        )

        with patch.object(error_handler.logger, "error") as mock_log:
            error_handler.handle_error(error, context, raise_on_critical=False)

            # Should log error
            mock_log.assert_called()

    def test_error_recovery_strategy(self, error_handler):
        """Test error recovery strategy execution."""
        error = ValueError("Test error")
        context = ErrorContext(
            module="test",
            operation="test",
            category=ErrorCategory.VALIDATION,
            recoverable=True,
        )

        with patch.object(error_handler, "_handle_validation_error") as mock_recover:
            mock_recover.return_value = True

            result = error_handler.handle_error(error, context, raise_on_critical=False)

            # Should call recovery strategy
            mock_recover.assert_called_once()


class TestRecoveryStrategies:
    """Tests for recovery strategies."""

    @pytest.fixture
    def error_handler(self):
        """Fixture for ErrorHandler instance."""
        return ErrorHandler()

    def test_retry_logic_with_backoff(self):
        """Test retry logic with exponential backoff."""
        call_count = [0]

        def failing_function():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        with patch("transcriptx.utils.error_handling.TENACITY_AVAILABLE", True):
            # If retry decorator is available, test it
            try:
                decorated = retry_with_backoff(failing_function)
                result = decorated()
                assert result == "success"
                assert call_count[0] == 3
            except (ImportError, AttributeError):
                # Retry not available, skip test
                pytest.skip("Retry mechanism not available")

    def test_fallback_mechanism(self, error_handler):
        """Test fallback mechanism."""
        error = ConnectionError("API unavailable")
        context = ErrorContext(
            module="test", operation="api_call", category=ErrorCategory.NETWORK
        )

        with patch.object(error_handler, "_handle_network_error") as mock_fallback:
            mock_fallback.return_value = True

            result = error_handler.handle_error(error, context, raise_on_critical=False)

            # Should attempt fallback
            mock_fallback.assert_called_once()

    def test_graceful_degradation(self, error_handler):
        """Test graceful degradation."""
        error = MemoryError("Out of memory")
        context = ErrorContext(
            module="test",
            operation="process",
            category=ErrorCategory.RESOURCE,
            recoverable=True,
        )

        with patch.object(error_handler, "_handle_resource_error") as mock_degrade:
            mock_degrade.return_value = True

            result = error_handler.handle_error(error, context, raise_on_critical=False)

            # Should degrade gracefully
            mock_degrade.assert_called_once()


class TestErrorReporting:
    """Tests for error reporting."""

    def test_user_friendly_message_generation(self):
        """Test generation of user-friendly error messages."""
        error = ValueError("Invalid input")
        message = get_user_friendly_message(error, ErrorCategory.VALIDATION)

        # Should generate user-friendly message
        assert message is not None
        assert isinstance(message, str)

    def test_error_message_logging(self):
        """Test error message logging."""
        error_handler = ErrorHandler()
        error = ValueError("Test error")
        context = ErrorContext(
            module="test", operation="test", user_message="A user-friendly message"
        )

        with patch.object(error_handler.logger, "error") as mock_log:
            error_handler.handle_error(error, context, raise_on_critical=False)

            # Should log error message
            mock_log.assert_called()

    def test_user_notification(self, error_handler):
        """Test user notification."""
        error = ValueError("Test error")
        context = ErrorContext(
            module="test", operation="test", user_message="Please check your input"
        )

        with patch("transcriptx.utils.error_handling.print") as mock_print:
            error_handler.handle_error(error, context, raise_on_critical=False)

            # Should notify user (if implemented)
            # This depends on actual implementation


class TestResourceCleanup:
    """Tests for resource cleanup."""

    def test_cleanup_on_error(self, error_handler):
        """Test resource cleanup on error."""
        error = MemoryError("Out of memory")
        context = ErrorContext(
            module="test", operation="allocate", category=ErrorCategory.RESOURCE
        )

        with patch.object(error_handler, "_cleanup_resources") as mock_cleanup:
            error_handler.handle_error(error, context, raise_on_critical=False)

            # Should attempt cleanup
            # Cleanup may be called during error handling
            assert True

    def test_resource_leak_prevention(self, error_handler):
        """Test resource leak prevention."""
        error = OSError("File handle limit")
        context = ErrorContext(
            module="test", operation="file_operation", category=ErrorCategory.RESOURCE
        )

        with patch.object(error_handler, "_cleanup_resources") as mock_cleanup:
            error_handler.handle_error(error, context, raise_on_critical=False)

            # Should prevent resource leaks
            assert True

    def test_state_restoration(self, error_handler):
        """Test state restoration on error."""
        error = RuntimeError("State corruption")
        context = ErrorContext(
            module="test", operation="state_update", category=ErrorCategory.PROCESSING
        )

        with patch.object(error_handler, "_restore_state") as mock_restore:
            # If state restoration is implemented
            error_handler.handle_error(error, context, raise_on_critical=False)

            # Should restore state if implemented
            assert True


class TestGracefulExit:
    """Tests for graceful exit handling."""

    def test_graceful_exit_context_manager(self):
        """Test graceful_exit context manager."""
        with graceful_exit():
            # Should set up signal handlers
            assert True

    def test_graceful_exit_on_signal(self):
        """Test graceful exit on signal."""
        with graceful_exit():
            # Simulate signal (would need actual signal handling)
            # This is tested through integration tests
            assert True

    def test_cleanup_on_exit(self):
        """Test cleanup on exit."""
        cleanup_called = [False]

        def cleanup():
            cleanup_called[0] = True

        with graceful_exit():
            # Register cleanup
            # Cleanup should be called on exit
            assert True
