"""Top-level TranscriptX configuration."""

from __future__ import annotations

from typing import Any, Callable, Optional
from pathlib import Path
import json

try:
    from dotenv import load_dotenv as _load_dotenv
except Exception:  # pragma: no cover - optional dependency guard
    _load_dotenv = None

load_dotenv: Optional[Callable[..., bool]] = _load_dotenv
from .analysis import AnalysisConfig


def get_install_profile() -> Optional[str]:
    """Return install profile from marker file: 'core', 'full', or None if absent. Used for core_mode resolution."""
    from transcriptx.core.utils.paths import CONFIG_DIR

    path = CONFIG_DIR / "install_profile"
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip() or None
        except Exception:
            return None
    return None


from .workflow import (
    WorkflowConfig,
    InputConfig,
    OutputConfig,
    GroupAnalysisConfig,
    DashboardConfig,
)
from .system import LLMConfig, LoggingConfig, AudioPreprocessingConfig


class TranscriptXConfig:
    """
    Main configuration class for TranscriptX.

    This is the central configuration class that manages all settings for the
    TranscriptX system. It combines configuration from multiple sources:
    - Default values
    - Environment variables
    - Configuration files

    The configuration is organized into logical sections:
    - analysis: Settings for all analysis modules
    - output: Settings for file output and organization
    - logging: Settings for logging system

    Configuration can be loaded from JSON files and environment variables,
    with environment variables taking precedence over file settings.
    """

    def __init__(self, config_file: str | None = None):
        """
        Initialize configuration with default values and optional file loading.

        Args:
            config_file: Path to configuration file (JSON format). If provided,
                        the file will be loaded after setting defaults and
                        environment variables.

        Note:
            Configuration loading order (highest to lowest priority):
            1. Environment variables
            2. Configuration file (if provided)
            3. Default values
        """
        # Initialize all configuration sections with default values
        self.analysis = AnalysisConfig()
        self.input = InputConfig()
        self.output = OutputConfig()
        self.logging = LoggingConfig()
        self.llm = LLMConfig()
        self.audio_preprocessing = AudioPreprocessingConfig()
        self.workflow = WorkflowConfig()
        self.group_analysis = GroupAnalysisConfig()
        self.dashboard = DashboardConfig()

        # Global settings
        self.mode = "simple"  # 'simple' or 'advanced' - controls UI complexity
        self.use_emojis = True  # Enable/disable emojis globally in output

        # Core mode: if True, only core modules and no auto-install of optional deps. Resolve: env > config file > install marker.
        self.core_mode: bool = True
        profile = get_install_profile()
        if profile == "full":
            self.core_mode = False

        # Active workflow profile
        self.active_workflow_profile: str = "default"

        # Load from config file if provided
        # File settings override defaults but not environment variables
        if config_file:
            self._load_from_file(config_file)

        # Load active profiles for each module
        # Profile settings override defaults and file settings but not environment variables
        self._load_module_profiles()

        # Load configuration from environment variables last
        # Environment variables take highest priority
        self._load_from_env()

    def _load_from_env(self):
        from transcriptx.core.utils.config.env_overrides import apply_transcriptx_env

        apply_transcriptx_env(self)

    def _load_from_file(self, config_file: str):
        """
        Load configuration from JSON file.

        This method reads a JSON configuration file and updates the configuration
        settings. The JSON file should have a structure that matches the
        configuration class hierarchy.

        Args:
            config_file: Path to the JSON configuration file

        Raises:
            ValueError: If the file cannot be read or parsed

        Note:
            The JSON file should have sections matching the configuration classes.
            Unsupported sections (e.g. ``transcription``) and legacy shapes raise
            ``ConfigLoadError`` with a migration-directional message.
        """
        from transcriptx.core.utils.config.file_overrides import load_config_file_into

        load_config_file_into(self, config_file)

    def _load_module_profiles(self):
        """
        Load active profiles for each module.

        Profile settings override defaults and file settings but not environment variables.
        If a profile doesn't exist, the default values from the dataclass are used.
        """
        from transcriptx.core.utils.config.profile_loading import load_module_profiles

        load_module_profiles(self)

    def _apply_profile_to_config(self, config_obj: Any, profile_data: dict[str, Any]):
        """
        Apply profile data to a config object.

        Args:
            config_obj: The config dataclass instance to update
            profile_data: Dictionary with profile settings
        """
        from transcriptx.core.utils.config.profile_loading import (
            apply_profile_to_config,
        )

        apply_profile_to_config(config_obj, profile_data)

    def _config_to_dict(self, config_obj: Any) -> dict[str, Any]:
        """
        Convert a config dataclass to a dictionary.

        Args:
            config_obj: The config dataclass instance

        Returns:
            Dictionary representation of the config
        """
        from dataclasses import asdict

        return asdict(config_obj)

    def to_dict(self) -> dict[str, Any]:
        """
        Return a complete configuration snapshot as a dictionary.
        """
        return {
            "analysis": {
                "sentiment_window_size": self.analysis.sentiment_window_size,
                "sentiment_min_confidence": self.analysis.sentiment_min_confidence,
                "emotion_min_confidence": self.analysis.emotion_min_confidence,
                "emotion_model_name": self.analysis.emotion_model_name,
                "emotion_output_mode": self.analysis.emotion_output_mode,
                "emotion_score_threshold": self.analysis.emotion_score_threshold,
                "sentiment_backend": self.analysis.sentiment_backend,
                "sentiment_model_name": self.analysis.sentiment_model_name,
                "ner_labels": self.analysis.ner_labels,
                "ner_min_confidence": self.analysis.ner_min_confidence,
                "ner_include_geocoding": self.analysis.ner_include_geocoding,
                "ner_use_light_model": self.analysis.ner_use_light_model,
                "ner_max_segments": self.analysis.ner_max_segments,
                "ner_batch_size": self.analysis.ner_batch_size,
                "wordcloud_max_words": self.analysis.wordcloud_max_words,
                "wordcloud_min_font_size": self.analysis.wordcloud_min_font_size,
                "wordcloud_stopwords": self.analysis.wordcloud_stopwords,
                "exclude_unidentified_from_speaker_charts": self.analysis.exclude_unidentified_from_speaker_charts,
                "readability_metrics": self.analysis.readability_metrics,
                "interaction_overlap_threshold": self.analysis.interaction_overlap_threshold,
                "interaction_min_gap": self.analysis.interaction_min_gap,
                "interaction_min_segment_length": self.analysis.interaction_min_segment_length,
                "interaction_response_threshold": self.analysis.interaction_response_threshold,
                "interaction_include_responses": self.analysis.interaction_include_responses,
                "interaction_include_overlaps": self.analysis.interaction_include_overlaps,
                "interaction_min_interactions": self.analysis.interaction_min_interactions,
                "interaction_time_window": self.analysis.interaction_time_window,
                "entity_min_mentions": self.analysis.entity_min_mentions,
                "entity_types": self.analysis.entity_types,
                "entity_sentiment_threshold": self.analysis.entity_sentiment_threshold,
                "loop_max_intermediate_turns": self.analysis.loop_max_intermediate_turns,
                "loop_exclude_monologues": self.analysis.loop_exclude_monologues,
                "loop_min_gap": self.analysis.loop_min_gap,
                "loop_max_gap": self.analysis.loop_max_gap,
                "semantic_similarity_threshold": self.analysis.semantic_similarity_threshold,
                "cross_speaker_similarity_threshold": self.analysis.cross_speaker_similarity_threshold,
                "repetition_time_window": self.analysis.repetition_time_window,
                "cross_speaker_time_window": self.analysis.cross_speaker_time_window,
                "semantic_model_name": self.analysis.semantic_model_name,
                "clustering_eps": self.analysis.clustering_eps,
                "clustering_min_samples": self.analysis.clustering_min_samples,
                "max_segments_for_semantic": self.analysis.max_segments_for_semantic,
                "max_segments_per_speaker": self.analysis.max_segments_per_speaker,
                "max_segments_for_cross_speaker": self.analysis.max_segments_for_cross_speaker,
                "use_quality_filtering": self.analysis.use_quality_filtering,
                "min_segment_quality_score": self.analysis.min_segment_quality_score,
                "quality_filtering_profile": self.analysis.quality_filtering_profile,
                "semantic_similarity_method": self.analysis.semantic_similarity_method,
                "quality_filtering_profiles": self.analysis.quality_filtering_profiles,
                "quality_weights_override": self.analysis.quality_weights_override,
                "quality_thresholds_override": self.analysis.quality_thresholds_override,
                "quality_indicators_override": self.analysis.quality_indicators_override,
                "max_semantic_comparisons": self.analysis.max_semantic_comparisons,
                "semantic_timeout_seconds": self.analysis.semantic_timeout_seconds,
                "semantic_batch_size": self.analysis.semantic_batch_size,
                "output_formats": self.analysis.output_formats,
                # Parallel processing removed - using DAG pipeline instead
                # Max workers removed - using DAG pipeline instead
                "analysis_mode": self.analysis.analysis_mode,
                "quick_analysis_settings": self.analysis.quick_analysis_settings,
                "full_analysis_settings": self.analysis.full_analysis_settings,
                # Module-specific configs
                "topic_modeling": self._config_to_dict(self.analysis.topic_modeling),
                "acts": self._config_to_dict(self.analysis.acts),
                "tag_extraction": self._config_to_dict(self.analysis.tag_extraction),
                "qa_analysis": self._config_to_dict(self.analysis.qa_analysis),
                "temporal_dynamics": self._config_to_dict(
                    self.analysis.temporal_dynamics
                ),
                "vectorization": self._config_to_dict(self.analysis.vectorization),
                "voice": self._config_to_dict(self.analysis.voice),
                "affect_tension": self._config_to_dict(self.analysis.affect_tension),
                "speaker_exemplars": self._config_to_dict(
                    self.analysis.speaker_exemplars
                ),
                # Active profiles
                "active_topic_modeling_profile": self.analysis.active_topic_modeling_profile,
                "active_acts_profile": self.analysis.active_acts_profile,
                "active_tag_extraction_profile": self.analysis.active_tag_extraction_profile,
                "active_qa_analysis_profile": self.analysis.active_qa_analysis_profile,
                "active_temporal_dynamics_profile": self.analysis.active_temporal_dynamics_profile,
                "active_vectorization_profile": self.analysis.active_vectorization_profile,
            },
            "input": {
                "wav_folders": self.input.wav_folders,
                "recordings_folders": self.input.recordings_folders,
                "file_selection_mode": getattr(
                    self.input, "file_selection_mode", "prompt"
                ),
                "playback_skip_seconds_short": getattr(
                    self.input, "playback_skip_seconds_short", 10.0
                ),
                "playback_skip_seconds_long": getattr(
                    self.input, "playback_skip_seconds_long", 60.0
                ),
            },
            "output": {
                "base_output_dir": self.output.base_output_dir,
                "create_subdirectories": self.output.create_subdirectories,
                "overwrite_existing": self.output.overwrite_existing,
                "dynamic_charts": self.output.dynamic_charts,
                "dynamic_views": self.output.dynamic_views,
                "default_audio_folder": self.output.default_audio_folder,
                "default_transcript_folder": self.output.default_transcript_folder,
                "default_readable_transcript_folder": self.output.default_readable_transcript_folder,
                "audio_deduplication_threshold": self.output.audio_deduplication_threshold,
            },
            "logging": {
                "level": self.logging.level,
                "format": self.logging.format,
                "file_logging": self.logging.file_logging,
                "log_file": self.logging.log_file,
                "max_log_size": self.logging.max_log_size,
                "backup_count": self.logging.backup_count,
            },
            "audio_preprocessing": {
                "preprocessing_mode": self.audio_preprocessing.preprocessing_mode,
                "convert_to_mono": self.audio_preprocessing.convert_to_mono,
                "downsample": self.audio_preprocessing.downsample,
                "target_sample_rate": self.audio_preprocessing.target_sample_rate,
                "skip_if_already_compliant": self.audio_preprocessing.skip_if_already_compliant,
                "normalize_mode": self.audio_preprocessing.normalize_mode,
                "target_lufs": self.audio_preprocessing.target_lufs,
                "limiter_enabled": self.audio_preprocessing.limiter_enabled,
                "limiter_peak_db": self.audio_preprocessing.limiter_peak_db,
                "denoise_mode": self.audio_preprocessing.denoise_mode,
                "denoise_strength": self.audio_preprocessing.denoise_strength,
                "highpass_mode": self.audio_preprocessing.highpass_mode,
                "highpass_cutoff": self.audio_preprocessing.highpass_cutoff,
                "lowpass_mode": self.audio_preprocessing.lowpass_mode,
                "lowpass_cutoff": self.audio_preprocessing.lowpass_cutoff,
                "bandpass_mode": self.audio_preprocessing.bandpass_mode,
                "bandpass_low": self.audio_preprocessing.bandpass_low,
                "bandpass_high": self.audio_preprocessing.bandpass_high,
            },
            "workflow": self._config_to_dict(self.workflow),
            "group_analysis": self._config_to_dict(self.group_analysis),
            "dashboard": self._config_to_dict(self.dashboard),
            "active_workflow_profile": self.active_workflow_profile,
            "use_emojis": self.use_emojis,
            "core_mode": self.core_mode,
        }

    def save_to_file(self, config_file: str):
        """
        Save current configuration to JSON file.

        This method serializes the current configuration state to a JSON file,
        preserving all settings for later use or sharing between systems.

        Args:
            config_file: Path where the configuration file should be saved

        Note:
            The saved file will contain all current configuration values,
            including any that were set via environment variables or
            programmatically. This provides a complete snapshot of the
            configuration state.
        """
        config_data = self.to_dict()
        with open(config_file, "w") as f:
            json.dump(config_data, f, indent=2, default=str)

    def get_quality_filtering_config(self) -> dict[str, Any]:
        """
        Get the active quality filtering configuration, applying profile and overrides.

        Returns:
            Dictionary with weights, thresholds, and indicators from active profile + overrides
        """
        profile_name = getattr(self.analysis, "quality_filtering_profile", "balanced")
        profiles = getattr(self.analysis, "quality_filtering_profiles", {})

        if profile_name not in profiles:
            from transcriptx.core.utils.logger import log_warning

            log_warning(
                "CONFIG", f"Unknown quality profile '{profile_name}', using 'balanced'"
            )
            profile_name = "balanced"

        profile_config = profiles[profile_name]

        # Apply overrides if specified
        config = {
            "weights": profile_config["weights"].copy(),
            "thresholds": profile_config["thresholds"].copy(),
            "indicators": profile_config["indicators"].copy(),
        }

        if self.analysis.quality_weights_override:
            config["weights"].update(self.analysis.quality_weights_override)

        if self.analysis.quality_thresholds_override:
            config["thresholds"].update(self.analysis.quality_thresholds_override)

        if self.analysis.quality_indicators_override:
            config["indicators"].update(self.analysis.quality_indicators_override)

        return config

    def list_quality_profiles(self) -> dict[str, str]:
        """
        List available quality filtering profiles with descriptions.

        Returns:
            Dictionary mapping profile names to descriptions
        """
        profiles = getattr(self.analysis, "quality_filtering_profiles", {})
        return {name: profile["description"] for name, profile in profiles.items()}

    def get_output_path(self, base_name: str, module: str) -> str:
        """
        Generate output path for a specific module.

        Note: For new code, use transcriptx.core.utils.output_structure.create_output_structure()
        instead, which provides a more flexible and configurable interface.
        """
        from transcriptx.core.utils.output_structure import create_output_structure

        # Use new output structure system
        structure = create_output_structure(
            transcript_path=f"{base_name}.json",  # Dummy path for structure creation
            module_name=module,
            base_name=base_name,
        )
        return str(structure.module_dir)

    def get_smart_output_dir(self, input_path: str) -> str:
        """
        Return a smart default output directory for a given transcript or audio file.
        Always creates a subfolder with the base name of the input file.

        Note: For new code, use transcriptx.core.utils.output_structure.create_output_structure()
        instead, which provides a more flexible and configurable interface.
        """
        from transcriptx.core.utils.output_structure import create_output_structure

        p = Path(input_path)
        base_name = p.stem

        # Use new output structure system
        structure = create_output_structure(
            transcript_path=str(input_path),
            module_name="",  # Empty for base structure
            base_name=base_name,
        )
        return str(structure.transcript_dir)


# Global configuration instance
_config: TranscriptXConfig | None = None


def get_config() -> TranscriptXConfig:
    """
    Get the global configuration instance.

    Note: For thread-local configuration support, use config_provider.get_config()
    instead. This function maintains backward compatibility.
    """
    global _config
    if _config is None:
        _config = TranscriptXConfig()
        # Initialize default profiles if they don't exist
        initialize_default_profiles()
    return _config


def set_config(config: TranscriptXConfig):
    """Set the global configuration instance."""
    global _config
    _config = config


def load_config(config_file: str) -> TranscriptXConfig:
    """Load configuration from file and set as global config."""
    config = TranscriptXConfig(config_file)
    set_config(config)
    return config


def initialize_default_profiles():
    """
    Initialize default profiles for all modules with sensible defaults.

    This function should be called once to create default profiles if they don't exist.
    """
    from transcriptx.core.utils.profile_manager import get_profile_manager

    profile_manager = get_profile_manager()

    # Initialize topic modeling default profile
    if not profile_manager.profile_exists("topic_modeling", "default"):
        topic_defaults = {
            "max_features": 1000,
            "min_df": 2,
            "max_df": 0.95,
            "ngram_range": [1, 2],
            "random_state": 42,
            "max_iter_lda": 50,
            "max_iter_nmf": 10000,
            "alpha_H": 0.1,
            "tol": 1e-2,
            "learning_method": "batch",
            "k_range": [3, 15],
            "test_size": 0.2,
        }
        profile_manager.create_default_profile(
            "topic_modeling",
            topic_defaults,
            "Default topic modeling profile with balanced settings",
        )

    # Initialize acts default profile
    if not profile_manager.profile_exists("acts", "default"):
        acts_defaults = {
            "method": "both",
            "use_context": True,
            "context_window_size": 3,
            "context_window_type": "sliding",
            "include_speaker_info": True,
            "include_timing_info": False,
            "min_confidence": 0.7,
            "high_confidence_threshold": 0.9,
            "ensemble_weight_transformer": 0.5,
            "ensemble_weight_ml": 0.3,
            "ensemble_weight_rules": 0.2,
            "ml_model_name": "bert-base-uncased",
            "ml_use_gpu": False,
            "ml_batch_size": 32,
            "ml_max_length": 512,
            "rules_use_enhanced_patterns": True,
            "rules_use_fallback_logic": True,
            "rules_confidence_boost_exact_match": 0.1,
            "rules_context_boost_factor": 0.15,
            "enable_caching": True,
            "cache_size": 1000,
        }
        profile_manager.create_default_profile(
            "acts", acts_defaults, "Default dialogue acts classification profile"
        )

    # Initialize tag extraction default profile
    if not profile_manager.profile_exists("tag_extraction", "default"):
        tag_defaults = {
            "early_window_seconds": 60,
            "early_segments": 10,
            "min_confidence": 0.6,
        }
        profile_manager.create_default_profile(
            "tag_extraction", tag_defaults, "Default tag extraction profile"
        )

    # Initialize QA analysis default profile
    if not profile_manager.profile_exists("qa_analysis", "default"):
        qa_defaults = {
            "response_time_threshold": 10.0,
            "weight_directness": 0.3,
            "weight_completeness": 0.3,
            "weight_relevance": 0.25,
            "weight_length": 0.15,
            "min_match_threshold": 0.3,
            "good_match_threshold": 0.5,
            "high_match_threshold": 0.7,
            "min_answer_length": 2,
            "optimal_answer_length": 5,
            "max_answer_length": 50,
        }
        profile_manager.create_default_profile(
            "qa_analysis", qa_defaults, "Default Q&A analysis profile"
        )

    # Initialize temporal dynamics default profile
    if not profile_manager.profile_exists("temporal_dynamics", "default"):
        temporal_defaults = {
            "window_size": 30.0,
            "weight_segment_factor": 0.4,
            "weight_length_factor": 0.3,
            "weight_question_factor": 0.3,
            "max_segments_normalization": 10.0,
            "max_questions_normalization": 5.0,
            "opening_phase_percentage": 0.1,
            "opening_phase_max_seconds": 120.0,
            "closing_phase_percentage": 0.1,
            "closing_phase_max_seconds": 120.0,
            "sentiment_change_threshold": 0.1,
            "engagement_change_threshold": 0.05,
            "speaking_rate_change_threshold": 10.0,
        }
        profile_manager.create_default_profile(
            "temporal_dynamics", temporal_defaults, "Default temporal dynamics profile"
        )

    # Initialize vectorization default profile
    if not profile_manager.profile_exists("vectorization", "default"):
        vector_defaults = {
            "max_features": 1000,
            "min_df": 1,
            "max_df": 0.95,
            "ngram_range": [1, 2],
            "wordcloud_max_features": 300,
            "wordcloud_ngram_range": [1, 2],
        }
        profile_manager.create_default_profile(
            "vectorization", vector_defaults, "Default vectorization profile"
        )

    # Initialize workflow default profile
    if not profile_manager.profile_exists("workflow", "default"):
        workflow_defaults = {
            "timeout_quick_seconds": 3600,
            "timeout_full_seconds": 7200,
            "update_interval": 10.0,
            "max_size_mb": 30,
            "subprocess_timeout": 5,
            "mp3_bitrate": "192k",
            "conversion_time_factor": 0.5,
            "speaker_gate": {
                "threshold_value": 0.0,
                "threshold_type": "absolute",
                "mode": "warn",
                "exemplar_count": 2,
            },
            "cli_pruning_enabled": False,
            "default_config_save_path": "",
        }
        profile_manager.create_default_profile(
            "workflow", workflow_defaults, "Default workflow profile"
        )
