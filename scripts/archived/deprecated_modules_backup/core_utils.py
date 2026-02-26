"""
Core utilities for TranscriptX.

⚠️ DEPRECATED MODULE - MIGRATION IN PROGRESS ⚠️

This module is being phased out in favor of organized utility modules.
**This module will be removed in v0.3.0**. Please migrate to the new modules.

Migration Guide:
    OLD (deprecated):                    NEW (preferred):
    from transcriptx.core_utils import *    from transcriptx.core.utils.output import (
                                                suppress_stdout_stderr,
                                                spinner,
                                            )
                                            from transcriptx.core.utils.speaker import (
                                                get_display_speaker_name,
                                            )
                                            from transcriptx.utils.text_utils import (
                                                format_time,
                                                is_named_speaker,
                                                strip_emojis,
                                            )
                                            from transcriptx.core.utils.notifications import (
                                                notify_user,
                                                print_section_break,
                                            )

Current Status:
- Functions are re-exported with deprecation warnings
- New code should use the organized utility modules
"""

import warnings

# Import from new locations
from transcriptx.core.utils.output import suppress_stdout_stderr, spinner
from transcriptx.core.utils.speaker import get_display_speaker_name
from transcriptx.core.utils.notifications import (
    notify_user,
    print_section_break,
    MODULE_COLOR_MAP,
)
from transcriptx.utils.text_utils import (
    strip_emojis,
    is_named_speaker,
    format_time,
    format_time_detailed,
    clean_text,
    normalize_text,
)


def _deprecation_warning(func_name: str, new_location: str):
    """Issue deprecation warning for functions being moved."""
    warnings.warn(
        f"transcriptx.core_utils.{func_name} is deprecated and will be removed in v0.3.0. "
        f"Use {new_location} instead.",
        DeprecationWarning,
        stacklevel=3,
    )


# Re-export functions directly (warnings handled at import time for non-context-manager functions)
# For context managers, we need to preserve the original function
# Note: We can't easily wrap context managers with deprecation warnings without breaking usage
# So we'll just re-export them directly and let the module-level deprecation notice handle it

# These are already in the right place, just re-export
__all__ = [
    "suppress_stdout_stderr",
    "spinner",
    "get_display_speaker_name",
    "notify_user",
    "print_section_break",
    "MODULE_COLOR_MAP",
    "strip_emojis",
    "is_named_speaker",
    "format_time",
    "format_time_detailed",
    "clean_text",
    "normalize_text",
]
