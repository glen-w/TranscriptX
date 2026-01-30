"""
Audio playback handler module for managing audio playback in file selection interfaces.

This module provides a PlaybackController class and key binding factory for
managing audio playback state and controls.
"""

import time
from pathlib import Path
from typing import Optional, Callable

from prompt_toolkit.key_binding import KeyBindings

from transcriptx.cli.audio import (
    get_audio_duration,
    play_audio_file_from_position,
    stop_audio_playback,
    check_ffplay_available,
    SegmentPlayer,
)
from rich.console import Console

console = Console()


class PlaybackController:
    """Manages audio playback state and controls."""

    def __init__(self):
        self._current_process: Optional[object] = None
        self._current_file: Optional[Path] = None
        self._current_position: float = 0.0
        self._playback_start_time: Optional[float] = None
        self._segment_player = SegmentPlayer()

    def play(self, file_path: Path) -> bool:
        """
        Start playing an audio file.

        Args:
            file_path: Path to the audio file to play

        Returns:
            True if playback started successfully, False otherwise
        """
        # Stop any existing playback
        self.stop()

        if self._segment_player.play_file(file_path):
            self._current_process = self._segment_player.current_process
            self._current_file = file_path
            self._current_position = 0.0
            self._playback_start_time = time.time()
            return True
        return False

    def stop(self) -> None:
        """Stop current playback and reset tracking variables."""
        # Kill the process we track (may be from play() or from skip())
        if self._current_process is not None:
            stop_audio_playback(self._current_process)
            self._current_process = None
        # Also stop segment player (cleans temp clips; its _proc may be set from play())
        self._segment_player.stop()

        self._current_file = None
        self._current_position = 0.0
        self._playback_start_time = None

    def skip(self, seconds: float) -> bool:
        """
        Skip playback forward or backward by specified seconds.

        Args:
            seconds: Number of seconds to skip (positive for forward, negative for backward)

        Returns:
            True if skip was successful, False otherwise
        """
        if self._current_file is None:
            return False

        # Save the current file path before calling stop() which clears it
        file_path = self._current_file

        # Check if ffplay is available (required for seeking)
        ffplay_available, _ = check_ffplay_available()
        if not ffplay_available:
            console.print(
                "[yellow]⚠️ Skip requires ffplay. Install ffmpeg to enable seeking.[/yellow]"
            )
            return False

        # Get current position
        current_pos = self.get_position()

        # Get file duration to validate position
        duration = get_audio_duration(file_path)
        if duration is None:
            console.print("[yellow]⚠️ Cannot skip: file duration unknown[/yellow]")
            return False

        # Calculate new position
        new_position = current_pos + seconds

        # Clamp to valid range
        if new_position < 0:
            new_position = 0
        elif new_position >= duration:
            new_position = max(0, duration - 1)  # Stop 1 second before end

        # Stop current playback
        self.stop()

        # Start playback from new position using the saved file path
        process = play_audio_file_from_position(file_path, new_position)
        if process is not None:
            self._current_process = process
            self._current_file = file_path  # Restore the file path
            self._current_position = new_position
            self._playback_start_time = time.time()
            return True

        return False

    def get_position(self) -> float:
        """
        Get the current playback position in seconds.

        Returns:
            Current playback position in seconds
        """
        if self._current_file is None or self._playback_start_time is None:
            return 0.0

        # Calculate elapsed time since playback started
        elapsed = time.time() - self._playback_start_time
        return self._current_position + elapsed

    def is_playing(self) -> bool:
        """
        Check if audio is currently playing.

        Returns:
            True if audio is playing, False otherwise
        """
        return self._current_process is not None and self._current_file is not None


def create_playback_key_bindings(
    controller: PlaybackController, get_current_file_fn: Callable[[], Optional[Path]]
) -> KeyBindings:
    """
    Create key bindings for audio playback controls.

    Args:
        controller: PlaybackController instance
        get_current_file_fn: Function that returns the currently highlighted file path

    Returns:
        KeyBindings object with playback controls
    """
    kb = KeyBindings()

    @kb.add("right")
    def play_current_file(event):
        """Play the currently highlighted file when right arrow is pressed."""
        file_path = get_current_file_fn()
        if file_path:
            controller.play(file_path)
        # NO app.exit() call - selections are preserved

    @kb.add("left")
    def stop_playback(event):
        """Stop current playback when left arrow is pressed."""
        controller.stop()
        # Don't print to console - it interferes with prompt_toolkit UI navigation

    @kb.add(",")
    @kb.add("<")
    def skip_backward(event):
        """Skip backward 10 seconds."""
        controller.skip(-10.0)

    @kb.add(".")
    @kb.add(">")
    def skip_forward(event):
        """Skip forward 10 seconds."""
        controller.skip(10.0)

    return kb
