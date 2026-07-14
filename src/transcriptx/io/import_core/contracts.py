"""Core import contracts: kinds, outcomes, and adapter capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence, runtime_checkable

from transcriptx.io.intermediate_transcript import (
    IntermediateTranscript,
    TranscriptSegment,
)


class AdapterKind(str, Enum):
    VENDOR = "vendor"
    FAMILY = "family"
    GENERIC = "generic"


class DetectionClass(str, Enum):
    REJECT = "reject"
    POSSIBLE = "possible"
    LIKELY = "likely"
    DEFINITIVE = "definitive"


class ImportOutcome(str, Enum):
    UNKNOWN_INPUT = "unknown_input"
    RECOGNIZED_FAMILY_UNSUPPORTED = "recognized_family_unsupported"
    KNOWN_FAMILY_MALFORMED = "known_family_malformed"
    RECOGNIZED_TRANSCRIPTX_CANONICAL = "recognized_transcriptx_canonical"
    SUPPORTED_IMPORTABLE = "supported_importable"


@dataclass(frozen=True)
class DetectionInput:
    path: Path
    extension: str
    content_type_hint: Optional[str]
    snippet: bytes
    json_skeleton: Optional[Mapping[str, Any]] = None


@dataclass(frozen=True)
class ParseInput:
    path: Path
    content: bytes
    content_type_hint: Optional[str] = None


@dataclass(frozen=True)
class AdapterCapabilities:
    supports_word_timestamps: bool = False
    supports_confidence_scores: bool = False
    supports_speaker_labels: bool = True
    supports_multichannel: bool = False
    supports_source_metadata: bool = True
    produces_html_markup: bool = False


@dataclass(frozen=True)
class DetectionOutcome:
    detection_class: DetectionClass
    score: float
    signals: Sequence[str] = field(default_factory=tuple)
    hard_rejects: Sequence[str] = field(default_factory=tuple)
    recognized_family: bool = False
    recognized_canonical: bool = False


@dataclass(frozen=True)
class RankedCandidate:
    adapter_id: str
    adapter_kind: AdapterKind
    detection_class: DetectionClass
    score: float
    signals: Sequence[str] = field(default_factory=tuple)
    hard_rejects: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class NormalizationSummary:
    input_turn_count: int
    output_segment_count: int
    warning_count: int
    actions: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportResult:
    selected_adapter_id: str
    selected_adapter_kind: AdapterKind
    detection_outcome: DetectionOutcome
    ranked_candidates: Sequence[RankedCandidate]
    parsed_import: IntermediateTranscript
    normalized_segments: Sequence[TranscriptSegment]
    canonical_document: Dict[str, Any]
    diagnostics: Sequence["ImportDiagnostic"]
    outcome: ImportOutcome
    normalization_summary: NormalizationSummary


@runtime_checkable
class ImportAdapter(Protocol):
    adapter_id: str
    display_name: str
    adapter_kind: AdapterKind
    supported_extensions: frozenset[str]
    format_family: str
    detection_priority: int
    capabilities: AdapterCapabilities

    def probe(self, input_data: DetectionInput) -> DetectionOutcome: ...

    def parse(self, input_data: ParseInput) -> IntermediateTranscript: ...


# Deferred import for typing only
from transcriptx.io.import_core.diagnostics import ImportDiagnostic  # noqa: E402
