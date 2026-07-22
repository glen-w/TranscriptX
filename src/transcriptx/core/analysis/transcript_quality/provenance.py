"""Score provenance for ASR confidence results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from transcriptx.core.analysis.transcript_quality.scores import (
    NORMALISATION_POLICY,
    SOURCE_SCORE_FIELD,
)


def _comparable_key(
    *,
    import_adapter: Optional[str],
    asr_engine: Optional[str],
    model_identifier: Optional[str],
    source_score_field: str,
    normalisation_policy: str,
) -> str:
    parts = [
        import_adapter or "",
        asr_engine or "",
        model_identifier or "",
        source_score_field,
        normalisation_policy,
    ]
    return "|".join(parts)


def build_provenance(
    *,
    import_adapter: Optional[str] = None,
    asr_engine: Optional[str] = None,
    model_identifier: Optional[str] = None,
    source_score_field: str = SOURCE_SCORE_FIELD,
    normalisation_policy: str = NORMALISATION_POLICY,
) -> Dict[str, Any]:
    """Privacy-safe provenance; nulls allowed when unknown."""
    return {
        "import_adapter": import_adapter,
        "asr_engine": asr_engine,
        "model_identifier": model_identifier,
        "source_score_field": source_score_field,
        "normalisation_policy": normalisation_policy,
        "comparable_key": _comparable_key(
            import_adapter=import_adapter,
            asr_engine=asr_engine,
            model_identifier=model_identifier,
            source_score_field=source_score_field,
            normalisation_policy=normalisation_policy,
        ),
    }


def resolve_provenance_from_transcript_path(
    transcript_path: Optional[str],
) -> Dict[str, Any]:
    """
    Best-effort provenance from managed transcript JSON + import sidecar.

    Missing fields stay null; never invent model identifiers.
    """
    import_adapter: Optional[str] = None
    asr_engine: Optional[str] = None
    model_identifier: Optional[str] = None

    if transcript_path:
        path = Path(transcript_path)
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                data = None
            if isinstance(data, dict):
                source = data.get("source")
                if isinstance(source, dict):
                    raw_type = source.get("type")
                    if isinstance(raw_type, str) and raw_type.strip():
                        import_adapter = raw_type.strip()
                    raw_model = source.get("model") or source.get("model_id")
                    if isinstance(raw_model, str) and raw_model.strip():
                        model_identifier = raw_model.strip()
                    raw_tool = source.get("tool") or source.get("source_tool")
                    if isinstance(raw_tool, str) and raw_tool.strip():
                        asr_engine = raw_tool.strip()
            # Sidecar adapter_source_id preferred when present
            try:
                from transcriptx.io.import_metadata_sidecar import (
                    sidecar_path_for_transcript,
                )

                side = sidecar_path_for_transcript(path)
                if side.is_file():
                    side_data = json.loads(side.read_text(encoding="utf-8"))
                    if isinstance(side_data, dict):
                        adapter = side_data.get("adapter_source_id")
                        if isinstance(adapter, str) and adapter.strip():
                            import_adapter = adapter.strip()
            except Exception:
                pass

    if asr_engine is None and import_adapter is not None:
        # Prefer adapter id as engine label when source tool is unknown.
        asr_engine = import_adapter

    return build_provenance(
        import_adapter=import_adapter,
        asr_engine=asr_engine,
        model_identifier=model_identifier,
    )
