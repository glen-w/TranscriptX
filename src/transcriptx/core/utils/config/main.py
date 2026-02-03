"""Top-level TranscriptX configuration."""

from __future__ import annotations

from typing import Any, Callable, Optional
from pathlib import Path
import json
import os
try:
    from dotenv import load_dotenv as _load_dotenv
except Exception:  # pragma: no cover - optional dependency guard
    _load_dotenv = None

load_dotenv: Optional[Callable[..., bool]] = _load_dotenv
from .analysis import AnalysisConfig
from .workflow import (
    WorkflowConfig,
    TranscriptionConfig,
    InputConfig,
    OutputConfig,
    GroupAnalysisConfig,
    DashboardConfig,
)
from .system import DatabaseConfig, LLMConfig, LoggingConfig, AudioPreprocessingConfig


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
    - transcription: Settings for audio transcription
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
        self.transcription = TranscriptionConfig()
        self.input = InputConfig()
        self.output = OutputConfig()
        self.logging = LoggingConfig()
        self.database = DatabaseConfig()
        self.llm = LLMConfig()
        self.audio_preprocessing = AudioPreprocessingConfig()
        self.workflow = WorkflowConfig()
        self.group_analysis = GroupAnalysisConfig()
        self.dashboard = DashboardConfig()

        # Global settings
        self.mode = "simple"  # 'simple' or 'advanced' - controls UI complexity
        self.use_emojis = True  # Enable/disable emojis globally in output

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
        """
        Load configuration from environment variables.

        This method reads environment variables with the TRANSCRIPTX_ prefix
        and updates the corresponding configuration settings. Environment
        variables provide the highest priority configuration source, allowing
        for easy deployment and containerization.

        Supported environment variables:
        - TRANSCRIPTX_SENTIMENT_WINDOW_SIZE: Sentiment analysis window size
        - TRANSCRIPTX_EMOTION_MODEL: Emotion detection model name
        - TRANSCRIPTX_SEMANTIC_MODEL: Semantic similarity model name
        - TRANSCRIPTX_ACTS_MODEL: Dialogue acts model name
        - TRANSCRIPTX_WORDCLOUD_MAX_WORDS: Maximum words in word clouds
        - TRANSCRIPTX_MODEL_NAME: Transcription model name
        - TRANSCRIPTX_COMPUTE_TYPE: Transcription compute type
        - TRANSCRIPTX_LANGUAGE: Transcription language
        - TRANSCRIPTX_OUTPUT_DIR: Base output directory
        - TRANSCRIPTX_LOG_LEVEL: Logging level
        - TRANSCRIPTX_USE_EMOJIS: Enable/disable emojis (1/true/yes/on or 0/false/no/off)
        """

        # Analysis configuration from environment
        if os.getenv("TRANSCRIPTX_SENTIMENT_WINDOW_SIZE"):
            try:
                self.analysis.sentiment_window_size = int(
                    os.getenv("TRANSCRIPTX_SENTIMENT_WINDOW_SIZE", "10")
                )
            except ValueError:
                pass  # Keep default value if conversion fails

        if os.getenv("TRANSCRIPTX_EMOTION_MODEL"):
            model_name = os.getenv("TRANSCRIPTX_EMOTION_MODEL")
            if model_name:
                self.analysis.emotion_model_name = model_name

        if os.getenv("TRANSCRIPTX_SEMANTIC_MODEL"):
            model_name = os.getenv("TRANSCRIPTX_SEMANTIC_MODEL")
            if model_name:
                self.analysis.semantic_model_name = model_name

        if os.getenv("TRANSCRIPTX_ACTS_MODEL"):
            model_name = os.getenv("TRANSCRIPTX_ACTS_MODEL")
            if model_name:
                self.analysis.acts.ml_model_name = model_name

        if os.getenv("TRANSCRIPTX_WORDCLOUD_MAX_WORDS"):
            try:
                self.analysis.wordcloud_max_words = int(
                    os.getenv("TRANSCRIPTX_WORDCLOUD_MAX_WORDS", "100")
                )
            except ValueError:
                pass  # Keep default value if conversion fails

        # Transcription configuration from environment
        if os.getenv("TRANSCRIPTX_MODEL_NAME"):
            model_name = os.getenv("TRANSCRIPTX_MODEL_NAME")
            if model_name:
                self.transcription.model_name = model_name

        if os.getenv("TRANSCRIPTX_COMPUTE_TYPE"):
            compute_type = os.getenv("TRANSCRIPTX_COMPUTE_TYPE")
            if compute_type:
                self.transcription.compute_type = compute_type

        if os.getenv("TRANSCRIPTX_LANGUAGE"):
            language = os.getenv("TRANSCRIPTX_LANGUAGE")
            if language:
                lang_norm = language.strip().lower()
                # We intentionally avoid WhisperX auto-detect by default. Treat legacy
                # values like "auto"/"none" as English.
                if not lang_norm or lang_norm in ("auto", "none"):
                    self.transcription.language = "en"
                else:
                    self.transcription.language = language

        hf_token = os.getenv("TRANSCRIPTX_HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
        if hf_token:
            self.transcription.huggingface_token = hf_token

        # Input configuration from environment
        if os.getenv("TRANSCRIPTX_WAV_FOLDERS"):
            wav_folders_str = os.getenv("TRANSCRIPTX_WAV_FOLDERS")
            if wav_folders_str:
                # Try to parse as JSON array first, fall back to comma-separated
                try:
                    wav_folders = json.loads(wav_folders_str)
                    if isinstance(wav_folders, list):
                        self.input.wav_folders = wav_folders
                except (json.JSONDecodeError, ValueError):
                    # Parse as comma-separated string
                    wav_folders = [
                        folder.strip()
                        for folder in wav_folders_str.split(",")
                        if folder.strip()
                    ]
                    if wav_folders:
                        self.input.wav_folders = wav_folders

        if os.getenv("TRANSCRIPTX_RECORDINGS_FOLDERS"):
            recordings_folders_str = os.getenv("TRANSCRIPTX_RECORDINGS_FOLDERS")
            if recordings_folders_str:
                # Try to parse as JSON array first, fall back to comma-separated
                try:
                    recordings_folders = json.loads(recordings_folders_str)
                    if isinstance(recordings_folders, list):
                        self.input.recordings_folders = recordings_folders
                except (json.JSONDecodeError, ValueError):
                    # Parse as comma-separated string
                    recordings_folders = [
                        folder.strip()
                        for folder in recordings_folders_str.split(",")
                        if folder.strip()
                    ]
                    if recordings_folders:
                        self.input.recordings_folders = recordings_folders

        if os.getenv("TRANSCRIPTX_FILE_SELECTION_MODE"):
            mode = os.getenv("TRANSCRIPTX_FILE_SELECTION_MODE").strip().lower()
            if mode in ("prompt", "explore", "direct"):
                self.input.file_selection_mode = mode

        # Output configuration from environment
        if os.getenv("TRANSCRIPTX_OUTPUT_DIR"):
            output_dir = os.getenv("TRANSCRIPTX_OUTPUT_DIR")
            if output_dir:
                self.output.base_output_dir = output_dir

        # Logging configuration from environment
        if os.getenv("TRANSCRIPTX_LOG_LEVEL"):
            log_level = os.getenv("TRANSCRIPTX_LOG_LEVEL")
            if log_level:
                self.logging.level = log_level

        # Global emoji configuration from environment
        emoji_env = os.getenv("TRANSCRIPTX_USE_EMOJIS")
        if emoji_env is not None:
            val = emoji_env.strip().lower()
            self.use_emojis = val in ("1", "true", "yes", "on")

        # Database configuration from environment
        db_enabled = os.getenv("TRANSCRIPTX_DB_ENABLED")
        if db_enabled is not None:
            val = db_enabled.strip().lower()
            self.database.enabled = val in ("1", "true", "yes", "on")

        db_auto_store = os.getenv("TRANSCRIPTX_DB_AUTO_STORE_SEGMENTS")
        if db_auto_store is not None:
            val = db_auto_store.strip().lower()
            self.database.auto_store_segments = val in ("1", "true", "yes", "on")

        db_first = os.getenv("TRANSCRIPTX_DB_FIRST")
        if db_first is not None:
            val = db_first.strip().lower()
            self.database.db_first = val in ("1", "true", "yes", "on")

        db_auto_import = os.getenv("TRANSCRIPTX_DB_AUTO_IMPORT")
        if db_auto_import is not None:
            val = db_auto_import.strip().lower()
            self.database.auto_import = val in ("1", "true", "yes", "on")

        db_strict = os.getenv("TRANSCRIPTX_DB_STRICT")
        if db_strict is not None:
            val = db_strict.strip().lower()
            self.database.strict_db = val in ("1", "true", "yes", "on")

        # Audio preprocessing configuration from environment
        # Global preprocessing mode
        if os.getenv("TRANSCRIPTX_AUDIO_PREPROCESSING_MODE"):
            mode = os.getenv("TRANSCRIPTX_AUDIO_PREPROCESSING_MODE").strip().lower()
            if mode in ("selected", "auto", "suggest", "off"):
                self.audio_preprocessing.preprocessing_mode = mode

        # Convert to mono (supports mode or legacy boolean)
        if os.getenv("TRANSCRIPTX_AUDIO_CONVERT_TO_MONO"):
            val = os.getenv("TRANSCRIPTX_AUDIO_CONVERT_TO_MONO").strip().lower()
            if val in ("auto", "suggest", "off"):
                self.audio_preprocessing.convert_to_mono = val
            elif val in ("1", "true", "yes", "on"):
                self.audio_preprocessing.convert_to_mono = "auto"
            elif val in ("0", "false", "no", "off"):
                self.audio_preprocessing.convert_to_mono = "off"

        # Downsample (supports mode or legacy boolean)
        if os.getenv("TRANSCRIPTX_AUDIO_DOWNSAMPLE"):
            val = os.getenv("TRANSCRIPTX_AUDIO_DOWNSAMPLE").strip().lower()
            if val in ("auto", "suggest", "off"):
                self.audio_preprocessing.downsample = val
            elif val in ("1", "true", "yes", "on"):
                self.audio_preprocessing.downsample = "auto"
            elif val in ("0", "false", "no", "off"):
                self.audio_preprocessing.downsample = "off"

        if os.getenv("TRANSCRIPTX_AUDIO_TARGET_SAMPLE_RATE"):
            try:
                self.audio_preprocessing.target_sample_rate = int(
                    os.getenv("TRANSCRIPTX_AUDIO_TARGET_SAMPLE_RATE", "16000")
                )
            except ValueError:
                pass

        # Normalize (supports mode or legacy boolean)
        if os.getenv("TRANSCRIPTX_AUDIO_NORMALIZE_MODE"):
            mode = os.getenv("TRANSCRIPTX_AUDIO_NORMALIZE_MODE").strip().lower()
            if mode in ("auto", "suggest", "off"):
                self.audio_preprocessing.normalize_mode = mode
        if os.getenv("TRANSCRIPTX_AUDIO_NORMALIZE_ENABLED"):  # Legacy support
            val = os.getenv("TRANSCRIPTX_AUDIO_NORMALIZE_ENABLED").strip().lower()
            self.audio_preprocessing.normalize_mode = (
                "auto" if val in ("1", "true", "yes", "on") else "off"
            )

        if os.getenv("TRANSCRIPTX_AUDIO_TARGET_LUFS"):
            try:
                self.audio_preprocessing.target_lufs = float(
                    os.getenv("TRANSCRIPTX_AUDIO_TARGET_LUFS", "-18.0")
                )
            except ValueError:
                pass

        # Denoise (supports mode or legacy boolean)
        if os.getenv("TRANSCRIPTX_AUDIO_DENOISE_MODE"):
            mode = os.getenv("TRANSCRIPTX_AUDIO_DENOISE_MODE").strip().lower()
            if mode in ("auto", "suggest", "off"):
                self.audio_preprocessing.denoise_mode = mode
        if os.getenv("TRANSCRIPTX_AUDIO_DENOISE_ENABLED"):  # Legacy support
            val = os.getenv("TRANSCRIPTX_AUDIO_DENOISE_ENABLED").strip().lower()
            self.audio_preprocessing.denoise_mode = (
                "auto" if val in ("1", "true", "yes", "on") else "off"
            )

        if os.getenv("TRANSCRIPTX_AUDIO_DENOISE_STRENGTH"):
            strength = (
                os.getenv("TRANSCRIPTX_AUDIO_DENOISE_STRENGTH", "medium")
                .strip()
                .lower()
            )
            if strength in ("low", "medium", "high"):
                self.audio_preprocessing.denoise_strength = strength

        # Highpass (supports mode or legacy boolean)
        if os.getenv("TRANSCRIPTX_AUDIO_HIGHPASS_MODE"):
            mode = os.getenv("TRANSCRIPTX_AUDIO_HIGHPASS_MODE").strip().lower()
            if mode in ("auto", "suggest", "off"):
                self.audio_preprocessing.highpass_mode = mode
        if os.getenv("TRANSCRIPTX_AUDIO_HIGHPASS_ENABLED"):  # Legacy support
            val = os.getenv("TRANSCRIPTX_AUDIO_HIGHPASS_ENABLED").strip().lower()
            self.audio_preprocessing.highpass_mode = (
                "auto" if val in ("1", "true", "yes", "on") else "off"
            )

        if os.getenv("TRANSCRIPTX_AUDIO_HIGHPASS_CUTOFF"):
            try:
                self.audio_preprocessing.highpass_cutoff = int(
                    os.getenv("TRANSCRIPTX_AUDIO_HIGHPASS_CUTOFF", "80")
                )
            except ValueError:
                pass

        speaker_gate = getattr(self.workflow, "speaker_gate", None)
        if speaker_gate is not None:
            if os.getenv("TRANSCRIPTX_SPEAKER_GATE_THRESHOLD_VALUE") is not None:
                speaker_gate.threshold_value = os.getenv(
                    "TRANSCRIPTX_SPEAKER_GATE_THRESHOLD_VALUE"
                )
            if os.getenv("TRANSCRIPTX_SPEAKER_GATE_THRESHOLD_TYPE") is not None:
                speaker_gate.threshold_type = os.getenv(
                    "TRANSCRIPTX_SPEAKER_GATE_THRESHOLD_TYPE"
                )
            if os.getenv("TRANSCRIPTX_SPEAKER_GATE_MODE") is not None:
                speaker_gate.mode = os.getenv("TRANSCRIPTX_SPEAKER_GATE_MODE")
            if os.getenv("TRANSCRIPTX_SPEAKER_GATE_EXEMPLAR_COUNT") is not None:
                speaker_gate.exemplar_count = os.getenv(
                    "TRANSCRIPTX_SPEAKER_GATE_EXEMPLAR_COUNT"
                )
            if hasattr(speaker_gate, "validate"):
                speaker_gate.validate()

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
            The JSON file should have sections matching the configuration classes:
            {
                "analysis": { ... },
                "transcription": { ... },
                "output": { ... },
                "logging": { ... },
                "use_emojis": true/false
            }
        """
        dashboard_migrated = False
        if not os.path.exists(config_file):
            return
        try:
            with open(config_file) as f:
                config_data = json.load(f)
            # Support project config format: {"schema_version": N, "config": {...}}
            if isinstance(config_data, dict) and "config" in config_data and "schema_version" in config_data:
                config_data = config_data["config"]

            # Update analysis configuration section
            if "analysis" in config_data:
                for key, value in config_data["analysis"].items():
                    # Handle module-specific configs
                    if key in (
                        "topic_modeling",
                        "acts",
                        "tag_extraction",
                        "qa_analysis",
                        "temporal_dynamics",
                        "vectorization",
                        "voice",
                        "speaker_exemplars",
                        "affect_tension",
                    ):
                        config_obj = getattr(self.analysis, key)
                        if isinstance(value, dict):
                            self._apply_profile_to_config(config_obj, value)
                    # Handle active profile names
                    elif key.startswith("active_") and key.endswith("_profile"):
                        setattr(self.analysis, key, value)
                    # Handle quality_filtering_profiles - convert list thresholds to tuples
                    elif key == "quality_filtering_profiles" and isinstance(
                        value, dict
                    ):
                        # Convert list thresholds to tuples in each profile
                        for profile_name, profile_data in value.items():
                            if (
                                isinstance(profile_data, dict)
                                and "thresholds" in profile_data
                            ):
                                thresholds = profile_data["thresholds"]
                                for (
                                    threshold_key,
                                    threshold_value,
                                ) in thresholds.items():
                                    if (
                                        isinstance(threshold_value, list)
                                        and len(threshold_value) == 2
                                    ):
                                        # Convert list to tuple for ranges
                                        thresholds[threshold_key] = tuple(
                                            threshold_value
                                        )
                        setattr(self.analysis, key, value)
                    # Handle regular analysis config
                    elif hasattr(self.analysis, key):
                        setattr(self.analysis, key, value)

            # Update transcription configuration section
            if "transcription" in config_data:
                for key, value in config_data["transcription"].items():
                    if hasattr(self.transcription, key):
                        setattr(self.transcription, key, value)
                # Back-compat: older configs may store null/"auto" for language.
                lang = getattr(self.transcription, "language", "en")
                lang_norm = str(lang).strip().lower() if lang is not None else ""
                if not lang_norm or lang_norm in ("auto", "none"):
                    self.transcription.language = "en"

            # Update input configuration section
            if "input" in config_data:
                for key, value in config_data["input"].items():
                    if hasattr(self.input, key):
                        setattr(self.input, key, value)

            # Update output configuration section
            if "output" in config_data:
                for key, value in config_data["output"].items():
                    if hasattr(self.output, key):
                        setattr(self.output, key, value)

            # Update dashboard configuration section
            if "dashboard" in config_data:
                from .workflow import migrate_dashboard_config

                dashboard_data, migrated = migrate_dashboard_config(
                    config_data["dashboard"]
                )
                for key, value in dashboard_data.items():
                    if hasattr(self.dashboard, key):
                        setattr(self.dashboard, key, value)
                if migrated:
                    config_data["dashboard"] = dashboard_data
                    dashboard_migrated = True

            # Update logging configuration section
            if "logging" in config_data:
                for key, value in config_data["logging"].items():
                    if hasattr(self.logging, key):
                        setattr(self.logging, key, value)

            # Update audio preprocessing configuration section
            if "audio_preprocessing" in config_data:
                for key, value in config_data["audio_preprocessing"].items():
                    # Handle backward compatibility: migrate old boolean fields to new mode fields
                    migration_map = {
                        "normalize_enabled": "normalize_mode",
                        "denoise_enabled": "denoise_mode",
                        "highpass_enabled": "highpass_mode",
                        "lowpass_enabled": "lowpass_mode",
                        "bandpass_enabled": "bandpass_mode",
                    }

                    # Check if this is an old boolean field that needs migration
                    if key in migration_map and isinstance(value, bool):
                        new_key = migration_map[key]
                        # Convert boolean to mode: True -> "auto", False -> "off"
                        mode_value = "auto" if value else "off"
                        if hasattr(self.audio_preprocessing, new_key):
                            setattr(self.audio_preprocessing, new_key, mode_value)
                    # Handle convert_to_mono and downsample migration
                    elif key in ("convert_to_mono", "downsample") and isinstance(
                        value, bool
                    ):
                        mode_value = "auto" if value else "off"
                        if hasattr(self.audio_preprocessing, key):
                            setattr(self.audio_preprocessing, key, mode_value)
                    # Normal field assignment
                    elif hasattr(self.audio_preprocessing, key):
                        setattr(self.audio_preprocessing, key, value)

            # Update workflow configuration section
            if "workflow" in config_data:
                for key, value in config_data["workflow"].items():
                    if key == "speaker_gate" and isinstance(value, dict):
                        if hasattr(self.workflow, "speaker_gate"):
                            self._apply_profile_to_config(self.workflow.speaker_gate, value)
                    elif hasattr(self.workflow, key):
                        self._apply_profile_to_config(self.workflow, {key: value})

            # Update group analysis configuration section
            if "group_analysis" in config_data:
                for key, value in config_data["group_analysis"].items():
                    if hasattr(self.group_analysis, key):
                        setattr(self.group_analysis, key, value)

            # Update active workflow profile
            if "active_workflow_profile" in config_data:
                self.active_workflow_profile = config_data["active_workflow_profile"]

            # Update global emoji configuration
            if "use_emojis" in config_data:
                self.use_emojis = bool(config_data["use_emojis"])

            if dashboard_migrated:
                try:
                    with open(config_file, "w") as f:
                        json.dump(config_data, f, indent=2)
                except Exception:
                    pass

        except Exception as e:
            raise ValueError(f"Failed to load configuration from {config_file}: {e}")

    def _load_module_profiles(self):
        """
        Load active profiles for each module.

        Profile settings override defaults and file settings but not environment variables.
        If a profile doesn't exist, the default values from the dataclass are used.
        """
        from transcriptx.core.utils.profile_manager import get_profile_manager

        profile_manager = get_profile_manager()

        # Load topic modeling profile
        topic_profile = profile_manager.load_profile(
            "topic_modeling", self.analysis.active_topic_modeling_profile
        )
        if topic_profile and "config" in topic_profile:
            self._apply_profile_to_config(
                self.analysis.topic_modeling, topic_profile["config"]
            )

        # Load acts profile
        acts_profile = profile_manager.load_profile(
            "acts", self.analysis.active_acts_profile
        )
        if acts_profile and "config" in acts_profile:
            self._apply_profile_to_config(self.analysis.acts, acts_profile["config"])
        env_acts_model = os.getenv("TRANSCRIPTX_ACTS_MODEL")
        if env_acts_model:
            self.analysis.acts.ml_model_name = env_acts_model

        # Load tag extraction profile
        tag_profile = profile_manager.load_profile(
            "tag_extraction", self.analysis.active_tag_extraction_profile
        )
        if tag_profile and "config" in tag_profile:
            self._apply_profile_to_config(
                self.analysis.tag_extraction, tag_profile["config"]
            )

        # Load QA analysis profile
        qa_profile = profile_manager.load_profile(
            "qa_analysis", self.analysis.active_qa_analysis_profile
        )
        if qa_profile and "config" in qa_profile:
            self._apply_profile_to_config(
                self.analysis.qa_analysis, qa_profile["config"]
            )

        # Load temporal dynamics profile
        temporal_profile = profile_manager.load_profile(
            "temporal_dynamics", self.analysis.active_temporal_dynamics_profile
        )
        if temporal_profile and "config" in temporal_profile:
            self._apply_profile_to_config(
                self.analysis.temporal_dynamics, temporal_profile["config"]
            )

        # Load vectorization profile
        vector_profile = profile_manager.load_profile(
            "vectorization", self.analysis.active_vectorization_profile
        )
        if vector_profile and "config" in vector_profile:
            self._apply_profile_to_config(
                self.analysis.vectorization, vector_profile["config"]
            )

        # Load workflow profile
        workflow_profile = profile_manager.load_profile(
            "workflow", self.active_workflow_profile
        )
        if workflow_profile and "config" in workflow_profile:
            self._apply_profile_to_config(self.workflow, workflow_profile["config"])

    def _apply_profile_to_config(self, config_obj: Any, profile_data: dict[str, Any]):
        """
        Apply profile data to a config object.

        Args:
            config_obj: The config dataclass instance to update
            profile_data: Dictionary with profile settings
        """
        for key, value in profile_data.items():
            if hasattr(config_obj, key):
                # Handle tuple values (like ngram_range, k_range)
                if isinstance(value, list) and len(value) == 2:
                    # Try to convert to tuple if it looks like a tuple
                    try:
                        if all(isinstance(x, (int, float)) for x in value):
                            value = tuple(value)
                    except (ValueError, TypeError):
                        pass
                setattr(config_obj, key, value)
        if hasattr(config_obj, "validate"):
            config_obj.validate()

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
            "transcription": {
                "model_name": self.transcription.model_name,
                "compute_type": self.transcription.compute_type,
                "language": self.transcription.language,
                "batch_size": self.transcription.batch_size,
                "diarize": self.transcription.diarize,
                "min_speakers": self.transcription.min_speakers,
                "max_speakers": self.transcription.max_speakers,
            },
            "input": {
                "wav_folders": self.input.wav_folders,
                "recordings_folders": self.input.recordings_folders,
                "file_selection_mode": getattr(
                    self.input, "file_selection_mode", "prompt"
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
            "use_emojis": self.use_emojis,  # New: save emoji config
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
            json.dump(config_data, f, indent=2)

    def get_quality_filtering_config(self) -> dict[str, Any]:
        """
        Get the active quality filtering configuration, applying profile and overrides.

        Returns:
            Dictionary with weights, thresholds, and indicators from active profile + overrides
        """
        profile_name = getattr(self.analysis, "quality_filtering_profile", "balanced")
        profiles = getattr(self.analysis, "quality_filtering_profiles", {})

        if profile_name not in profiles:
            from .logger import log_warning

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
_env_loaded = False


def _load_repo_dotenv() -> None:
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    if load_dotenv is None:
        return
    repo_root = Path(__file__).resolve().parents[5]
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


def get_config() -> TranscriptXConfig:
    """
    Get the global configuration instance.

    Note: For thread-local configuration support, use config_provider.get_config()
    instead. This function maintains backward compatibility.
    """
    global _config
    if _config is None:
        _load_repo_dotenv()
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
