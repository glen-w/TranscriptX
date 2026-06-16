"""System configuration classes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from transcriptx.core.utils.config.analysis import AnalysisConfig
from transcriptx.core.utils.config.workflow import (
    DashboardConfig,
    GroupAnalysisConfig,
    InputConfig,
    OutputConfig,
    WorkflowConfig,
)
from transcriptx.core.utils.config.system_env import apply_env_overrides


def _read_install_profile() -> str | None:
    """Return install profile from marker file: 'core', 'full', or None."""
    from transcriptx.core.utils.paths import CONFIG_DIR

    path = CONFIG_DIR / "install_profile"
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip() or None
        except Exception:
            return None
    return None


@dataclass
class LLMConfig:
    """
    LLM provider configuration.

    This configuration is infrastructure-only. No UI integration yet.
    Future modules (summarization, action items, speaker briefs) will use
    this interface with strict provenance and caching.
    """

    enabled: bool = False
    provider: str = "null"  # null, ollama, openai
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None


@dataclass
class LoggingConfig:
    """
    Configuration for logging system.

    This class defines all logging-related settings including log levels,
    output formats, file handling, and rotation policies.

    Attributes:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Format string for log messages
        file_logging: Whether to log to files in addition to console
        log_file: Name of the log file
        max_log_size: Maximum size of log file before rotation (in bytes)
        backup_count: Number of backup log files to keep
    """

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_logging: bool = True
    log_file: str = "transcriptx.log"
    max_log_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


# Preprocessing mode types (config layer: defaults for per-step and global behavior)
PreprocessingMode = Literal["auto", "suggest", "off"]
GlobalPreprocessingMode = Literal["selected", "auto", "suggest", "off"]


@dataclass
class AudioPreprocessingConfig:
    """
    Configuration for audio preprocessing settings (config layer).

    This dataclass defines **config-time defaults**: per-step and global modes
    that influence how apply_preprocessing() behaves when no run-time override
    is given. It is a different layer from the **request-time** contract used by
    PreprocessRequest.preprocessing_mode ("off" | "selected" | "auto"), which
    controls a single run. The workflow bridges the two: it uses
    preprocessing_mode to derive a per-step decisions dict, then passes that into
    apply_preprocessing() along with this config for numeric parameters (LUFS,
    cutoffs, etc.). See PreprocessRequest and _derive_decisions() in the
    preprocess workflow for the request → config bridge.

    Per-step modes (convert_to_mono, downsample, normalize_mode, denoise_mode, …):
    - "auto": Always apply if needed (no user interaction)
    - "suggest": Assess files and suggest to user, apply if confirmed
    - "off": Never apply this preprocessing step

    Global preprocessing_mode overrides all per-step settings when not "selected":
    - "selected": Use per-step mode settings (fine-grained control)
    - "auto": Override all steps to "auto"
    - "suggest": Override all steps to "suggest"
    - "off": Override all steps to "off"

    Attributes:
        preprocessing_mode: Global preprocessing control mode (default: "selected")
        convert_to_mono: Convert stereo to mono mode (default: "auto")
        downsample: Downsample to target sample rate mode (default: "auto")
        target_sample_rate: Target sample rate in Hz (default: 16000)
        skip_if_already_compliant: Skip processing if file already meets requirements (default: True)
        normalize_mode: Loudness normalization mode (default: "auto")
        target_lufs: Target loudness in LUFS (range: -20 to -16, default: -18.0)
        limiter_enabled: Enable peak limiter (default: True)
        limiter_peak_db: Peak limiter threshold in dB (default: -1.0)
        denoise_mode: Denoising mode (default: "suggest")
        denoise_strength: Denoising strength: "low", "medium", or "high" (default: "medium")
        highpass_mode: High-pass filter mode (default: "suggest")
        highpass_cutoff: High-pass filter cutoff in Hz (range: 70-100, default: 80)
        lowpass_mode: Low-pass filter mode (default: "off")
        lowpass_cutoff: Low-pass filter cutoff in Hz (default: 8000)
        bandpass_mode: Band-pass filter mode (default: "off")
        bandpass_low: Band-pass low cutoff in Hz (default: 300)
        bandpass_high: Band-pass high cutoff in Hz (default: 3400)
    """

    # Global preprocessing control
    preprocessing_mode: GlobalPreprocessingMode = (
        "selected"  # Override all per-step modes
    )

    # Core settings
    convert_to_mono: PreprocessingMode = "auto"
    downsample: PreprocessingMode = "auto"
    target_sample_rate: int = 16000
    skip_if_already_compliant: bool = True

    # Loudness normalization
    normalize_mode: PreprocessingMode = "auto"  # Renamed from normalize_enabled
    target_lufs: float = -18.0  # Range: -20 to -16
    limiter_enabled: bool = True
    limiter_peak_db: float = -1.0

    # Noise reduction
    denoise_mode: PreprocessingMode = "suggest"  # Renamed from denoise_enabled
    denoise_strength: Literal["low", "medium", "high"] = "medium"

    # Filtering (ASR-safe)
    highpass_mode: PreprocessingMode = "suggest"  # Renamed from highpass_enabled
    highpass_cutoff: int = 80  # Range: 70-100 Hz
    lowpass_mode: PreprocessingMode = "off"  # Renamed from lowpass_enabled
    lowpass_cutoff: int = 8000
    bandpass_mode: PreprocessingMode = "off"  # Renamed from bandpass_enabled
    bandpass_low: int = 300
    bandpass_high: int = 3400


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
        self.core_mode: bool = True
        profile = _read_install_profile()
        if profile == "full":
            self.core_mode = False

        # Active workflow profile
        self.active_workflow_profile: str = "default"

        # Load configuration from environment variables first
        # Environment variables take highest priority
        self._load_from_env()

        # Load from config file if provided
        # File settings override defaults but not environment variables
        if config_file:
            self._load_from_file(config_file)

        # Load active profiles for each module
        # Profile settings override defaults and file settings but not environment variables
        self._load_module_profiles()

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
        - TRANSCRIPTX_OUTPUT_DIR: Base output directory
        - TRANSCRIPTX_LOG_LEVEL: Logging level
        - TRANSCRIPTX_USE_EMOJIS: Enable/disable emojis (1/true/yes/on or 0/false/no/off)
        """

        apply_env_overrides(self)

    def _load_from_file(self, config_file: str):
        """
        Load configuration from JSON file.

        Raises:
            ConfigLoadError: If the file violates the supported config contract
            ValueError: If the file cannot be read or parsed
        """
        from transcriptx.core.utils.config.file_overrides import load_config_file_into

        load_config_file_into(self, config_file)

    def _load_module_profiles(self):
        """Load active profiles via canonical adapter-driven loader."""
        from transcriptx.core.utils.config.profile_loading import load_module_profiles

        load_module_profiles(self)

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
        # Keep this class as a compatibility shim; canonical serialization lives in
        # transcriptx.core.utils.config.main.TranscriptXConfig.to_dict.
        from transcriptx.core.utils.config.main import TranscriptXConfig as MainConfig

        return MainConfig.to_dict(self)

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
