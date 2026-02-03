"""Configuration editor modules.

This package contains modularized configuration editors for different
sections of the TranscriptX configuration.
"""

from .analysis import edit_analysis_config
from .transcription import edit_transcription_config
from .output import edit_output_config
from .input import edit_input_config
from .logging import edit_logging_config
from .audio_preprocessing import edit_audio_preprocessing_config
from .group_analysis import edit_group_analysis_config
from .quality_filtering import edit_quality_filtering_config
from .dashboard import edit_dashboard_config
from .voice import edit_voice_config
from .workflow import edit_workflow_config
from .display import show_current_config
from .save import save_config_interactive

__all__ = [
    "edit_analysis_config",
    "edit_transcription_config",
    "edit_output_config",
    "edit_input_config",
    "edit_logging_config",
    "edit_audio_preprocessing_config",
    "edit_group_analysis_config",
    "edit_quality_filtering_config",
    "edit_dashboard_config",
    "edit_voice_config",
    "edit_workflow_config",
    "show_current_config",
    "save_config_interactive",
]
