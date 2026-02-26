"""
Speaker Utilities for TranscriptX.

⚠️ DEPRECATED MODULE - MIGRATION IN PROGRESS ⚠️

This module has been moved to transcriptx.core.utils.speaker_profiling.
**This module will be removed in v0.3.0**. Please migrate to the new module.

Migration Guide:
    OLD (deprecated):                    NEW (preferred):
    from transcriptx.speaker_utils import *    from transcriptx.core.utils.speaker_profiling import (
                                                    get_speaker_profile,
                                                    update_speaker_profile,
                                                    SpeakerRegistry,
                                                    SPEAKER_DIR,
                                                )

Current Status:
- Functions are re-exported for backward compatibility
- New code should use transcriptx.core.utils.speaker_profiling
"""

import warnings

# Import from new location
from transcriptx.core.utils.speaker_profiling import (
    get_speaker_profile,
    update_speaker_profile,
    SpeakerRegistry,
    SPEAKER_DIR,
)


def _deprecation_warning(func_name: str):
    """Issue deprecation warning for functions being moved."""
    warnings.warn(
        f"transcriptx.speaker_utils.{func_name} is deprecated and will be removed in v0.3.0. "
        f"Use transcriptx.core.utils.speaker_profiling.{func_name} instead.",
        DeprecationWarning,
        stacklevel=3,
    )


# Re-export with deprecation warnings on first use
# Note: We can't easily wrap functions with deprecation warnings without breaking usage
# So we'll just re-export them directly and let the module-level deprecation notice handle it

__all__ = [
    "get_speaker_profile",
    "update_speaker_profile",
    "SpeakerRegistry",
    "SPEAKER_DIR",
]
