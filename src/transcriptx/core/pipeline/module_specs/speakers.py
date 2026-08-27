"""Domain-specific module registry definition builders."""

from __future__ import annotations

from typing import Dict, List

from transcriptx.core.domain.module_requirements import Requirement


def build_speakers_module_definitions(
    default_requirements: List[Requirement],
) -> Dict[str, Dict]:
    return {
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
            "required_extras": ["voice"],
            # Long transcripts + deep_mode can exceed the default 600s budget.
            "timeout_seconds": 3600,
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
            "required_extras": ["voice"],
        },
        "voice_tension": {
            "description": "Conversation tension curve from voice",
            "dependencies": ["voice_features"],
            "category": "medium",
            "determinism_tier": "T0",
            "requirements": [Requirement.SEGMENTS, Requirement.SEGMENT_TIMESTAMPS],
            "enhancements": [],
            "exclude_from_default": True,
            "requires_audio": True,
            "supports_audio": True,
            "cost_tier": "normal",
            "required_extras": ["voice"],
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
            "required_extras": ["voice"],
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
            "required_extras": ["voice"],
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
            "required_extras": ["voice"],
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
            "required_extras": ["voice"],
        },
    }
