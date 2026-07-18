"""Top-level TranscriptX configuration."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Callable, Optional

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
    MetadataConfig,
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
        self.metadata = MetadataConfig()

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
        from transcriptx.core.utils.config.config_raw_validation import (
            validate_applied_llm_config,
        )

        validate_applied_llm_config(self.llm)

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
        Return a curated configuration snapshot as a dictionary.

        Curated projection (not ``asdict(self.analysis)``): deliberately omits
        runtime-only fields such as ``analysis.use_dag_pipeline`` and ``self.mode``.
        Adapter ``active_*`` profile keys are emitted via
        ``write_activation_value``. Nested dataclass subtrees use
        ``_config_to_dict`` / ``asdict`` (deep copy); some flat list/dict
        analysis fields are returned by reference (aliasing preserved).
        """
        from transcriptx.core.config import iter_all_profile_target_adapters

        flat_active_profiles: dict[str, Any] = {}
        analysis_active_profiles: dict[str, Any] = {}
        root_active_profiles: dict[str, Any] = {}
        for adapter in iter_all_profile_target_adapters():
            value = adapter.get_active_profile_name(self)
            adapter.write_activation_value(
                value=value,
                flat_map=flat_active_profiles,
                analysis_map=analysis_active_profiles,
                root_map=root_active_profiles,
            )

        # Explicit curated analysis shell — do not dump the whole AnalysisConfig.
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
                "semantic_progress_log_interval_seconds": self.analysis.semantic_progress_log_interval_seconds,
                "module_progress_log_interval_seconds": self.analysis.module_progress_log_interval_seconds,
                "output_formats": self.analysis.output_formats,
                # Parallel processing removed - using DAG pipeline instead
                # Max workers removed - using DAG pipeline instead
                "analysis_mode": self.analysis.analysis_mode,
                "include_legacy_modules": self.analysis.include_legacy_modules,
                "quick_analysis_settings": self.analysis.quick_analysis_settings,
                "full_analysis_settings": self.analysis.full_analysis_settings,
                "semantic_similarity_v2": self._config_to_dict(
                    self.analysis.semantic_similarity_v2
                ),
                "active_semantic_similarity_v2_profile": (
                    self.analysis.active_semantic_similarity_v2_profile
                ),
                "semantic_similarity_v2_profiles": (
                    self.analysis.semantic_similarity_v2_profiles
                ),
                # Module-specific configs
                "topic_modeling": self._config_to_dict(self.analysis.topic_modeling),
                "acts": self._config_to_dict(self.analysis.acts),
                "tag_extraction": self._config_to_dict(self.analysis.tag_extraction),
                "llm_summary": self._config_to_dict(self.analysis.llm_summary),
                "llm_speaker_summary": self._config_to_dict(
                    self.analysis.llm_speaker_summary
                ),
                "llm_action_items": self._config_to_dict(
                    self.analysis.llm_action_items
                ),
                "qa_analysis": self._config_to_dict(self.analysis.qa_analysis),
                "temporal_dynamics": self._config_to_dict(
                    self.analysis.temporal_dynamics
                ),
                "vectorization": self._config_to_dict(self.analysis.vectorization),
                "voice": self._config_to_dict(self.analysis.voice),
                "affect_tension": self._config_to_dict(self.analysis.affect_tension),
                "emotion": self._config_to_dict(self.analysis.emotion),
                "contextual_emotion": self._config_to_dict(
                    self.analysis.contextual_emotion
                ),
                "fine_grained_emotion": self._config_to_dict(
                    self.analysis.fine_grained_emotion
                ),
                "speaker_exemplars": self._config_to_dict(
                    self.analysis.speaker_exemplars
                ),
                "corrections": self._config_to_dict(self.analysis.corrections),
                "highlights": self._config_to_dict(self.analysis.highlights),
                "summary": self._config_to_dict(self.analysis.summary),
                "bertopic": self._config_to_dict(self.analysis.bertopic),
                "pauses": self._config_to_dict(self.analysis.pauses),
                "echoes": self._config_to_dict(self.analysis.echoes),
                "momentum": self._config_to_dict(self.analysis.momentum),
                "moments": self._config_to_dict(self.analysis.moments),
                # Active profiles
                **analysis_active_profiles,
            },
            "input": {
                "wav_folders": self.input.wav_folders,
                "recordings_folders": self.input.recordings_folders,
                "prefill_rename_with_date_prefix": getattr(
                    self.input, "prefill_rename_with_date_prefix", True
                ),
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
            "llm": self._config_to_dict(self.llm),
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
            "metadata": self._config_to_dict(self.metadata),
            **root_active_profiles,
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
        from transcriptx.core.config.persistence import save_config_atomic

        config_data = self.to_dict()
        save_config_atomic(config_data, Path(config_file))

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
    """Backward-compatible no-op: defaults are virtual and not persisted."""
    return None
