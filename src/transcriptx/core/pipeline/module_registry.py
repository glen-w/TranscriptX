"""
Unified module registry for TranscriptX analysis pipeline.

This module provides a single source of truth for all analysis modules,
centralizing module metadata, dependencies, and lazy import functions.
"""

from typing import Dict, List, Optional, Callable, Iterable
from dataclasses import dataclass

from transcriptx.core.domain.module_requirements import Requirement, Enhancement
from transcriptx.core.utils.audio_availability import has_resolvable_audio


def analyze_sentiment_from_file(transcript_path: str):
    from transcriptx.core.analysis.sentiment import SentimentAnalysis

    return SentimentAnalysis().run_from_file(transcript_path)


@dataclass
class ModuleInfo:
    """Information about an analysis module."""

    name: str
    description: str
    category: str  # light, medium, heavy
    dependencies: List[str]
    determinism_tier: str  # T0, T1, T2
    requirements: List[Requirement]
    enhancements: List[Enhancement]
    function: Optional[Callable] = None
    timeout_seconds: int = 600
    exclude_from_default: bool = False
    requires_audio: bool = False
    supports_audio: bool = False
    output_namespace: Optional[str] = None
    output_version: Optional[str] = None
    cost_tier: str = "normal"


class ModuleRegistry:
    """
    Central registry for all analysis modules.

    This class provides a single source of truth for module metadata
    and handles lazy loading of module functions.
    """

    def __init__(self) -> None:
        """Initialize the module registry."""
        self._modules: Dict[str, ModuleInfo] = {}
        self._setup_modules()

    def _setup_modules(self) -> None:
        """Set up all available analysis modules."""
        # Define module metadata
        default_requirements = [Requirement.SEGMENTS]
        module_definitions = {
            "corrections": {
                "description": "Semi-automatic transcription accuracy tuning",
                "dependencies": [],
                "category": "light",
                "determinism_tier": "T0",
                "requirements": [Requirement.SEGMENTS],
                "enhancements": [],
                "exclude_from_default": True,
            },
            "acts": {
                "description": "Dialogue Act Classification",
                "dependencies": [],
                "category": "medium",
                "determinism_tier": "T0",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "conversation_loops": {
                "description": "Conversation Loop Detection",
                "dependencies": [],
                "category": "light",
                "determinism_tier": "T0",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "contagion": {
                "description": "Emotional Contagion Detection",
                "dependencies": ["emotion"],
                "category": "heavy",
                "determinism_tier": "T1",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "convokit": {
                "description": "ConvoKit Coordination and Accommodation Analysis",
                "dependencies": [],
                "category": "medium",
                "determinism_tier": "T1",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "emotion": {
                "description": "Emotion Analysis",
                "dependencies": [],
                "category": "medium",
                "determinism_tier": "T1",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "entity_sentiment": {
                "description": "Entity-based Sentiment Analysis",
                "dependencies": ["ner", "sentiment"],
                "category": "heavy",
                "determinism_tier": "T1",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "affect_tension": {
                "description": "Emotion + Sentiment mismatch and tension indices",
                "dependencies": ["emotion", "sentiment"],
                "category": "medium",
                "determinism_tier": "T1",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "interactions": {
                "description": "Speaker Interaction Analysis",
                "dependencies": [],
                "category": "medium",
                "determinism_tier": "T0",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "ner": {
                "description": "Named Entity Recognition",
                "dependencies": [],
                "category": "medium",
                "determinism_tier": "T1",
                "requirements": default_requirements,
                "enhancements": [],
            },
            "semantic_similarity": {
                "description": "Semantic Similarity Analysis",
                "dependencies": [],
                "category": "heavy",
                "determinism_tier": "T1",
                "requirements": default_requirements,
                "enhancements": [],
            },
            "semantic_similarity_advanced": {
                "description": "Advanced Semantic Similarity with Analysis Integration",
                "dependencies": [],
                "category": "heavy",
                "determinism_tier": "T1",
                "requirements": default_requirements,
                "enhancements": [],
            },
            "sentiment": {
                "description": "Sentiment Analysis",
                "dependencies": [],
                "category": "medium",
                "determinism_tier": "T1",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "stats": {
                "description": "Statistical Analysis",
                "dependencies": [],
                "category": "light",
                "determinism_tier": "T0",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "topic_modeling": {
                "description": "Topic Modeling",
                "dependencies": [],
                "category": "heavy",
                "determinism_tier": "T2",
                "requirements": default_requirements,
                "enhancements": [],
            },
            "transcript_output": {
                "description": "Generate human readable transcripts",
                "dependencies": [],
                "category": "light",
                "determinism_tier": "T0",
                "requirements": default_requirements,
                "enhancements": [Enhancement.SPEAKER_DISPLAY_NAMES],
            },
            "simplified_transcript": {
                "description": "Simplified transcript (tics, agreements, repetitions removed)",
                "dependencies": [],
                "category": "light",
                "determinism_tier": "T0",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "understandability": {
                "description": "Understandability Analysis",
                "dependencies": [],
                "category": "medium",
                "determinism_tier": "T0",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "wordclouds": {
                "description": "Word Cloud Generation",
                "dependencies": [],
                "category": "light",
                "determinism_tier": "T1",
                "requirements": default_requirements,
                "enhancements": [],
            },
            "tics": {
                "description": "Verbal Tics Analysis",
                "dependencies": [],
                "category": "light",
                "determinism_tier": "T0",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "temporal_dynamics": {
                "description": "Temporal Dynamics Analysis",
                "dependencies": [],
                "category": "medium",
                "determinism_tier": "T1",
                "requirements": [
                    Requirement.SEGMENTS,
                    Requirement.SEGMENT_TIMESTAMPS,
                    Requirement.SPEAKER_LABELS,
                ],
                "enhancements": [],
            },
            "qa_analysis": {
                "description": "Question-Answer Pairing and Response Quality",
                "dependencies": ["acts"],
                "category": "medium",
                "determinism_tier": "T1",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "pauses": {
                "description": "Silence and Timing Analysis",
                "dependencies": [],
                "category": "light",
                "determinism_tier": "T0",
                "requirements": [
                    Requirement.SEGMENTS,
                    Requirement.SEGMENT_TIMESTAMPS,
                    Requirement.SPEAKER_LABELS,
                ],
                "enhancements": [],
            },
            "echoes": {
                "description": "Quote/Echo/Paraphrase Detection",
                "dependencies": [],
                "category": "medium",
                "determinism_tier": "T1",
                "requirements": [Requirement.SEGMENTS, Requirement.SPEAKER_LABELS],
                "enhancements": [],
            },
            "momentum": {
                "description": "Stall/Flow Index Analysis",
                "dependencies": ["pauses"],
                "category": "medium",
                "determinism_tier": "T0",
                "requirements": [
                    Requirement.SEGMENTS,
                    Requirement.SEGMENT_TIMESTAMPS,
                    Requirement.SPEAKER_LABELS,
                ],
                "enhancements": [],
            },
            "moments": {
                "description": "Ranked Moments Worth Revisiting",
                "dependencies": ["momentum"],
                "category": "light",
                "determinism_tier": "T0",
                "requirements": [
                    Requirement.SEGMENTS,
                    Requirement.SEGMENT_TIMESTAMPS,
                ],
                "enhancements": [],
            },
            "highlights": {
                "description": "Highlights and conflict moments (quote-forward)",
                "dependencies": [],
                "category": "light",
                "determinism_tier": "T0",
                "requirements": [
                    Requirement.SEGMENTS,
                    Requirement.SEGMENT_TIMESTAMPS,
                    Requirement.SPEAKER_LABELS,
                ],
                "enhancements": [],
            },
            "summary": {
                "description": "Executive brief summary derived from highlights",
                "dependencies": ["highlights"],
                "category": "light",
                "determinism_tier": "T0",
                "requirements": [
                    Requirement.SEGMENTS,
                    Requirement.SEGMENT_TIMESTAMPS,
                    Requirement.SPEAKER_LABELS,
                ],
                "enhancements": [],
            },
            "voice_features": {
                "description": "Voice feature extraction and caching",
                "dependencies": [],
                "category": "heavy",
                "determinism_tier": "T0",
                "requirements": [
                    Requirement.SEGMENTS,
                    Requirement.SEGMENT_TIMESTAMPS,
                    Requirement.SPEAKER_LABELS,
                ],
                "enhancements": [],
                "requires_audio": True,
                "supports_audio": True,
                "cost_tier": "heavy",
            },
            "voice_mismatch": {
                "description": "Tone–Text mismatch detection (sarcasm/discord moments)",
                "dependencies": ["voice_features"],
                "category": "medium",
                "determinism_tier": "T0",
                "requirements": [
                    Requirement.SEGMENTS,
                    Requirement.SEGMENT_TIMESTAMPS,
                    Requirement.SPEAKER_LABELS,
                ],
                "enhancements": [],
                "exclude_from_default": True,
                "requires_audio": True,
                "supports_audio": True,
                "cost_tier": "normal",
            },
            "voice_tension": {
                "description": "Conversation tension curve from voice",
                "dependencies": ["voice_features"],
                "category": "medium",
                "determinism_tier": "T0",
                "requirements": [
                    Requirement.SEGMENTS,
                    Requirement.SEGMENT_TIMESTAMPS,
                ],
                "enhancements": [],
                "exclude_from_default": True,
                "requires_audio": True,
                "supports_audio": True,
                "cost_tier": "normal",
            },
            "voice_fingerprint": {
                "description": "Per-speaker voice fingerprint baseline and drift",
                "dependencies": ["voice_features"],
                "category": "medium",
                "determinism_tier": "T0",
                "requirements": [
                    Requirement.SEGMENTS,
                    Requirement.SEGMENT_TIMESTAMPS,
                    Requirement.SPEAKER_LABELS,
                ],
                "enhancements": [],
                "exclude_from_default": True,
                "requires_audio": True,
                "supports_audio": True,
                "cost_tier": "normal",
            },
            "prosody_dashboard": {
                "description": "Prosody dashboard charts from voice features",
                "dependencies": ["voice_features"],
                "category": "medium",
                "determinism_tier": "T0",
                "requirements": [
                    Requirement.SEGMENTS,
                    Requirement.SEGMENT_TIMESTAMPS,
                    Requirement.SPEAKER_LABELS,
                ],
                "enhancements": [],
                "requires_audio": True,
                "supports_audio": True,
                "cost_tier": "cheap",
            },
            "voice_charts_core": {
                "description": "Voice charts core: pauses + rhythm indices",
                "dependencies": ["voice_features"],
                "category": "medium",
                "determinism_tier": "T0",
                "requirements": [
                    Requirement.SEGMENTS,
                    Requirement.SEGMENT_TIMESTAMPS,
                    Requirement.SPEAKER_LABELS,
                ],
                "enhancements": [],
                "requires_audio": True,
                "supports_audio": True,
                "output_namespace": "voice",
                "output_version": "v1",
                "cost_tier": "normal",
            },
            "voice_contours": {
                "description": "Voice contours (slow; needs audio decode + pitch tracking)",
                "dependencies": ["voice_features"],
                "category": "medium",
                "determinism_tier": "T0",
                "requirements": [
                    Requirement.SEGMENTS,
                    Requirement.SEGMENT_TIMESTAMPS,
                    Requirement.SPEAKER_LABELS,
                ],
                "enhancements": [],
                "requires_audio": True,
                "supports_audio": True,
                "exclude_from_default": True,
                "output_namespace": "voice",
                "output_version": "v1",
                "cost_tier": "heavy",
            },
        }

        # Create module info objects
        for name, info in module_definitions.items():
            self._modules[name] = ModuleInfo(
                name=name,
                description=info["description"],
                category=info["category"],
                dependencies=info["dependencies"],
                determinism_tier=info.get("determinism_tier", "T0"),
                requirements=info.get("requirements", default_requirements),
                enhancements=info.get("enhancements", []),
                exclude_from_default=info.get("exclude_from_default", False),
                requires_audio=info.get("requires_audio", False),
                supports_audio=info.get("supports_audio", False),
                output_namespace=info.get("output_namespace"),
                output_version=info.get("output_version"),
                cost_tier=info.get("cost_tier", "normal"),
                timeout_seconds=600,
            )

    def get_available_modules(self) -> List[str]:
        """Get list of available analysis modules."""
        return list(self._modules.keys())

    def get_default_modules(
        self,
        transcript_targets: Optional[Iterable[object]] = None,
        *,
        audio_resolver: Optional[Callable[[object], bool]] = None,
        dep_resolver: Optional[Callable[[ModuleInfo], bool]] = None,
        include_heavy: bool = True,
        include_excluded_from_default: bool = False,
    ) -> List[str]:
        """Get list of modules used for default analysis runs."""
        audio_available: Optional[bool] = None
        if transcript_targets is not None:
            resolver = audio_resolver or has_resolvable_audio
            try:
                audio_available = resolver(transcript_targets)
            except Exception:
                audio_available = None

        if dep_resolver is None:
            def dep_resolver(info: ModuleInfo) -> bool:
                if not info.requires_audio:
                    return True
                try:
                    from transcriptx.core.analysis.voice.deps import (
                        check_voice_optional_deps,
                    )
                    from transcriptx.core.utils.config import get_config

                    voice_cfg = getattr(getattr(get_config(), "analysis", None), "voice", None)
                    egemaps_enabled = bool(getattr(voice_cfg, "egemaps_enabled", True))
                    deps = check_voice_optional_deps(egemaps_enabled=egemaps_enabled)
                    return bool(deps.get("ok", True))
                except Exception:
                    return True

        selected: list[str] = []
        for name, info in self._modules.items():
            if not include_excluded_from_default and info.exclude_from_default:
                continue
            if not include_heavy and info.cost_tier == "heavy":
                continue
            if info.requires_audio and audio_available is False:
                continue
            if dep_resolver is not None and not dep_resolver(info):
                continue
            selected.append(name)
        return selected

    def get_module_info(self, module_name: str) -> Optional[ModuleInfo]:
        """Get information about a specific analysis module."""
        return self._modules.get(module_name)

    def get_module_function(self, module_name: str) -> Optional[Callable]:
        """Get the lazy import function for a module."""
        module_info = self._modules.get(module_name)
        if not module_info:
            return None

        # Return cached function if available
        if module_info.function:
            return module_info.function

        # Create lazy import function
        lazy_function = self._create_lazy_import_function(module_name)
        module_info.function = lazy_function
        return lazy_function

    def _create_lazy_import_function(self, module_name: str) -> Callable:
        """
        Create a lazy import function that returns AnalysisModule class for a module.

        All modules now use the AnalysisModule base class interface,
        allowing the DAG pipeline to use the shared PipelineContext.

        Raises:
            ImportError: If the AnalysisModule class cannot be imported
            ValueError: If the module name is unknown
        """
        # Module name to AnalysisModule class mapping
        module_class_map = {
            "corrections": (
                "transcriptx.core.analysis.corrections",
                "CorrectionsAnalysis",
            ),
            "emotion": ("transcriptx.core.analysis.emotion", "EmotionAnalysis"),
            "contagion": ("transcriptx.core.analysis.contagion", "ContagionAnalysis"),
            "sentiment": ("transcriptx.core.analysis.sentiment", "SentimentAnalysis"),
            "acts": ("transcriptx.core.analysis.acts.analysis", "ActsAnalysis"),
            "stats": ("transcriptx.core.analysis.stats", "StatsAnalysis"),
            "convokit": ("transcriptx.core.analysis.convokit", "ConvoKitAnalysis"),
            "interactions": (
                "transcriptx.core.analysis.interactions.analysis",
                "InteractionsAnalysis",
            ),
            "ner": ("transcriptx.core.analysis.ner", "NERAnalysis"),
            "entity_sentiment": (
                "transcriptx.core.analysis.entity_sentiment",
                "EntitySentimentAnalysis",
            ),
            "affect_tension": (
                "transcriptx.core.analysis.affect_tension",
                "AffectTensionAnalysis",
            ),
            "conversation_loops": (
                "transcriptx.core.analysis.conversation_loops.analysis",
                "ConversationLoopsAnalysis",
            ),
            "topic_modeling": (
                "transcriptx.core.analysis.topic_modeling",
                "TopicModelingAnalysis",
            ),
            "semantic_similarity": (
                "transcriptx.core.analysis.semantic_similarity",
                "SemanticSimilarityAnalysis",
            ),
            "semantic_similarity_advanced": (
                "transcriptx.core.analysis.semantic_similarity",
                "SemanticSimilarityAdvancedAnalysis",
            ),
            "transcript_output": (
                "transcriptx.core.analysis.transcript_output",
                "TranscriptOutputAnalysis",
            ),
            "simplified_transcript": (
                "transcriptx.core.analysis.simplified_transcript",
                "SimplifiedTranscriptAnalysis",
            ),
            "wordclouds": (
                "transcriptx.core.analysis.wordclouds.analysis",
                "WordcloudsAnalysis",
            ),
            "tics": ("transcriptx.core.analysis.tics", "TicsAnalysis"),
            "understandability": (
                "transcriptx.core.analysis.understandability",
                "UnderstandabilityAnalysis",
            ),
            "temporal_dynamics": (
                "transcriptx.core.analysis.temporal_dynamics.analysis",
                "TemporalDynamicsAnalysis",
            ),
            "qa_analysis": ("transcriptx.core.analysis.qa_analysis.analysis", "QAAnalysis"),
            "pauses": (
                "transcriptx.core.analysis.dynamics.pauses",
                "PausesAnalysis",
            ),
            "echoes": (
                "transcriptx.core.analysis.dynamics.echoes",
                "EchoesAnalysis",
            ),
            "momentum": (
                "transcriptx.core.analysis.dynamics.momentum",
                "MomentumAnalysis",
            ),
            "moments": (
                "transcriptx.core.analysis.dynamics.moments",
                "MomentsAnalysis",
            ),
            "highlights": (
                "transcriptx.core.analysis.highlights",
                "HighlightsAnalysis",
            ),
            "summary": (
                "transcriptx.core.analysis.summary",
                "SummaryAnalysis",
            ),
            "voice_features": (
                "transcriptx.core.analysis.voice_features",
                "VoiceFeaturesAnalysis",
            ),
            "voice_mismatch": (
                "transcriptx.core.analysis.voice_mismatch",
                "VoiceMismatchAnalysis",
            ),
            "voice_tension": (
                "transcriptx.core.analysis.voice_tension",
                "VoiceTensionAnalysis",
            ),
            "voice_fingerprint": (
                "transcriptx.core.analysis.voice_fingerprint",
                "VoiceFingerprintAnalysis",
            ),
            "prosody_dashboard": (
                "transcriptx.core.analysis.voice.dashboard",
                "ProsodyDashboardAnalysis",
            ),
            "voice_charts_core": (
                "transcriptx.core.analysis.voice.charts_core",
                "VoiceChartsCoreAnalysis",
            ),
            "voice_contours": (
                "transcriptx.core.analysis.voice.contours",
                "VoiceContoursAnalysis",
            ),
        }

        if module_name not in module_class_map:
            raise ValueError(f"Unknown module: {module_name}")

        module_path, class_name = module_class_map[module_name]

        # Dynamically import the AnalysisModule class
        try:
            module = __import__(module_path, fromlist=[class_name])
            analysis_class = getattr(module, class_name)

            # Verify it's actually an AnalysisModule class
            from transcriptx.core.analysis.base import AnalysisModule

            if not (
                isinstance(analysis_class, type)
                and issubclass(analysis_class, AnalysisModule)
            ):
                raise TypeError(f"{class_name} is not an AnalysisModule subclass")

            class ModuleCallable:
                def __init__(self, module_cls, module_name: str):
                    self._module_cls = module_cls
                    self._module_name = module_name

                def run_from_context(self, context):
                    return self._module_cls().run_from_context(context)

                def __call__(self, transcript_path: str):
                    if self._module_name == "sentiment":
                        return analyze_sentiment_from_file(transcript_path)
                    return self._module_cls().run_from_file(transcript_path)

            return ModuleCallable(analysis_class, module_name)
        except ImportError as e:
            raise ImportError(
                f"Failed to import {class_name} from {module_path} for module '{module_name}': {e}"
            ) from e
        except AttributeError as e:
            raise AttributeError(
                f"Module {module_path} does not have class {class_name}: {e}"
            ) from e

    def get_dependencies(self, module_name: str) -> List[str]:
        """Get dependencies for a module."""
        module_info = self._modules.get(module_name)
        return module_info.dependencies if module_info else []

    def get_category(self, module_name: str) -> Optional[str]:
        """Get category for a module."""
        module_info = self._modules.get(module_name)
        return module_info.category if module_info else None

    def get_description(self, module_name: str) -> Optional[str]:
        """Get description for a module."""
        module_info = self._modules.get(module_name)
        return module_info.description if module_info else None

    def get_determinism_tier(self, module_name: str) -> Optional[str]:
        """Get determinism tier for a module."""
        module_info = self._modules.get(module_name)
        return module_info.determinism_tier if module_info else None


# Global registry instance
_module_registry = ModuleRegistry()


def get_available_modules() -> List[str]:
    """Get list of available analysis modules."""
    return _module_registry.get_available_modules()


def get_default_modules(
    transcript_targets: Optional[Iterable[object]] = None,
    *,
    audio_resolver: Optional[Callable[[object], bool]] = None,
    dep_resolver: Optional[Callable[[ModuleInfo], bool]] = None,
    include_heavy: bool = True,
    include_excluded_from_default: bool = False,
) -> List[str]:
    """Get list of modules used for default analysis runs."""
    return _module_registry.get_default_modules(
        transcript_targets,
        audio_resolver=audio_resolver,
        dep_resolver=dep_resolver,
        include_heavy=include_heavy,
        include_excluded_from_default=include_excluded_from_default,
    )


def get_module_info(module_name: str) -> Optional[ModuleInfo]:
    """Get information about a specific analysis module."""
    return _module_registry.get_module_info(module_name)


def get_module_function(module_name: str) -> Optional[Callable]:
    """Get the lazy import function for a module."""
    return _module_registry.get_module_function(module_name)


def get_dependencies(module_name: str) -> List[str]:
    """Get dependencies for a module."""
    return _module_registry.get_dependencies(module_name)


def get_category(module_name: str) -> Optional[str]:
    """Get category for a module."""
    return _module_registry.get_category(module_name)


def get_description(module_name: str) -> Optional[str]:
    """Get description for a module."""
    return _module_registry.get_description(module_name)


def get_determinism_tier(module_name: str) -> Optional[str]:
    """Get determinism tier for a module."""
    return _module_registry.get_determinism_tier(module_name)
