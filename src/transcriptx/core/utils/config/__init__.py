from .analysis import (
    AnalysisConfig,
    SpeakerExemplarsConfig,
    HighlightsConfig,
    SummaryConfig,
    TopicModelingConfig,
    BERTopicConfig,
    ActsConfig,
    TagExtractionConfig,
    QAAnalysisConfig,
    TemporalDynamicsConfig,
    ConvokitConfig,
    VectorizationConfig,
    VoiceConfig,
)
from .workflow import (
    WorkflowConfig,
    TranscriptionConfig,
    InputConfig,
    OutputConfig,
    GroupAnalysisConfig,
    DashboardConfig,
    SpeakerGateConfig,
)
from .system import DatabaseConfig, LLMConfig, LoggingConfig, AudioPreprocessingConfig
from .main import (
    TranscriptXConfig,
    initialize_default_profiles,
)
from . import main as _main

# Backward-compatibility alias for tests and callers that expect Config
Config = TranscriptXConfig
from .base import (
    EMOTION_CATEGORIES,
    ACT_TYPES,
    DEFAULT_NER_LABELS,
    DEFAULT_STOPWORDS,
    STOPWORDS_FILE,
    TICS_FILE,
)

_global_config = None


def get_config() -> TranscriptXConfig:
    """Get the global configuration instance."""
    global _global_config
    if _global_config is None:
        if getattr(_main, "_config", None) is not None:
            _global_config = _main._config
        else:
            _global_config = TranscriptXConfig()
            initialize_default_profiles()
    _main.set_config(_global_config)
    return _global_config


def set_config(config: TranscriptXConfig) -> None:
    """Set the global configuration instance."""
    global _global_config
    _global_config = config
    _main.set_config(config)


def load_config(config_file: str) -> TranscriptXConfig:
    """Load configuration from file and set as global config."""
    config = TranscriptXConfig(config_file)
    set_config(config)
    return config


__all__ = [
    "Config",
    "AnalysisConfig",
    "SpeakerExemplarsConfig",
    "HighlightsConfig",
    "SummaryConfig",
    "TopicModelingConfig",
    "BERTopicConfig",
    "ActsConfig",
    "TagExtractionConfig",
    "QAAnalysisConfig",
    "TemporalDynamicsConfig",
    "ConvokitConfig",
    "VectorizationConfig",
    "VoiceConfig",
    "WorkflowConfig",
    "TranscriptionConfig",
    "InputConfig",
    "OutputConfig",
    "GroupAnalysisConfig",
    "DashboardConfig",
    "SpeakerGateConfig",
    "DatabaseConfig",
    "LLMConfig",
    "LoggingConfig",
    "AudioPreprocessingConfig",
    "TranscriptXConfig",
    "get_config",
    "set_config",
    "load_config",
    "initialize_default_profiles",
    "EMOTION_CATEGORIES",
    "ACT_TYPES",
    "DEFAULT_NER_LABELS",
    "DEFAULT_STOPWORDS",
    "STOPWORDS_FILE",
    "TICS_FILE",
]
