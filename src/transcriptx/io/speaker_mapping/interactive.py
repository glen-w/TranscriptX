"""Speaker mapping module."""

from pathlib import Path
from typing import List, Optional

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import has_focus
from prompt_toolkit.layout import HSplit, Layout, Window, FormattedTextControl
from prompt_toolkit.widgets import TextArea
from transcriptx.cli.file_selection_ui_helpers import build_help_text
from colorama import Fore, init
from rich.console import Console

from transcriptx.core.utils.logger import get_logger
from transcriptx.cli.audio import SegmentPlayer

# Lazy imports to avoid circular dependencies:
# - choose_mapping_action imported in load_or_create_speaker_map
# - offer_and_edit_tags imported in load_or_create_speaker_map

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# Color cycle for speaker identification
# Each speaker gets a distinct color during the mapping process
COLOR_CYCLE = [
    Fore.CYAN,
    Fore.MAGENTA,
    Fore.YELLOW,
    Fore.GREEN,
    Fore.BLUE,
    Fore.LIGHTRED_EX,
]

console = Console()
logger = get_logger()

# Sentinel value to indicate "go back to previous speaker"
GO_BACK_SENTINEL = "__GO_BACK__"
# Sentinel value to indicate "exit speaker mapping"
EXIT_SENTINEL = "__EXIT__"

from .utils import SegmentRef, _format_lines_for_display, _parse_user_input
from transcriptx.cli.audio import SegmentPlayer


def _interactive_speaker_naming(
    speaker_id: str,
    segments: List[SegmentRef],
    existing_name: Optional[str],
    audio_path: Optional[Path],
) -> Optional[str]:
    """Interactive speaker naming with batch review and playback shortcuts."""
    playback_enabled = bool(audio_path and audio_path.exists())
    if playback_enabled:
        # Check if playback tools are available
        from transcriptx.cli.audio import check_ffplay_available, check_ffmpeg_available

        ffplay_avail, ffplay_err = check_ffplay_available()
        ffmpeg_avail, ffmpeg_err = check_ffmpeg_available()
        if not ffplay_avail and not ffmpeg_avail:
            logger.warning(
                f"Audio playback disabled: ffplay and ffmpeg not available. {ffplay_err or ffmpeg_err}"
            )
            playback_enabled = False
    player = SegmentPlayer(audio_path=audio_path)
    status_message = "Ready."
    batch_size = 10
    cursor = 0
    displayed_indices: List[int] = []
    selected_offset = 0
    sort_mode = "unique"
    original_segments = list(segments)
    refresh_counter = 0  # Counter to force UI refresh when loading more lines

    def line_score(text: str) -> float:
        tokens = text.lower().split()
        return len(set(tokens)) + 0.1 * len(tokens)

    def sort_by_uniqueness(items: List[SegmentRef]) -> List[SegmentRef]:
        return sorted(items, key=lambda seg: line_score(seg.text), reverse=True)

    def sort_by_time(items: List[SegmentRef]) -> List[SegmentRef]:
        return sorted(
            items,
            key=lambda seg: (seg.start is None, seg.start if seg.start is not None else 0.0),
        )

    def apply_sort_mode() -> None:
        nonlocal segments
        if sort_mode == "unique":
            segments = sort_by_uniqueness(original_segments)
        else:
            segments = sort_by_time(original_segments)

    apply_sort_mode()

    def append_batch() -> bool:
        nonlocal cursor, displayed_indices
        if cursor >= len(segments):
            return False
        batch_end = min(cursor + batch_size, len(segments))
        # Page the view instead of accumulating.
        #
        # The UI window that displays lines is a fixed height (10). When we
        # accumulate indices, newly loaded lines end up below the visible area,
        # so the user sees "Loaded more lines." but the content appears
        # unchanged. Paging ensures "More lines" immediately shows new content.
        displayed_indices = list(range(cursor, batch_end))
        cursor = batch_end
        return True

    append_batch()
    name_input = TextArea(
        height=1,
        prompt="Name: ",
        multiline=False,
    )

    def header_text() -> str:
        remaining = max(0, len(segments) - cursor)
        title = f"Speaker {speaker_id} — {len(segments)} lines ({remaining} remaining)"
        if existing_name:
            title = f"{title} (Enter to keep '{existing_name}')"
        mode_text = (
            "most unique first" if sort_mode == "unique" else "chronological order"
        )
        return f"{title} ({mode_text})\n"

    # Use lambdas to ensure controls refresh when variables change
    # Include refresh_counter in lambda to force re-evaluation when it changes
    header_control = FormattedTextControl(text=lambda: header_text())
    lines_control = FormattedTextControl(
        text=lambda: (
            refresh_counter,  # Reference refresh_counter to force re-evaluation
            _format_lines_for_display(segments, displayed_indices, selected_offset)
        )[1]  # Return the formatted lines, but evaluate refresh_counter first
    )
    status_control = FormattedTextControl(text=lambda: f"[{status_message}]")

    # Build shortcuts list for help box
    shortcuts = []
    if playback_enabled:
        shortcuts.extend(
            [
                ("▶️", "Play", "[→]"),
                ("⏹️", "Stop", "[←]"),
                ("⏩", "Short", "[Shift+→]"),
                ("⏭️", "Long", "[Ctrl+→]"),
            ]
        )
    shortcuts.extend(
        [
            ("↕️", "Navigate", "[↑↓]"),
            ("➕", "More lines", "[m] / [Ctrl+l]"),
            ("🔄", "Toggle sort", "[t] / [Ctrl+t]"),
            ("⌨️", "Toggle focus", "[Tab]"),
            ("⌨️", "Focus lines", "[Shift+Tab]"),
            ("⬅️", "Previous speaker", "[Ctrl+b/p] or [p]"),
            ("🚪", "Exit mapping", "[Ctrl+e]"),
            ("✅", "Confirm", "[Enter]"),
            ("❌", "Cancel", "[Esc/Q]"),
        ]
    )
    help_text_control = build_help_text(shortcuts, box_width=None)
    help_height = ((len(shortcuts) + 1) // 2) + 2  # rows + top/bottom border

    kb = KeyBindings()

    def update_status(message: str) -> None:
        nonlocal status_message
        status_message = message

    def get_selected_segment() -> Optional[SegmentRef]:
        if not displayed_indices:
            return None
        if 0 <= selected_offset < len(displayed_indices):
            seg_idx = displayed_indices[selected_offset]
            return segments[seg_idx]
        return None

    def play_segment(pad_before: float, pad_after: float) -> None:
        seg = get_selected_segment()
        if not seg:
            update_status("No segment selected.")
            return
        if not playback_enabled:
            update_status(
                "Playback disabled - audio file not found or tools unavailable."
            )
            return
        if not seg.has_timestamps:
            update_status("No timestamps for this line.")
            return
        if audio_path:
            # Verify audio file exists and is readable
            if not audio_path.exists():
                update_status(f"Audio file not found: {audio_path.name}")
                logger.warning(f"Audio file does not exist: {audio_path}")
                return
            # Stop any current playback first
            player.stop()
            # Attempt to play the segment
            update_status(f"Starting playback... ({seg.start:.1f}s - {seg.end:.1f}s)")
            player.play_segment(
                audio_path,
                seg.start or 0.0,
                seg.end or 0.0,
                pad_before=pad_before,
                pad_after=pad_after,
            )
            # Check if playback actually started by checking if a process was created
            import time

            time.sleep(0.2)  # Give it a moment to start
            proc = player.current_process
            if proc is not None:
                # Give the process a moment to start, then check if it's still running
                time.sleep(0.3)  # Wait longer to see if it fails
                if proc.poll() is None:  # Process is still running
                    # Process is running - audio should be playing
                    # Note: Removed debug log to avoid interfering with menu display
                    # Status message already provides feedback to user
                    update_status(
                        f"▶️ Playing ({seg.start:.1f}s - {seg.end:.1f}s)"
                    )
                else:
                    # Process exited immediately - playback failed
                    exit_code = (
                        proc.returncode if proc.returncode is not None else "unknown"
                    )
                    error_msg = f"Playback failed (exit code: {exit_code})"
                    logger.warning(
                        f"{error_msg} - segment {seg.start:.1f}s-{seg.end:.1f}s"
                    )
                    update_status(error_msg)
            elif player.is_playing:
                update_status(
                    f"▶️ Playing ({seg.start:.1f}s - {seg.end:.1f}s)"
                )
            else:
                # No process was created - check what's available
                from transcriptx.cli.audio import (
                    check_ffplay_available,
                    check_ffmpeg_available,
                )

                ffplay_avail, ffplay_err = check_ffplay_available()
                ffmpeg_avail, ffmpeg_err = check_ffmpeg_available()
                if not ffplay_avail and not ffmpeg_avail:
                    update_status(
                        "❌ Playback unavailable. Install ffmpeg for audio preview."
                    )
                    logger.warning(
                        f"Playback tools unavailable: ffplay={ffplay_err}, ffmpeg={ffmpeg_err}"
                    )
                else:
                    update_status(
                        f"❌ Playback failed. Audio: {audio_path.name if audio_path else 'None'}"
                    )
                    logger.warning(
                        f"Playback failed - no process created. Audio: {audio_path}, exists: {audio_path.exists() if audio_path else False}"
                    )
        else:
            update_status("No audio file path provided.")

    def load_more_lines() -> None:
        nonlocal selected_offset, refresh_counter
        if not append_batch():
            update_status("No more lines.")
            return
        # Reset selection to top of the newly loaded page.
        selected_offset = 0
        # Increment refresh counter to force UI control to re-evaluate
        refresh_counter += 1
        update_status("Loaded more lines.")

    def reset_display() -> None:
        nonlocal cursor, displayed_indices, selected_offset, refresh_counter
        cursor = 0
        displayed_indices = []
        selected_offset = 0
        refresh_counter += 1  # Force UI refresh
        append_batch()

    def toggle_sort_mode() -> None:
        nonlocal sort_mode
        sort_mode = "chronological" if sort_mode == "unique" else "unique"
        apply_sort_mode()
        reset_display()
        update_status(
            "Showing chronological order."
            if sort_mode == "chronological"
            else "Showing most unique lines first."
        )

    @kb.add("up")
    def move_up(event):
        nonlocal selected_offset
        if selected_offset > 0:
            selected_offset -= 1
        event.app.invalidate()

    @kb.add("down")
    def move_down(event):
        nonlocal selected_offset
        if selected_offset < len(displayed_indices) - 1:
            selected_offset += 1
        event.app.invalidate()

    @kb.add("right")
    def play_exact(event):
        play_segment(0.0, 0.0)
        event.app.invalidate()

    @kb.add("s-right")
    def play_short_context(event):
        play_segment(0.8, 0.8)
        event.app.invalidate()

    @kb.add("c-right")
    def play_long_context(event):
        play_segment(3.0, 3.0)
        event.app.invalidate()

    @kb.add("left")
    def stop_playback(event):
        """Stop current playback when left arrow is pressed."""
        player.stop()
        update_status("Playback stopped.")
        event.app.invalidate()

    @kb.add("m", filter=~has_focus(name_input))
    def load_more(event):
        load_more_lines()
        event.app.invalidate()

    # Global shortcut: works even when name_input has focus.
    # Note: We intentionally do NOT use Ctrl+M because Ctrl+M is Enter in terminals.
    @kb.add("c-l")
    def load_more_ctrl_l(event):
        load_more_lines()
        event.app.invalidate()

    @kb.add("t", filter=~has_focus(name_input))
    def toggle_sort(event):
        toggle_sort_mode()
        event.app.invalidate()

    # Global shortcut: works even when name_input has focus.
    @kb.add("c-t")
    def toggle_sort_ctrl_t(event):
        toggle_sort_mode()
        event.app.invalidate()

    @kb.add("tab")
    def toggle_focus(event):
        """Toggle focus between transcript lines and the name input field."""
        if event.app.layout.has_focus(name_input):
            event.app.layout.focus(lines_window)
        else:
            event.app.layout.focus(name_input)
        event.app.invalidate()

    @kb.add("s-tab")
    def focus_lines(event):
        """Focus the transcript lines window (Shift+Tab)."""
        event.app.layout.focus(lines_window)
        event.app.invalidate()

    @kb.add("c-b")
    def go_back_ctrl_b(event):
        """Go back to previous speaker (Ctrl+B - works globally)."""
        player.cleanup()
        event.app.exit(result=GO_BACK_SENTINEL)
    
    @kb.add("c-p")
    def go_back_ctrl_p(event):
        """Go back to previous speaker (Ctrl+P - alternative if Ctrl+B doesn't work)."""
        player.cleanup()
        event.app.exit(result=GO_BACK_SENTINEL)
    
    @kb.add("p", filter=~has_focus(name_input))
    def go_back_p(event):
        """Go back to previous speaker (P key - works when name field is not focused)."""
        player.cleanup()
        event.app.exit(result=GO_BACK_SENTINEL)

    @kb.add("c-e")
    def exit_mapping(event):
        """Exit speaker mapping and return to menu."""
        player.cleanup()
        event.app.exit(result=EXIT_SENTINEL)

    @kb.add("enter")
    def confirm(event):
        action, value = _parse_user_input(name_input.text)
        if action == "name" and value:
            player.cleanup()
            event.app.exit(result=value)
            return
        if action == "more":
            load_more_lines()
            name_input.text = ""
            event.app.invalidate()
            return
        if existing_name:
            player.cleanup()
            event.app.exit(result="")
            return
        if cursor < len(segments):
            load_more_lines()
            name_input.text = ""
            event.app.invalidate()
            return
        player.cleanup()
        event.app.exit(result="")

    @kb.add("escape")
    @kb.add("q")
    def cancel(event):
        player.cleanup()
        event.app.exit(result=None)

    @kb.add("c-c")
    def cancel_ctrl(event):
        player.cleanup()
        event.app.exit(result=None)

    lines_window = Window(lines_control, height=10)
    layout = Layout(
        HSplit(
            [
                Window(header_control, height=3),
                lines_window,
                Window(status_control, height=1),
                Window(help_text_control, height=help_height),
                name_input,
            ]
        )
    )
    # Default focus on the transcript lines so navigation shortcuts work immediately.
    layout.focus(lines_window)
    app = Application(layout=layout, key_bindings=kb, full_screen=False)
    result = app.run()
    player.cleanup()
    return result


def _select_name_with_playback(
    speaker_id: str,
    segments: List[SegmentRef],
    existing_name: Optional[str],
    audio_path: Optional[Path],
) -> Optional[str]:
    """Interactive prompt_toolkit UI to pick a name with playback controls."""
    return _interactive_speaker_naming(
        speaker_id=speaker_id,
        segments=segments,
        existing_name=existing_name,
        audio_path=audio_path,
    )
