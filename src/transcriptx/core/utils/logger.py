# transcriptx/core/logger.py

"""
Logging configuration and utilities for TranscriptX.

This module provides centralized logging configuration and utility functions
for consistent error handling and debugging across all TranscriptX modules.

The logging system is designed to provide:
- Consistent log formatting across all modules
- Multiple output destinations (console and file)
- Structured error reporting with context
- Performance monitoring capabilities
- Pipeline and analysis tracking
- Configuration change logging

Key Features:
- Global logger instance with lazy initialization
- Standardized log message formats
- Module-specific logging with context
- Exception tracking and stack traces
- Performance timing and monitoring
- File operation logging
- Pipeline execution tracking
"""

import logging
import logging.handlers
import sys
from typing import Any

# Global logger instance for singleton pattern
# This ensures all modules use the same logger configuration
_logger: logging.Logger | None = None

# Default logging configuration values
# These can be overridden by configuration files or environment variables
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LOG_FILE = "transcriptx.log"


def setup_logging(
    level: str = DEFAULT_LOG_LEVEL,
    log_file: str | None = None,
    format_string: str | None = None,
) -> logging.Logger:
    """
    Set up logging configuration for TranscriptX.

    This function initializes the global logging system with console and
    optional file output. It creates a singleton logger instance that
    can be used throughout the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional). If provided, logs will be
                 written to both console and file.
        format_string: Custom log format string (optional). Uses default
                      format if not provided.

    Returns:
        Configured logger instance

    Note:
        This function uses a singleton pattern - subsequent calls will
        return the same logger instance. The logger is configured with
        both console and file handlers if a log file is specified.
    """
    global _logger

    # Create logger with the transcriptx namespace
    logger = logging.getLogger("transcriptx")
    logger.disabled = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(getattr(logging, level.upper()))

    # Create formatter for consistent log message formatting
    formatter = logging.Formatter(
        format_string or DEFAULT_LOG_FORMAT,
    )

    # Simple console handler - no spinner interference
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler for persistent logging (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Store the logger instance globally
    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """
    Get the global logger instance.

    This function provides access to the singleton logger instance.
    If the logger hasn't been initialized yet, it will be set up
    with default configuration.

    Returns:
        The global logger instance

    Note:
        This is the primary way to access the logger throughout
        the TranscriptX codebase. It ensures consistent logging
        configuration across all modules.
    """
    if _logger is None:
        return setup_logging()
    return _logger


def log_error(
    module: str, error: str, context: str = "", exception: Exception | None = None
) -> None:
    """
    Log a standardized error message.

    This function provides a consistent way to log errors across all
    modules. It automatically formats the message with module context
    and can include exception details and stack traces.

    Args:
        module: Name of the module where the error occurred
        error: Error message describing what went wrong
        context: Additional context information (optional)
        exception: Exception object to include stack trace (optional)

    Note:
        If an exception is provided, the full stack trace will be
        included in the log message for debugging purposes.
    """
    logger = get_logger()
    message = f"[{module.upper()}] {error}"
    if context:
        message += f" | Context: {context}"

    if exception:
        logger.error(message, exc_info=True)
    else:
        logger.error(message)
    for handler in logger.handlers:
        try:
            handler.flush()
        except Exception:
            continue


def log_warning(module: str, warning: str, context: str = "") -> None:
    """
    Log a standardized warning message.

    This function provides a consistent way to log warnings across all
    modules. Warnings indicate potential issues that don't prevent
    execution but should be noted.

    Args:
        module: Name of the module where the warning occurred
        warning: Warning message describing the potential issue
        context: Additional context information (optional)
    """
    logger = get_logger()
    message = f"[{module.upper()}] {warning}"
    if context:
        message += f" | Context: {context}"
    logger.warning(message)


def log_info(module: str, message: str, context: str = "") -> None:
    """
    Log a standardized info message.

    This function provides a consistent way to log informational messages
    across all modules. Info messages provide general status updates
    and progress information.

    Args:
        module: Name of the module where the info occurred
        message: Informational message
        context: Additional context information (optional)
    """
    logger = get_logger()
    message = f"[{module.upper()}] {message}"
    if context:
        message += f" | Context: {context}"
    logger.info(message)


def log_debug(module: str, message: str, context: str = "") -> None:
    """
    Log a standardized debug message.

    This function provides a consistent way to log debug messages
    across all modules. Debug messages provide detailed information
    useful for troubleshooting and development.

    Args:
        module: Name of the module where the debug occurred
        message: Debug message with detailed information
        context: Additional context information (optional)
    """
    logger = get_logger()
    message = f"[{module.upper()}] {message}"
    if context:
        message += f" | Context: {context}"
    logger.debug(message)


def log_analysis_start(module_name: str, transcript_path: str) -> None:
    """
    Log the start of an analysis module.

    Args:
        module_name: Name of the analysis module
        transcript_path: Path to the transcript being analyzed
    """
    logger = get_logger()
    logger.info(f"Starting {module_name} analysis for: {transcript_path}")


def log_analysis_complete(
    module_name: str, transcript_path: str, duration: float | None = None
) -> None:
    """
    Log the completion of an analysis module.

    Args:
        module_name: Name of the analysis module
        transcript_path: Path to the transcript that was analyzed
        duration: Duration of the analysis in seconds (optional)
    """
    logger = get_logger()
    message = f"Completed {module_name} analysis for: {transcript_path}"
    if duration is not None:
        message += f" (took {duration:.2f}s)"
    logger.info(message)


def log_analysis_error(
    module_name: str, transcript_path: str, error: Exception
) -> None:
    """
    Log an error that occurred during analysis.

    Args:
        module_name: Name of the analysis module
        transcript_path: Path to the transcript being analyzed
        error: The exception that occurred
    """
    logger = get_logger()
    logger.error(
        f"Error in {module_name} analysis for {transcript_path}: {error}",
        exc_info=True,
    )


def log_pipeline_start(transcript_path: str, modules: list[str]) -> None:
    """
    Log the start of a pipeline execution.

    Args:
        transcript_path: Path to the transcript being processed
        modules: List of modules that will be executed
    """
    logger = get_logger()
    logger.info(
        f"Starting analysis pipeline for {transcript_path} with modules: {', '.join(modules)}"
    )


def log_pipeline_complete(
    transcript_path: str, modules_run: list[str], errors: list[str]
) -> None:
    """
    Log the completion of a pipeline execution.

    Args:
        transcript_path: Path to the transcript that was processed
        modules_run: List of modules that were successfully executed
        errors: List of errors that occurred during execution
    """
    logger = get_logger()
    message = f"Pipeline completed for {transcript_path}"
    if modules_run:
        message += f" - Successfully ran: {', '.join(modules_run)}"
    if errors:
        message += f" - Errors: {', '.join(errors)}"
    logger.info(message)


def log_configuration_change(setting: str, old_value: Any, new_value: Any) -> None:
    """
    Log a configuration change.

    Args:
        setting: Name of the setting that changed
        old_value: Previous value of the setting
        new_value: New value of the setting
    """
    logger = get_logger()
    logger.info(f"Configuration changed: {setting} = {old_value} -> {new_value}")


def log_file_operation(
    operation: str, file_path: str, success: bool, error: str | None = None
) -> None:
    """
    Log a file operation.

    Args:
        operation: Type of operation (read, write, delete, etc.)
        file_path: Path to the file being operated on
        success: Whether the operation was successful
        error: Error message if the operation failed (optional)
    """
    logger = get_logger()
    if success:
        logger.info(f"File {operation}: {file_path}")
    else:
        logger.error(f"File {operation} failed: {file_path} - {error}")


def log_performance(operation: str, duration: float, context: str = "") -> None:
    """
    Log performance metrics.

    Args:
        operation: Name of the operation being measured
        duration: Duration of the operation in seconds
        context: Additional context about the operation (optional)
    """
    logger = get_logger()
    message = f"Performance: {operation} took {duration:.2f}s"
    if context:
        message += f" ({context})"
    logger.info(message)


def log_function_call(
    func_name: str,
    args: dict[str, Any] | None = None,
    kwargs: dict[str, Any] | None = None,
) -> None:
    """
    Log a function call for debugging purposes.

    Args:
        func_name: Name of the function being called
        args: Positional arguments (optional)
        kwargs: Keyword arguments (optional)
    """
    logger = get_logger()
    message = f"Function call: {func_name}"
    if args:
        message += f" args={args}"
    if kwargs:
        message += f" kwargs={kwargs}"
    logger.debug(message)


def log_function_result(
    func_name: str, result: Any | None = None, error: Exception | None = None
) -> None:
    """
    Log a function result for debugging purposes.

    Args:
        func_name: Name of the function that was called
        result: Return value of the function (optional)
        error: Exception that occurred (optional)
    """
    logger = get_logger()
    if error:
        logger.debug(f"Function result: {func_name} failed with {error}")
    else:
        logger.debug(f"Function result: {func_name} returned {result}")


def log_transcription_start(audio_path: str, model_name: str) -> None:
    """
    Log the start of a transcription process.

    Args:
        audio_path: Path to the audio file being transcribed
        model_name: Name of the transcription model being used
    """
    logger = get_logger()
    logger.info(f"Starting transcription of {audio_path} using {model_name}")


def log_transcription_complete(
    audio_path: str, output_path: str, duration: float | None = None
) -> None:
    """
    Log the completion of a transcription process.

    Args:
        audio_path: Path to the audio file that was transcribed
        output_path: Path where the transcription was saved
        duration: Duration of the transcription process in seconds (optional)
    """
    logger = get_logger()
    message = f"Completed transcription of {audio_path} -> {output_path}"
    if duration is not None:
        message += f" (took {duration:.2f}s)"
    logger.info(message)


def log_speaker_mapping_start(speaker_count: int) -> None:
    """
    Log the start of speaker mapping process.

    Args:
        speaker_count: Number of speakers detected in the transcript
    """
    logger = get_logger()
    logger.info(f"Starting speaker mapping for {speaker_count} speakers")


def log_speaker_mapping_complete(speaker_map: dict[str, str]) -> None:
    """
    Log the completion of speaker mapping process.

    Args:
        speaker_map: The completed speaker mapping dictionary
    """
    logger = get_logger()
    mapped_count = len([v for v in speaker_map.values() if v])
    total_count = len(speaker_map)
    logger.info(
        f"Completed speaker mapping: {mapped_count}/{total_count} speakers mapped"
    )


def reset_logging() -> None:
    """
    Reset the global logger instance.

    This is useful for testing or when you need to reconfigure
    the logging system from scratch.
    """
    global _logger
    logger = logging.getLogger("transcriptx")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    _logger = None
