"""Public transcript import API built on import_core orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR
from transcriptx.io.import_adapters.registry_builtins import build_default_registry
from transcriptx.io.import_core.normalization_policy import NormalizationPolicy
from transcriptx.io.import_core.orchestrator import (
    run_import_orchestration,
    utc_now_iso,
)
from transcriptx.io.import_core.writer import AtomicTranscriptWriter
from transcriptx.io.transcript_schema import validate_transcript_document
import json

logger = get_logger()
registry = build_default_registry()


@dataclass(frozen=True)
class ImportResult:
    json_path: Path
    adapter_source_id: str
    imported_at: str

    def __fspath__(self) -> str:
        return str(self.json_path)

    def __str__(self) -> str:
        return str(self.json_path)

    def __getattr__(self, item):
        return getattr(self.json_path, item)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ImportResult):
            return (
                self.json_path == other.json_path
                and self.adapter_source_id == other.adapter_source_id
                and self.imported_at == other.imported_at
            )
        if isinstance(other, (str, Path)):
            return self.json_path == Path(other)
        return False


def detect_transcript_format(path: Path) -> str:
    """Return the selected adapter id for a transcript path."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")
    result = run_import_orchestration(source_path=path, registry=registry)
    return result.selected_adapter_id


def ensure_json_artifact(path: Path, force_adapter: Optional[str] = None) -> Path:
    """Ensure a canonical JSON artifact exists for a source path."""
    path = Path(path)
    if path.suffix.lower() == ".json" and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            validate_transcript_document(data)
            return path
        except Exception:
            pass
    return import_transcript(path, force_adapter=force_adapter).json_path


def import_transcript(
    source_path: str | Path,
    output_dir: Optional[str | Path] = None,
    coalesce_config: Optional[object] = None,
    overwrite: bool = False,
    force_adapter: Optional[str] = None,
    imported_at: Optional[str] = None,
    source_original_path: Optional[str] = None,
    canonical_json_stem: Optional[str] = None,
) -> ImportResult:
    """Import transcript source and persist canonical JSON artifact."""
    _ = coalesce_config  # coalescing policy now handled by normalization policy.
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    if output_dir is None:
        output_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = canonical_json_stem if canonical_json_stem is not None else source_path.stem
    if not stem:
        raise ValueError("canonical_json_stem must be non-empty when provided")
    if "/" in stem or "\\" in stem or stem in {".", ".."}:
        raise ValueError(f"Invalid canonical_json_stem: {stem!r}")
    json_filename = f"{stem}.json"
    json_path = output_dir / json_filename

    force_reimport = False
    if json_path.exists() and not overwrite:
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            validate_transcript_document(data)
            return ImportResult(
                json_path=json_path,
                adapter_source_id="existing",
                imported_at=imported_at or utc_now_iso(),
            )
        except Exception:
            logger.warning(
                "Existing JSON at %s is not a valid v1.0 transcript; re-importing",
                json_path,
            )
            force_reimport = True

    orchestration = run_import_orchestration(
        source_path=source_path,
        registry=registry,
        force_adapter=force_adapter,
        imported_at=imported_at,
        source_original_path=source_original_path,
        normalization_policy=NormalizationPolicy(),
    )
    writer = AtomicTranscriptWriter(reason="import")
    writer.write(
        json_path,
        orchestration.canonical_document,
        overwrite=overwrite or force_reimport,
    )

    return ImportResult(
        json_path=json_path,
        adapter_source_id=orchestration.selected_adapter_id,
        imported_at=imported_at or utc_now_iso(),
    )
