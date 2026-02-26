"""
Enhanced progress tracking and user feedback for TranscriptX.

This module provides comprehensive progress tracking with:
- Percentage-based progress bars
- Regular user feedback (every 10 seconds)
- Graceful Ctrl+C handling
- Resource monitoring
- Process encapsulation in spinners
- Timeout management
- Memory usage tracking
"""

import os
import signal
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta

import humanize
import psutil

try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

try:
    from alive_progress import alive_bar

    ALIVE_PROGRESS_AVAILABLE = True
except ImportError:
    ALIVE_PROGRESS_AVAILABLE = False

from transcriptx.core.utils.logger import get_logger, log_error, log_info, log_warning
from transcriptx.utils.spinner import Spinner

"""
Retry logic utilities for handling transient failures.

This module provides decorators and utilities for implementing retry logic
with exponential backoff, timeout handling, and graceful degradation.
"""

import functools
from typing import Callable, Any, Optional, Type, Union, Tuple


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = (
        OSError,
        ConnectionError,
        TimeoutError,
    ),
    timeout: Optional[float] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Callable:
    """
    Decorator to retry operations on transient failures.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay on each retry
        exceptions: Exception types to retry on
        timeout: Maximum total time for all attempts
        on_retry: Optional callback function called on each retry

    Returns:
        Decorated function with retry logic

    Example:
        @retry_on_failure(max_attempts=3, delay=1.0)
        def fetch_data():
            # This will be retried up to 3 times on OSError, ConnectionError, etc.
            return requests.get(url)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            start_time = time.time()

            for attempt in range(max_attempts):
                try:
                    # Check timeout
                    if timeout and (time.time() - start_time) > timeout:
                        raise TimeoutError(
                            f"Operation timed out after {timeout} seconds"
                        )

                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    # Log retry attempt
                    log_warning(
                        "RETRY",
                        f"Attempt {attempt + 1}/{max_attempts} failed: {e}",
                        context=f"Function: {func.__name__}",
                    )

                    # Call retry callback if provided
                    if on_retry:
                        try:
                            on_retry(attempt + 1, e)
                        except Exception as callback_error:
                            log_error(
                                "RETRY", f"Retry callback failed: {callback_error}"
                            )

                    # Don't retry on last attempt
                    if attempt == max_attempts - 1:
                        break

                    # Calculate delay with exponential backoff
                    current_delay = delay * (backoff_factor**attempt)

                    # Check if we would exceed timeout
                    if timeout and (time.time() - start_time + current_delay) > timeout:
                        raise TimeoutError(
                            f"Operation would exceed timeout of {timeout} seconds"
                        )

                    time.sleep(current_delay)

            # If we get here, all attempts failed
            log_error(
                "RETRY",
                f"All {max_attempts} attempts failed for {func.__name__}",
                exception=last_exception,
            )
            raise last_exception

        return wrapper

    return decorator


def retry_with_circuit_breaker(
    max_attempts: int = 3,
    delay: float = 1.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = (
        OSError,
        ConnectionError,
    ),
    circuit_breaker_threshold: int = 5,
    circuit_breaker_timeout: float = 60.0,
) -> Callable:
    """
    Decorator with circuit breaker pattern for handling repeated failures.

    Args:
        max_attempts: Maximum number of retry attempts per operation
        delay: Initial delay between retries in seconds
        exceptions: Exception types to retry on
        circuit_breaker_threshold: Number of consecutive failures before circuit opens
        circuit_breaker_timeout: Time to wait before attempting to close circuit

    Returns:
        Decorated function with circuit breaker retry logic
    """
    # Circuit breaker state
    failure_count = 0
    last_failure_time = 0
    circuit_open = False

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            nonlocal failure_count, last_failure_time, circuit_open

            # Check if circuit is open
            if circuit_open:
                if time.time() - last_failure_time < circuit_breaker_timeout:
                    raise ConnectionError(
                        "Circuit breaker is open - too many recent failures"
                    )
                else:
                    # Try to close circuit
                    circuit_open = False
                    failure_count = 0

            try:
                result = func(*args, **kwargs)
                # Success - reset failure count
                failure_count = 0
                return result

            except exceptions as e:
                failure_count += 1
                last_failure_time = time.time()

                # Open circuit if threshold exceeded
                if failure_count >= circuit_breaker_threshold:
                    circuit_open = True
                    log_error(
                        "CIRCUIT_BREAKER",
                        f"Circuit breaker opened after {failure_count} consecutive failures",
                    )
                    raise ConnectionError(
                        "Circuit breaker opened - too many consecutive failures"
                    )

                # Retry with exponential backoff
                for attempt in range(max_attempts - 1):
                    time.sleep(delay * (2**attempt))
                    try:
                        result = func(*args, **kwargs)
                        failure_count = 0  # Reset on success
                        return result
                    except exceptions:
                        failure_count += 1
                        last_failure_time = time.time()

                        # Open circuit if threshold exceeded during retries
                        if failure_count >= circuit_breaker_threshold:
                            circuit_open = True
                            log_error(
                                "CIRCUIT_BREAKER",
                                f"Circuit breaker opened during retries after {failure_count} failures",
                            )
                            raise ConnectionError(
                                "Circuit breaker opened during retries"
                            )

                # All retries failed
                raise e

        return wrapper

    return decorator


def timeout_handler(
    timeout: float,
    default_return: Any = None,
    on_timeout: Optional[Callable[[], None]] = None,
) -> Callable:
    """
    Decorator to handle timeouts gracefully.

    Args:
        timeout: Maximum execution time in seconds
        default_return: Value to return if timeout occurs
        on_timeout: Optional callback function called on timeout

    Returns:
        Decorated function with timeout handling
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import signal

            def timeout_handler_signal(signum, frame):
                raise TimeoutError(f"Operation timed out after {timeout} seconds")

            # Set up signal handler for timeout
            old_handler = signal.signal(signal.SIGALRM, timeout_handler_signal)
            signal.alarm(int(timeout))

            try:
                result = func(*args, **kwargs)
                signal.alarm(0)  # Cancel alarm
                return result

            except TimeoutError:
                log_warning(
                    "TIMEOUT", f"Operation {func.__name__} timed out after {timeout}s"
                )

                if on_timeout:
                    try:
                        on_timeout()
                    except Exception as callback_error:
                        log_error(
                            "TIMEOUT", f"Timeout callback failed: {callback_error}"
                        )

                return default_return

            finally:
                signal.alarm(0)  # Ensure alarm is cancelled
                signal.signal(signal.SIGALRM, old_handler)  # Restore original handler

        return wrapper

    return decorator


def graceful_degradation(
    fallback_func: Callable,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
) -> Callable:
    """
    Decorator to provide graceful degradation with fallback function.

    Args:
        fallback_func: Function to call if primary function fails
        exceptions: Exception types to catch and fall back on

    Returns:
        Decorated function with graceful degradation
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                log_warning(
                    "GRACEFUL_DEGRADATION",
                    f"Primary function {func.__name__} failed, using fallback: {e}",
                )
                return fallback_func(*args, **kwargs)

        return wrapper

    return decorator


# Example usage functions for testing
def example_file_operation(file_path: str) -> str:
    """Example function that might fail due to file system issues."""
    with open(file_path, "r") as f:
        return f.read()


def example_network_operation(url: str) -> str:
    """Example function that might fail due to network issues."""
    import requests

    response = requests.get(url, timeout=5)
    return response.text


def example_fallback_operation(*args, **kwargs) -> str:
    """Example fallback function for graceful degradation."""
    return "Fallback result"


# Example decorated functions
@retry_on_failure(max_attempts=3, delay=0.1)
def robust_file_operation(file_path: str) -> str:
    """File operation with retry logic."""
    return example_file_operation(file_path)


@retry_with_circuit_breaker(max_attempts=2, delay=0.1)
def robust_network_operation(url: str) -> str:
    """Network operation with circuit breaker."""
    return example_network_operation(url)


@timeout_handler(timeout=5.0, default_return="Timeout result")
def timeout_protected_operation() -> str:
    """Operation with timeout protection."""
    time.sleep(10)  # This will timeout
    return "Should not reach here"


@graceful_degradation(example_fallback_operation, OSError)
def graceful_file_operation(file_path: str) -> str:
    """File operation with graceful degradation."""
    return example_file_operation(file_path)


@dataclass
class ProgressConfig:
    """Configuration for progress tracking."""

    update_interval: float = 10.0  # Seconds between user feedback
    show_percentage: bool = True
    show_memory: bool = True
    show_time_remaining: bool = True
    show_speed: bool = True
    timeout: float | None = None  # Timeout in seconds
    timeout_warn_only: bool = (
        False  # If True, log warning instead of raising on timeout
    )
    graceful_exit: bool = True


class ProgressTracker:
    """
    Comprehensive progress tracker with user feedback and resource monitoring.

    This class provides:
    - Percentage-based progress tracking
    - Regular user feedback (every 10 seconds by default)
    - Memory and CPU usage monitoring
    - Graceful Ctrl+C handling
    - Timeout management
    - Speed calculation
    """

    def __init__(
        self,
        total: int,
        description: str = "Processing",
        config: ProgressConfig | None = None,
    ):
        self.total = total
        self.description = description
        self.config = config or ProgressConfig()
        self.current = 0
        self.start_time = time.time()
        self.last_update = time.time()
        self.last_feedback = time.time()
        self.process = psutil.Process(os.getpid())
        self.logger = get_logger()
        self._interrupted = False
        self._timeout_reached = False  # Track if timeout has been reached
        self._lock = threading.Lock()

        # Set up signal handlers for graceful exit
        if self.config.graceful_exit:
            self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful interruption."""

        def signal_handler(signum, frame):
            self._interrupted = True
            self.logger.info(
                f"Received interrupt signal {signum}, preparing for graceful exit..."
            )

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def update(self, increment: int = 1, custom_message: str | None = None):
        """
        Update progress and provide user feedback.

        Args:
            increment: Number of items processed
            custom_message: Optional custom message to display
        """
        with self._lock:
            self.current += increment
            current_time = time.time()

            # Check for timeout
            if (
                self.config.timeout
                and (current_time - self.start_time) > self.config.timeout
            ):
                if not self._timeout_reached:
                    # First time timeout is reached
                    self._timeout_reached = True
                    timeout_msg = (
                        f"Progress tracker timeout reached ({self.config.timeout} seconds). "
                        f"Pipeline will continue but progress tracking may be inaccurate."
                    )

                    if self.config.timeout_warn_only:
                        # Log warning and continue
                        log_warning("PROGRESS", timeout_msg)
                        self.logger.warning(timeout_msg)
                    else:
                        # Raise error (original behavior)
                        raise TimeoutError(
                            f"Operation timed out after {self.config.timeout} seconds"
                        )
                # If timeout already reached and warn_only, just continue silently

            # Check for interruption
            if self._interrupted:
                raise KeyboardInterrupt("Operation interrupted by user")

            # Provide regular feedback
            if (current_time - self.last_feedback) >= self.config.update_interval:
                self._provide_feedback(custom_message)
                self.last_feedback = current_time

    def _provide_feedback(self, custom_message: str | None = None):
        """Provide user feedback with progress and resource information."""
        elapsed = time.time() - self.start_time
        percentage = (self.current / self.total) * 100 if self.total > 0 else 0

        # Calculate speed and time remaining
        if elapsed > 0:
            speed = self.current / elapsed
            if speed > 0:
                remaining_items = self.total - self.current
                time_remaining = remaining_items / speed
            else:
                time_remaining = float("inf")
        else:
            speed = 0
            time_remaining = float("inf")

        # Get memory usage
        memory_info = self.process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024

        # Build feedback message
        feedback_parts = [f"🔄 {self.description}"]

        if self.config.show_percentage:
            feedback_parts.append(f"{percentage:.1f}%")

        feedback_parts.append(f"({self.current}/{self.total})")

        if self.config.show_speed and speed > 0:
            feedback_parts.append(f"Speed: {speed:.1f} items/s")

        if self.config.show_time_remaining and time_remaining != float("inf"):
            feedback_parts.append(f"ETA: {timedelta(seconds=int(time_remaining))}")

        if self.config.show_memory:
            feedback_parts.append(f"Memory: {memory_mb:.1f} MB")

        if custom_message:
            feedback_parts.append(f"| {custom_message}")

        feedback = " | ".join(feedback_parts)

        # Log the feedback
        log_info("PROGRESS", feedback)

        # Also print to console for immediate feedback
        print(f"\r{feedback}", end="", flush=True)

    def finish(self, message: str | None = None):
        """Mark progress as complete."""
        with self._lock:
            total_time = time.time() - self.start_time
            final_message = message or f"✅ {self.description} completed"

            if total_time > 0:
                avg_speed = self.total / total_time
                final_message += f" in {timedelta(seconds=int(total_time))} ({avg_speed:.1f} items/s)"

            log_info("PROGRESS", final_message)
            print(f"\n{final_message}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is None:
            self.finish()
        else:
            error_msg = f"❌ {self.description} failed: {exc_val}"
            log_error("PROGRESS", error_msg)
            print(f"\n{error_msg}")


class ProgressBar:
    """
    Enhanced progress bar with multiple backend support.

    Supports tqdm, alive-progress, and fallback text-based progress.
    """

    def __init__(
        self,
        total: int,
        description: str = "Processing",
        use_tqdm: bool = True,
        use_alive: bool = True,
    ):
        self.total = total
        self.description = description
        self.use_tqdm = use_tqdm and TQDM_AVAILABLE
        self.use_alive = use_alive and ALIVE_PROGRESS_AVAILABLE
        self.current = 0
        self._bar = None
        self._start_time = None

    def __enter__(self):
        """Initialize the progress bar."""
        self._start_time = time.time()

        if self.use_tqdm:
            self._bar = tqdm(
                total=self.total,
                desc=self.description,
                unit="items",
                ncols=100,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
            )
        elif self.use_alive:
            self._bar = alive_bar(
                self.total,
                title=self.description,
                length=50,
                spinner="dots",
            )
        else:
            # Fallback text-based progress
            print(f"🔄 {self.description}: 0/{self.total} (0.0%)")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up the progress bar."""
        if self._bar:
            if hasattr(self._bar, "close"):
                self._bar.close()
            elif hasattr(self._bar, "__exit__"):
                self._bar.__exit__(exc_type, exc_val, exc_tb)

        if exc_type is None:
            elapsed = time.time() - self._start_time
            print(
                f"✅ {self.description} completed in {timedelta(seconds=int(elapsed))}"
            )
        else:
            print(f"❌ {self.description} failed: {exc_val}")

    def update(self, increment: int = 1):
        """Update the progress bar."""
        self.current += increment

        if self._bar:
            if hasattr(self._bar, "update"):
                self._bar.update(increment)
            elif hasattr(self._bar, "next"):
                self._bar.next()
        else:
            # Fallback text-based update
            percentage = (self.current / self.total) * 100 if self.total > 0 else 0
            print(
                f"\r🔄 {self.description}: {self.current}/{self.total} ({percentage:.1f}%)",
                end="",
                flush=True,
            )


@contextmanager
def process_spinner(
    description: str,
    config: ProgressConfig | None = None,
    timeout: float | None = None,
):
    """
    Context manager for encapsulating large processes in spinners with progress tracking.

    Args:
        description: Description of the process
        config: Progress configuration
        timeout: Timeout in seconds

    Yields:
        ProgressTracker instance for detailed progress updates
    """
    config = config or ProgressConfig()
    if timeout:
        config.timeout = timeout

    # Use Spinner class instead of progress() to support pause/resume for interactive workflows
    with Spinner(description) as spinner:
        tracker = ProgressTracker(100, description, config)
        try:
            yield tracker
        except KeyboardInterrupt:
            print("❌ Interrupted")
            raise
        except Exception as e:
            print(f"❌ Failed: {e}")
            raise
        else:
            print("✅ Completed")


def _resource_sampler(
    process: "psutil.Process",
    resources: dict,
    stop_event: threading.Event,
    interval: float = 1.0,
) -> None:
    """Background thread: sample CPU and memory periodically and update peak values."""
    # First call to cpu_percent() returns 0.0; subsequent calls return % since last call.
    process.cpu_percent()
    while not stop_event.wait(timeout=interval):
        try:
            cpu = process.cpu_percent()
            mem = process.memory_info().rss
            resources["peak_cpu"] = max(resources["peak_cpu"], cpu)
            resources["peak_memory"] = max(resources["peak_memory"], mem)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            break


@contextmanager
def resource_monitor(description: str = "Monitoring resources"):
    """
    Context manager for monitoring system resources during operations.
    Samples CPU and memory in a background thread so peak values are meaningful
    (psutil's cpu_percent() returns 0.0 on first call with interval=None).

    Args:
        description: Description of the operation

    Yields:
        Dict containing resource information
    """
    process = psutil.Process(os.getpid())
    start_memory = process.memory_info().rss
    start_time = time.time()

    resources = {
        "start_memory": start_memory,
        "start_time": start_time,
        "peak_memory": start_memory,
        "peak_cpu": 0.0,
    }

    stop_event = threading.Event()
    sampler = threading.Thread(
        target=_resource_sampler,
        args=(process, resources, stop_event),
        daemon=True,
    )
    sampler.start()

    try:
        yield resources
    finally:
        stop_event.set()
        sampler.join(timeout=2.5)

        end_time = time.time()
        end_memory = process.memory_info().rss
        duration = end_time - start_time
        memory_increase = end_memory - start_memory

        log_info(
            "RESOURCES",
            f"{description} - Duration: {duration:.2f}s, "
            f"Memory: {humanize.naturalsize(memory_increase)} increase, "
            f"Peak CPU: {resources['peak_cpu']:.1f}%",
        )


def monitor_large_process(
    func: Callable,
    description: str,
    total_items: int,
    config: ProgressConfig | None = None,
) -> Callable:
    """
    Decorator for monitoring large processes with progress tracking.

    Args:
        func: Function to monitor
        description: Description of the process
        total_items: Total number of items to process
        config: Progress configuration

    Returns:
        Wrapped function with progress tracking
    """

    def wrapper(*args, **kwargs):
        with process_spinner(description, config) as tracker:
            with resource_monitor(description):
                result = func(*args, **kwargs)
                tracker.update(total_items - tracker.current)  # Complete the progress
                return result

    return wrapper


class TimeoutManager:
    """Manager for handling timeouts in long-running operations."""

    def __init__(self, timeout: float):
        self.timeout = timeout
        self.start_time = time.time()

    def check_timeout(self):
        """Check if timeout has been reached."""
        if time.time() - self.start_time > self.timeout:
            raise TimeoutError(f"Operation timed out after {self.timeout} seconds")

    def time_remaining(self) -> float:
        """Get remaining time before timeout."""
        elapsed = time.time() - self.start_time
        return max(0, self.timeout - elapsed)


def create_progress_bar(
    total: int,
    description: str = "Processing",
    style: str = "auto",
) -> ProgressBar:
    """
    Factory function for creating progress bars with different styles.

    Args:
        total: Total number of items
        description: Description of the process
        style: Progress bar style ('tqdm', 'alive', 'text', 'auto')

    Returns:
        ProgressBar instance
    """
    if style == "auto":
        if TQDM_AVAILABLE:
            style = "tqdm"
        elif ALIVE_PROGRESS_AVAILABLE:
            style = "alive"
        else:
            style = "text"

    use_tqdm = style == "tqdm"
    use_alive = style == "alive"

    return ProgressBar(total, description, use_tqdm, use_alive)
