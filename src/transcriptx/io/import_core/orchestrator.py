from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from transcriptx.io.import_canonical.builder import (
    CanonicalBuildInput,
    build_canonical_document,
)
from transcriptx.io.import_core.contracts import (
    DetectionClass,
    ImportOutcome,
    ImportResult,
    NormalizationSummary,
    ParseInput,
)
from transcriptx.io.import_core.diagnostics import (
    DiagnosticSeverity,
    DiagnosticStage,
    ImportDiagnostic,
)
from transcriptx.io.import_core.errors import UnsupportedImportError
from transcriptx.io.import_core.normalization_policy import NormalizationPolicy
from transcriptx.io.import_core.pipeline import run_normalization_pipeline
from transcriptx.io.import_core.registry import ImportAdapterRegistry


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_import_orchestration(
    *,
    source_path: str | Path,
    registry: ImportAdapterRegistry,
    force_adapter: Optional[str] = None,
    imported_at: Optional[str] = None,
    source_original_path: Optional[str] = None,
    normalization_policy: Optional[NormalizationPolicy] = None,
    content_type_hint: Optional[str] = None,
) -> ImportResult:
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    content = path.read_bytes()
    imported_at_value = imported_at or utc_now_iso()
    policy = normalization_policy or NormalizationPolicy()

    # canonical artifact recognition
    if path.suffix.lower() == ".json":
        artifact_outcome = _recognize_transcriptx_artifact(content)
        if artifact_outcome is not None:
            canonical_doc = json.loads(content.decode("utf-8", errors="replace"))
            return ImportResult(
                selected_adapter_id="transcriptx",
                selected_adapter_kind=artifact_outcome["kind"],
                detection_outcome=artifact_outcome["detection"],
                ranked_candidates=[],
                parsed_import=artifact_outcome["parsed"],
                normalized_segments=canonical_doc.get("segments", []),
                canonical_document=canonical_doc,
                diagnostics=artifact_outcome["diagnostics"],
                outcome=ImportOutcome.RECOGNIZED_TRANSCRIPTX_CANONICAL,
                normalization_summary=NormalizationSummary(
                    input_turn_count=0,
                    output_segment_count=len(canonical_doc.get("segments", [])),
                    warning_count=0,
                    actions={"canonical_passthrough": 1},
                ),
            )

    selected = registry.detect(
        path=path,
        content=content,
        force_adapter=force_adapter,
        content_type_hint=content_type_hint,
    )
    # Compatibility: allow legacy monkeypatched detect() returning adapter-like object.
    adapter_obj = getattr(selected, "adapter", selected)
    selected_outcome = getattr(selected, "outcome", None)
    ranked_candidates = getattr(selected, "ranked_candidates", ())
    if selected_outcome is None:
        from transcriptx.io.import_core.contracts import AdapterKind, DetectionOutcome

        selected_outcome = DetectionOutcome(
            detection_class=DetectionClass.LIKELY,
            score=1.0,
            signals=("legacy_detect_adapter",),
        )
        ranked_candidates = ()
        if not hasattr(adapter_obj, "adapter_id"):
            setattr(
                adapter_obj, "adapter_id", getattr(adapter_obj, "source_id", "unknown")
            )
        if not hasattr(adapter_obj, "adapter_kind"):
            setattr(adapter_obj, "adapter_kind", AdapterKind.FAMILY)

    try:
        parsed = adapter_obj.parse(
            ParseInput(path=path, content=content, content_type_hint=content_type_hint)
        )
    except TypeError:
        # Compatibility for legacy parse(path, content) adapter signatures.
        parsed = adapter_obj.parse(path, content)
    segments, actions = run_normalization_pipeline(parsed, policy)
    if not segments:
        missing_bs4 = any(
            "beautifulsoup4 is required" in w.lower() for w in parsed.warnings
        )
        if missing_bs4:
            raise ValueError(
                "Sembly HTML import requires 'beautifulsoup4'. Install dependencies and retry."
            )
        raise UnsupportedImportError(
            path=str(path),
            outcome=ImportOutcome.KNOWN_FAMILY_MALFORMED,
            candidates=ranked_candidates,
        )

    canonical_doc = build_canonical_document(
        CanonicalBuildInput(
            source_type=adapter_obj.adapter_id,
            source_path=path,
            imported_at=imported_at_value,
            segments=segments,
            content=content,
            source_original_path=source_original_path,
        )
    )
    diagnostics = list(_warnings_to_diagnostics(parsed.warnings))
    diagnostics.append(
        ImportDiagnostic(
            code="detection.selected_adapter",
            severity=DiagnosticSeverity.INFO,
            stage=DiagnosticStage.PROBE,
            message=f"Selected adapter {adapter_obj.adapter_id}",
            recoverable=True,
            context={
                "signals": list(selected_outcome.signals),
                "score": selected_outcome.score,
            },
        )
    )
    outcome = ImportOutcome.SUPPORTED_IMPORTABLE
    if selected_outcome.detection_class == DetectionClass.POSSIBLE:
        outcome = ImportOutcome.RECOGNIZED_FAMILY_UNSUPPORTED

    return ImportResult(
        selected_adapter_id=adapter_obj.adapter_id,
        selected_adapter_kind=adapter_obj.adapter_kind,
        detection_outcome=selected_outcome,
        ranked_candidates=ranked_candidates,
        parsed_import=parsed,
        normalized_segments=segments,
        canonical_document=canonical_doc,
        diagnostics=diagnostics,
        outcome=outcome,
        normalization_summary=NormalizationSummary(
            input_turn_count=len(parsed.turns),
            output_segment_count=len(segments),
            warning_count=len(parsed.warnings),
            actions=actions,
        ),
    )


def _warnings_to_diagnostics(warnings: list[str]) -> list[ImportDiagnostic]:
    return [
        ImportDiagnostic(
            code="parse.warning",
            severity=DiagnosticSeverity.WARNING,
            stage=DiagnosticStage.PARSE,
            message=warning,
            recoverable=True,
        )
        for warning in warnings
    ]


def _recognize_transcriptx_artifact(content: bytes):
    try:
        data = json.loads(content.decode("utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if {"schema_version", "source", "segments"}.issubset(data.keys()):
        from transcriptx.io.intermediate_transcript import IntermediateTranscript
        from transcriptx.io.import_core.contracts import AdapterKind, DetectionOutcome

        return {
            "kind": AdapterKind.FAMILY,
            "detection": DetectionOutcome(
                detection_class=DetectionClass.DEFINITIVE,
                score=1.0,
                signals=("transcriptx_canonical_shape",),
                recognized_canonical=True,
            ),
            "parsed": IntermediateTranscript(
                source_tool="transcriptx",
                source_format="json",
                turns=[],
                source_metadata={"source": "canonical"},
                warnings=[],
            ),
            "diagnostics": [
                ImportDiagnostic(
                    code="canonical.recognized",
                    severity=DiagnosticSeverity.INFO,
                    stage=DiagnosticStage.CANONICALIZE,
                    message="TranscriptX canonical artifact recognized",
                )
            ],
        }
    return None
