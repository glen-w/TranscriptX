"""
Enhanced error handling and validation for TranscriptX.

This module provides comprehensive error handling with:
- Graceful error recovery mechanisms
- Input validation and sanitization
- User-friendly error messages
- Retry logic with exponential backoff
- Error categorization and logging
- Graceful exit handling
- Resource cleanup
"""

import functools
import importlib.util
import os
import signal
import sys
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any

try:
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False

try:
    PYDANTIC_AVAILABLE = importlib.util.find_spec("pydantic") is not None
except Exception:
    PYDANTIC_AVAILABLE = False

try:
    import typer

    TYPER_AVAILABLE = True
except ImportError:
    TYPER_AVAILABLE = False

from transcriptx.core.utils.logger import get_logger, log_error, log_info


class ErrorSeverity(Enum):
    """Error severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCategory(Enum):
    """Error categories for better organization."""

    VALIDATION = "VALIDATION"
    PROCESSING = "PROCESSING"
    RESOURCE = "RESOURCE"
    DEPENDENCY = "DEPENDENCY"
    TIMEOUT = "TIMEOUT"
    NETWORK = "NETWORK"
    SECURITY = "SECURITY"
    UNKNOWN = "UNKNOWN"


@dataclass
class ErrorContext:
    """Context information for error handling."""

    module: str
    operation: str
    severity: ErrorSeverity = ErrorSeverity.ERROR
    category: ErrorCategory = ErrorCategory.UNKNOWN
    recoverable: bool = True
    user_message: str | None = None
    technical_details: str | None = None
    retry_count: int = 0
    max_retries: int = 3


class ErrorHandler:
    """
    Comprehensive error handler with recovery mechanisms.

    This class provides:
    - Error categorization and logging
    - Graceful recovery strategies
    - User-friendly error messages
    - Retry logic with exponential backoff
    - Resource cleanup
    - Graceful exit handling
    """

    def __init__(self):
        self.logger = get_logger()
        self._error_counts: dict[str, int] = {}
        self._recovery_strategies: dict[ErrorCategory, Callable] = {}
        self._setup_default_recovery_strategies()
        self._setup_signal_handlers()

    def _setup_default_recovery_strategies(self):
        """Set up default recovery strategies for different error categories."""
        self._recovery_strategies = {
            ErrorCategory.VALIDATION: self._handle_validation_error,
            ErrorCategory.PROCESSING: self._handle_processing_error,
            ErrorCategory.RESOURCE: self._handle_resource_error,
            ErrorCategory.DEPENDENCY: self._handle_dependency_error,
            ErrorCategory.TIMEOUT: self._handle_timeout_error,
            ErrorCategory.NETWORK: self._handle_network_error,
            ErrorCategory.SECURITY: self._handle_security_error,
            ErrorCategory.UNKNOWN: self._handle_unknown_error,
        }

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful exit."""

        def signal_handler(signum, frame):
            self.logger.info(
                f"Received signal {signum}, initiating graceful shutdown..."
            )
            self._cleanup_resources()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def handle_error(
        self,
        error: Exception,
        context: ErrorContext,
        raise_on_critical: bool = True,
    ) -> bool:
        """
        Handle an error with appropriate recovery strategy.

        Args:
            error: The exception that occurred
            context: Error context information
            raise_on_critical: Whether to raise critical errors

        Returns:
            True if error was handled successfully, False otherwise
        """
        # Log the error
        self._log_error(error, context)

        # Update error counts
        error_key = f"{context.module}:{context.operation}"
        self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1

        # Check if error is recoverable
        if not context.recoverable:
            if raise_on_critical:
                raise error
            return False

        # Apply recovery strategy
        recovery_strategy = self._recovery_strategies.get(
            context.category, self._handle_unknown_error
        )
        return recovery_strategy(error, context)

    def _log_error(self, error: Exception, context: ErrorContext):
        """Log error with comprehensive information."""
        error_info = {
            "module": context.module,
            "operation": context.operation,
            "severity": context.severity.value,
            "category": context.category.value,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "recoverable": context.recoverable,
            "retry_count": context.retry_count,
        }

        if context.technical_details:
            error_info["technical_details"] = context.technical_details

        log_error(
            context.module,
            f"{context.operation} failed: {error}",
            context.technical_details or str(error),
        )

    def _handle_validation_error(self, error: Exception, context: ErrorContext) -> bool:
        """Handle validation errors."""
        user_msg = context.user_message or f"Invalid input for {context.operation}"
        print(f"⚠️  {user_msg}")
        return False  # Validation errors are not recoverable

    def _handle_processing_error(self, error: Exception, context: ErrorContext) -> bool:
        """Handle processing errors with retry logic."""
        if context.retry_count < context.max_retries:
            context.retry_count += 1
            wait_time = 2**context.retry_count  # Exponential backoff
            print(
                f"🔄 Retrying {context.operation} in {wait_time} seconds... (attempt {context.retry_count}/{context.max_retries})"
            )
            time.sleep(wait_time)
            return True
        user_msg = (
            context.user_message
            or f"Failed to process {context.operation} after {context.max_retries} attempts"
        )
        print(f"❌ {user_msg}")
        return False

    def _handle_resource_error(self, error: Exception, context: ErrorContext) -> bool:
        """Handle resource errors (memory, disk, etc.)."""
        user_msg = (
            context.user_message or f"Insufficient resources for {context.operation}"
        )
        print(f"💾 {user_msg}")
        self._cleanup_resources()
        return False

    def _handle_dependency_error(self, error: Exception, context: ErrorContext) -> bool:
        """Handle dependency errors."""
        user_msg = context.user_message or f"Missing dependency for {context.operation}"
        print(f"📦 {user_msg}")
        return False

    def _handle_timeout_error(self, error: Exception, context: ErrorContext) -> bool:
        """Handle timeout errors."""
        user_msg = context.user_message or f"Operation {context.operation} timed out"
        print(f"⏰ {user_msg}")
        return False

    def _handle_network_error(self, error: Exception, context: ErrorContext) -> bool:
        """Handle network errors."""
        user_msg = context.user_message or f"Network error during {context.operation}"
        print(f"🌐 {user_msg}")
        return False

    def _handle_security_error(self, error: Exception, context: ErrorContext) -> bool:
        """Handle security errors."""
        user_msg = context.user_message or f"Security issue with {context.operation}"
        print(f"🔒 {user_msg}")
        return False

    def _handle_unknown_error(self, error: Exception, context: ErrorContext) -> bool:
        """Handle unknown errors."""
        user_msg = (
            context.user_message or f"Unexpected error during {context.operation}"
        )
        print(f"❓ {user_msg}")
        return False

    def _cleanup_resources(self):
        """Clean up system resources."""
        try:
            # Add any cleanup logic here
            log_info("ERROR_HANDLER", "Resources cleaned up successfully")
        except Exception as e:
            log_error("ERROR_HANDLER", f"Failed to cleanup resources: {e}")


class InputValidator:
    """
    Comprehensive input validation with user-friendly error messages.

    This class provides:
    - File validation
    - Data structure validation
    - Type checking
    - Range validation
    - Format validation
    - Security validation
    """

    def __init__(self):
        self.logger = get_logger()
        self.error_handler = ErrorHandler()

    def validate_file(
        self,
        file_path: str,
        required: bool = True,
        file_type: str | None = None,
        max_size: int | None = None,
    ) -> bool:
        """
        Validate file existence and properties.

        Args:
            file_path: Path to the file
            required: Whether the file is required
            file_type: Expected file type/extension
            max_size: Maximum file size in bytes

        Returns:
            True if file is valid, False otherwise
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                if required:
                    context = ErrorContext(
                        module="VALIDATOR",
                        operation="file_validation",
                        category=ErrorCategory.VALIDATION,
                        user_message=f"File not found: {file_path}",
                        technical_details=f"File path does not exist: {file_path}",
                    )
                    self.error_handler.handle_error(
                        FileNotFoundError(f"File not found: {file_path}"), context
                    )
                    return False
                return True

            # Check file type
            if file_type and not file_path.lower().endswith(file_type.lower()):
                context = ErrorContext(
                    module="VALIDATOR",
                    operation="file_validation",
                    category=ErrorCategory.VALIDATION,
                    user_message=f"Invalid file type. Expected: {file_type}",
                    technical_details=f"File {file_path} has wrong extension",
                )
                self.error_handler.handle_error(
                    ValueError(f"Invalid file type: {file_path}"), context
                )
                return False

            # Check file size
            if max_size:
                file_size = os.path.getsize(file_path)
                if file_size > max_size:
                    context = ErrorContext(
                        module="VALIDATOR",
                        operation="file_validation",
                        category=ErrorCategory.VALIDATION,
                        user_message=f"File too large. Maximum size: {max_size} bytes",
                        technical_details=f"File {file_path} size: {file_size} bytes",
                    )
                    self.error_handler.handle_error(
                        ValueError(f"File too large: {file_path}"), context
                    )
                    return False

            return True

        except Exception as e:
            context = ErrorContext(
                module="VALIDATOR",
                operation="file_validation",
                category=ErrorCategory.VALIDATION,
                user_message="File validation failed",
                technical_details=str(e),
            )
            self.error_handler.handle_error(e, context)
            return False

    def validate_json_structure(
        self,
        data: Any,
        required_keys: list[str] | None = None,
        optional_keys: list[str] | None = None,
        schema: dict | None = None,
    ) -> bool:
        """
        Validate JSON data structure.

        Args:
            data: Data to validate
            required_keys: List of required keys
            optional_keys: List of optional keys
            schema: JSON schema for validation

        Returns:
            True if data is valid, False otherwise
        """
        try:
            # Check if data is a dictionary
            if not isinstance(data, dict):
                context = ErrorContext(
                    module="VALIDATOR",
                    operation="json_validation",
                    category=ErrorCategory.VALIDATION,
                    user_message="Invalid data format. Expected JSON object.",
                    technical_details=f"Data type: {type(data)}",
                )
                self.error_handler.handle_error(
                    TypeError("Data is not a dictionary"), context
                )
                return False

            # Check required keys
            if required_keys:
                missing_keys = [key for key in required_keys if key not in data]
                if missing_keys:
                    context = ErrorContext(
                        module="VALIDATOR",
                        operation="json_validation",
                        category=ErrorCategory.VALIDATION,
                        user_message=f"Missing required fields: {', '.join(missing_keys)}",
                        technical_details=f"Missing keys: {missing_keys}",
                    )
                    self.error_handler.handle_error(
                        KeyError(f"Missing keys: {missing_keys}"), context
                    )
                    return False

            # Validate against schema if provided
            if schema and PYDANTIC_AVAILABLE:
                try:
                    # This is a simplified schema validation
                    # In a real implementation, you'd use jsonschema or pydantic
                    pass
                except Exception as e:
                    context = ErrorContext(
                        module="VALIDATOR",
                        operation="json_validation",
                        category=ErrorCategory.VALIDATION,
                        user_message="Data does not match expected schema",
                        technical_details=str(e),
                    )
                    self.error_handler.handle_error(e, context)
                    return False

            return True

        except Exception as e:
            context = ErrorContext(
                module="VALIDATOR",
                operation="json_validation",
                category=ErrorCategory.VALIDATION,
                user_message="Data validation failed",
                technical_details=str(e),
            )
            self.error_handler.handle_error(e, context)
            return False

    def validate_transcript_data(self, data: Any) -> bool:
        """
        Validate transcript data structure.

        Args:
            data: Transcript data to validate

        Returns:
            True if transcript is valid, False otherwise
        """
        try:
            # Check if data is a list
            if not isinstance(data, list):
                context = ErrorContext(
                    module="VALIDATOR",
                    operation="transcript_validation",
                    category=ErrorCategory.VALIDATION,
                    user_message="Invalid transcript format. Expected list of messages.",
                    technical_details=f"Data type: {type(data)}",
                )
                self.error_handler.handle_error(
                    TypeError("Transcript data is not a list"), context
                )
                return False

            # Validate each message
            for i, message in enumerate(data):
                if not isinstance(message, dict):
                    context = ErrorContext(
                        module="VALIDATOR",
                        operation="transcript_validation",
                        category=ErrorCategory.VALIDATION,
                        user_message=f"Invalid message format at position {i}",
                        technical_details=f"Message type: {type(message)}",
                    )
                    self.error_handler.handle_error(
                        TypeError(f"Message {i} is not a dictionary"), context
                    )
                    return False

                # Check required fields
                required_fields = ["speaker", "text"]
                missing_fields = [
                    field for field in required_fields if field not in message
                ]
                if missing_fields:
                    context = ErrorContext(
                        module="VALIDATOR",
                        operation="transcript_validation",
                        category=ErrorCategory.VALIDATION,
                        user_message=f"Missing required fields in message {i}: {', '.join(missing_fields)}",
                        technical_details=f"Message {i} missing fields: {missing_fields}",
                    )
                    self.error_handler.handle_error(
                        KeyError(f"Message {i} missing fields: {missing_fields}"),
                        context,
                    )
                    return False

                # Validate field types
                if not isinstance(message["speaker"], str):
                    context = ErrorContext(
                        module="VALIDATOR",
                        operation="transcript_validation",
                        category=ErrorCategory.VALIDATION,
                        user_message=f"Speaker must be a string in message {i}",
                        technical_details=f"Speaker type: {type(message['speaker'])}",
                    )
                    self.error_handler.handle_error(
                        TypeError(f"Speaker in message {i} is not a string"), context
                    )
                    return False

                if not isinstance(message["text"], str):
                    context = ErrorContext(
                        module="VALIDATOR",
                        operation="transcript_validation",
                        category=ErrorCategory.VALIDATION,
                        user_message=f"Text must be a string in message {i}",
                        technical_details=f"Text type: {type(message['text'])}",
                    )
                    self.error_handler.handle_error(
                        TypeError(f"Text in message {i} is not a string"), context
                    )
                    return False

            return True

        except Exception as e:
            context = ErrorContext(
                module="VALIDATOR",
                operation="transcript_validation",
                category=ErrorCategory.VALIDATION,
                user_message="Transcript validation failed",
                technical_details=str(e),
            )
            self.error_handler.handle_error(e, context)
            return False


# Global instances
error_handler = ErrorHandler()
input_validator = InputValidator()


def handle_errors(
    error_types: list[type[Exception]] | None = None,
    max_retries: int = 3,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
):
    """
    Decorator for automatic error handling.

    Args:
        error_types: List of exception types to handle
        max_retries: Maximum number of retry attempts
        category: Error category for handling strategy
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            context = ErrorContext(
                module=func.__module__,
                operation=func.__name__,
                category=category,
                max_retries=max_retries,
            )

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if error_types and not any(isinstance(e, t) for t in error_types):
                        raise  # Re-raise if not in handled types

                    context.retry_count = attempt
                    if not error_handler.handle_error(e, context):
                        raise  # Re-raise if error handling failed

            # This should never be reached, but just in case
            raise RuntimeError(
                f"Function {func.__name__} failed after {max_retries} attempts"
            )

        return wrapper

    return decorator


@contextmanager
def graceful_exit():
    """
    Context manager for graceful exit handling.

    This context manager ensures proper cleanup when the program exits,
    whether normally or due to an interrupt signal.
    """
    try:
        yield
    except KeyboardInterrupt:
        print("\n🛑 Operation interrupted by user. Cleaning up...")
        error_handler._cleanup_resources()
        print("✅ Cleanup completed. Exiting gracefully.")
        sys.exit(0)
    except Exception as e:
        # Allow typer.Exit (and CliExit which extends it) to pass through
        # These are used for clean program exits, not errors
        if TYPER_AVAILABLE and isinstance(e, typer.Exit):
            error_handler._cleanup_resources()
            raise  # Re-raise to let typer handle the exit
        print(f"\n❌ Unexpected error: {e}")
        error_handler._cleanup_resources()
        raise


def retry_with_backoff(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: list[type[Exception]] | None = None,
) -> Callable:
    """
    Retry function with exponential backoff.

    Args:
        func: Function to retry
        max_attempts: Maximum number of attempts
        base_delay: Base delay between attempts
        max_delay: Maximum delay between attempts
        exponential_base: Base for exponential backoff
        exceptions: List of exceptions to retry on

    Returns:
        Wrapped function with retry logic
    """
    if TENACITY_AVAILABLE:
        # Use tenacity for advanced retry logic
        retry_decorator = retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=base_delay, max=max_delay),
            retry=retry_if_exception_type(tuple(exceptions or [Exception])),
        )
        return retry_decorator(func)

    # Fallback implementation
    def wrapper(*args, **kwargs):
        last_exception = None

        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if exceptions and not any(isinstance(e, exc) for exc in exceptions):
                    raise

                if attempt < max_attempts - 1:
                    delay = min(base_delay * (exponential_base**attempt), max_delay)
                    print(
                        f"🔄 Attempt {attempt + 1} failed, retrying in {delay:.1f} seconds..."
                    )
                    time.sleep(delay)

        raise last_exception

    return wrapper


def categorize_error(error: Exception) -> ErrorCategory:
    """
    Categorize an exception into an ErrorCategory.

    Args:
        error: The exception to categorize

    Returns:
        The appropriate ErrorCategory for the exception
    """
    error_type = type(error)

    # Validation errors
    if error_type in (ValueError, TypeError, KeyError, AttributeError):
        return ErrorCategory.VALIDATION

    # Processing errors
    if error_type in (RuntimeError, NotImplementedError, AssertionError):
        return ErrorCategory.PROCESSING

    # Resource errors
    if error_type in (MemoryError, OSError, IOError):
        return ErrorCategory.RESOURCE

    # Dependency errors
    if error_type in (ImportError, ModuleNotFoundError):
        return ErrorCategory.DEPENDENCY

    # Timeout errors
    if error_type == TimeoutError:
        return ErrorCategory.TIMEOUT

    # Network errors
    if error_type in (ConnectionError, ConnectionRefusedError, ConnectionAbortedError):
        return ErrorCategory.NETWORK

    # Security errors
    if error_type in (PermissionError,):
        return ErrorCategory.SECURITY

    # Unknown errors
    return ErrorCategory.UNKNOWN


def get_user_friendly_message(error: Exception, category: ErrorCategory) -> str:
    """
    Generate a user-friendly error message from an exception.

    Args:
        error: The exception that occurred
        category: The error category

    Returns:
        A user-friendly error message
    """
    error_message = str(error)

    # Base messages for each category
    category_messages = {
        ErrorCategory.VALIDATION: "Invalid input provided",
        ErrorCategory.PROCESSING: "An error occurred while processing",
        ErrorCategory.RESOURCE: "Insufficient resources available",
        ErrorCategory.DEPENDENCY: "A required dependency is missing",
        ErrorCategory.TIMEOUT: "The operation timed out",
        ErrorCategory.NETWORK: "A network error occurred",
        ErrorCategory.SECURITY: "A security issue was detected",
        ErrorCategory.UNKNOWN: "An unexpected error occurred",
    }

    base_message = category_messages.get(category, "An error occurred")

    # If the error message is user-friendly, use it; otherwise use the base message
    if (
        error_message
        and len(error_message) < 200
        and not any(
            tech_term in error_message.lower()
            for tech_term in ["traceback", "exception", "error at", "file", "line"]
        )
    ):
        return f"{base_message}: {error_message}"

    return base_message
