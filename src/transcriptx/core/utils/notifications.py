"""
User notification utilities for TranscriptX.

This module provides a unified notification system that respects
the user's configuration preferences. It can show different levels
of detail based on whether the user is in 'simple' or 'advanced' mode.
"""

from rich.console import Console
from rich.style import Style

from transcriptx.utils.text_utils import strip_emojis

console = Console()

# Track the current module to print section breaks only when starting a new module
_current_module: str | None = None

# Color mapping for different modules to provide visual organization
# Each module gets a distinct color for its notifications and section breaks
# This helps users quickly identify which part of the system is active
# Using a mix of standard and extended Rich color names for maximum distinction
MODULE_COLOR_MAP = {
    # Core operations
    "transcribe": "cyan",  # Audio transcription operations
    "speaker": "magenta",  # Speaker mapping and identification
    "analyze": "green",  # General analysis operations
    # Analysis modules - each gets a unique color for visual distinction
    "sentiment": "yellow",  # Sentiment analysis
    "emotion": "red",  # Emotion detection
    "stats": "blue",  # Statistics generation
    "ner": "bright_cyan",  # Named entity recognition
    "wordclouds": "bright_magenta",  # Word cloud generation
    "interactions": "bright_yellow",  # Speaker interactions
    "transcript_output": "bright_green",  # Transcript output generation
    "acts": "bright_blue",  # Dialogue act classification
    "conversation_loops": "bright_red",  # Conversation loop detection
    "contagion": "bright_white",  # Emotional contagion detection
    "entity_sentiment": "#ff875f",  # Entity-based sentiment analysis (salmon/orange)
    "semantic_similarity": "#af00d7",  # Semantic similarity analysis (dark violet)
    "semantic_similarity_advanced": "#d700ff",  # Advanced semantic similarity (violet)
    "topic_modeling": "#ffd700",  # Topic modeling (gold)
    "tics": "#ff5f00",  # Tics analysis (orange red)
    "understandability": "#00ffaf",  # Understandability analysis (medium spring green)
    "temporal_dynamics": "#00ff87",  # Temporal dynamics analysis (spring green)
    "qa_analysis": "#875fff",  # Q&A analysis (medium slate blue)
    "pauses": "#87ceeb",  # Pauses analysis (sky blue)
    "echoes": "#dda0dd",  # Echoes analysis (plum)
    "momentum": "#f0e68c",  # Momentum analysis (khaki)
    "moments": "#ffb6c1",  # Moments analysis (light pink)
    "default": "white",  # Default color for unknown modules
}

# Emoji mapping for different modules to provide visual feedback
# Each module gets a distinct emoji for quick visual identification
MODULE_EMOJI_MAP = {
    # Core operations
    "transcribe": "🎤",  # Audio transcription operations
    "speaker": "👤",  # Speaker mapping and identification
    "analyze": "🔍",  # General analysis operations
    # Analysis modules
    "sentiment": "😊",  # Sentiment analysis
    "emotion": "😄",  # Emotion detection
    "stats": "📊",  # Statistics generation
    "ner": "🏷️",  # Named entity recognition
    "wordclouds": "💬",  # Word cloud generation
    "interactions": "🤝",  # Speaker interactions
    "transcript_output": "📃",  # Transcript output generation
    "acts": "🗣️",  # Dialogue act classification
    "conversation_loops": "🔄",  # Conversation loop detection
    "contagion": "🌊",  # Emotional contagion detection
    "entity_sentiment": "💭",  # Entity-based sentiment analysis
    "semantic_similarity": "🔗",  # Semantic similarity analysis
    "semantic_similarity_advanced": "🔗",  # Advanced semantic similarity
    "topic_modeling": "💡",  # Topic modeling
    "tics": "✔️",  # Tics analysis
    "understandability": "📖",  # Understandability analysis
    "temporal_dynamics": "⏱️",  # Temporal dynamics analysis
    "qa_analysis": "❓",  # Q&A analysis
    "pauses": "⏸️",  # Pauses analysis
    "echoes": "🔁",  # Echoes analysis
    "momentum": "🚀",  # Momentum analysis
    "moments": "⭐",  # Moments analysis
    "default": "⚙️",  # Default emoji for unknown modules
}


def print_section_break(module: str | None = "default", force: bool = False) -> None:
    """
    Print a colored section break for visual organization.
    Section breaks are printed when starting a new module to provide visual spacing.

    Args:
        module: Module name to determine color
        force: If True, print section break even if it's the same module
    """
    global _current_module

    # Skip if this is the same module and not forced
    if not force and module == _current_module:
        return

    # Check if emojis are enabled
    try:
        from transcriptx.core.utils.config import get_config

        config = get_config()
        use_emojis = getattr(config, "use_emojis", True)
    except ImportError:
        # Fallback to defaults if config is not available
        use_emojis = True

    # Get color for the module (handle None case)
    module_key = module if module else "default"
    color = MODULE_COLOR_MAP.get(module_key, MODULE_COLOR_MAP["default"])

    # Create a section break with module name
    # Format: blank line, horizontal line, emoji + title (caps), horizontal line
    if module and module != "default":
        console.print()  # Blank line for spacing
        console.print("─" * 60, style=Style(color=color))
        # Get emoji for the module (only if emojis are enabled)
        emoji = ""
        if use_emojis:
            emoji = MODULE_EMOJI_MAP.get(module_key, MODULE_EMOJI_MAP["default"]) + " "
        # Format module name: replace underscores with spaces and capitalize
        module_display = module.upper().replace("_", " ")
        # Print with emoji prefix (if enabled)
        console.print(f"{emoji}{module_display}", style=Style(color=color, bold=True))
        console.print("─" * 60, style=Style(color=color))
        _current_module = module
    else:
        console.print()  # Blank line for spacing
        console.print("─" * 60, style=Style(color=color))


def notify_user(
    msg: str, level: str = "info", technical: bool = False, section: str | None = None
) -> None:
    """
    Print/log user notifications based on the configured mode.

    This function provides a unified notification system that respects
    the user's configuration preferences. It can show different levels
    of detail based on whether the user is in 'simple' or 'advanced' mode.

    Args:
        msg: Message to display to the user
        level: Log level (info, warning, error, etc.) - currently for future use
        technical: If True, message is only shown in advanced mode
        section: Optional module name for colored section break

    Usage:
        # User-facing message (shown in both modes)
        notify_user("Transcription complete!", technical=False, section="transcribe")

        # Technical message (only shown in advanced mode)
        notify_user("Model loaded with 1.2GB memory usage", technical=True, section="analyze")

    Note:
        The function automatically handles emoji stripping based on the
        global configuration. It also provides visual organization through
        colored section breaks when a section is specified.
    """
    try:
        from transcriptx.core.utils.config import get_config

        config = get_config()
        mode = getattr(config, "mode", "simple")
        use_emojis = getattr(config, "use_emojis", True)
    except ImportError:
        # Fallback to defaults if config is not available
        mode = "simple"
        use_emojis = True

    # Skip technical messages in simple mode
    if mode == "simple" and technical:
        return

    # Print section break if specified and this is a new module
    # Only print section break for "Running..." messages, not "Completed..." messages
    if section and ("Running" in msg or "🔍" in msg):
        print_section_break(section)

    # Strip emojis if disabled
    display_msg = msg if use_emojis else strip_emojis(msg)
    console.print(display_msg)

    # Add blank line after completion messages for visual spacing
    if section and ("Completed" in msg or "✅" in msg):
        console.print()
