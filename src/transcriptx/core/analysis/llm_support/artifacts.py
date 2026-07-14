"""Artifact-pair writers for LLM analysis modules.

Contract: **atomic pair promotion with rollback, then registration.**

1. Both JSON and Markdown are fully staged before any promotion.
2. JSON is promoted first, then Markdown; if the Markdown promotion fails,
   the JSON promotion is undone exactly once (restored from backup, or
   unlinked when there was no prior file).
3. Prior canonical files are never deleted optimistically; backups live in
   the staging directory.
4. The staging directory is cleaned up in ``finally``.
5. ``record_file()`` runs only after both promotions succeed.
6. There is **no filesystem rollback after registration begins**: if the
   first ``record_file`` (JSON) fails, both files remain promoted and nothing
   is registered; if the second (Markdown) fails, both files remain promoted
   and only the JSON registration exists. Registration rollback would require
   an OutputService unregister API, which does not exist.
7. If rollback itself fails while handling a promotion failure, the original
   promotion exception is propagated (the rollback failure is logged and
   attached via implicit exception context).
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from transcriptx.core.analysis.llm_support.filenames import safe_speaker_filename
from transcriptx.core.output.output_service import OutputService
from transcriptx.core.utils.artifact_writer import write_json, write_text
from transcriptx.core.utils.logger import get_logger

__all__ = [
    "write_llm_artifacts",
    "write_llm_speaker_artifacts",
]

logger = get_logger()


def _rollback_promoted_file(
    final_path: Path,
    backup_path: Optional[Path],
    *,
    had_prior: bool,
) -> None:
    if had_prior and backup_path is not None and backup_path.exists():
        os.replace(str(backup_path), str(final_path))
    elif final_path.exists():
        final_path.unlink()


def _write_llm_pair(
    *,
    json_final: Path,
    md_final: Path,
    payload: Dict[str, Any],
    markdown: str,
    output_service: OutputService,
) -> Tuple[str, str]:
    """Write a JSON/Markdown pair to fully resolved final paths.

    Callers are responsible for path construction (directory layout and
    filename scheme); this function owns staging, promotion, rollback, and
    registration ordering per the module contract.
    """
    staging_root = json_final.parent / ".staging"
    staging = staging_root / str(uuid.uuid4())
    try:
        staging.mkdir(parents=True, exist_ok=True)

        json_staging = staging / json_final.name
        md_staging = staging / md_final.name
        had_json = json_final.exists()
        had_md = md_final.exists()
        json_backup = staging / f".backup.{json_final.name}" if had_json else None
        md_backup = staging / f".backup.{md_final.name}" if had_md else None
        if had_json and json_backup is not None:
            shutil.copy2(json_final, json_backup)
        if had_md and md_backup is not None:
            shutil.copy2(md_final, md_backup)

        write_json(str(json_staging), payload)
        write_text(str(md_staging), markdown)

        os.replace(str(json_staging), str(json_final))
        try:
            os.replace(str(md_staging), str(md_final))
        except BaseException as promote_exc:
            # Undo the JSON promotion exactly once. If the rollback itself
            # fails, log it, attach it to the original promotion failure's
            # context chain, and re-raise the original error.
            try:
                _rollback_promoted_file(json_final, json_backup, had_prior=had_json)
            except Exception as rollback_exc:
                logger.error(
                    "Rollback of %s failed while handling a Markdown promotion "
                    "failure; the original error is propagated",
                    json_final,
                )
                promote_exc.__context__ = rollback_exc
            raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if staging_root.exists() and not any(staging_root.iterdir()):
            staging_root.rmdir()

    # Registration begins only after both promotions succeeded. No filesystem
    # rollback from here on: a record_file failure leaves both files promoted
    # (and possibly a partial registration) and propagates.
    output_service.record_file(json_final, "json")
    output_service.record_file(md_final, "md")
    return str(json_final), str(md_final)


def write_llm_speaker_artifacts(
    output_service: OutputService,
    *,
    speaker: str,
    artifact_filename: str,
    payload: Dict[str, Any],
    markdown: str,
) -> Tuple[str, str]:
    """
    Write per-speaker JSON and Markdown under ``data/speakers/`` using the
    pair promotion contract.
    """
    structure = output_service.get_output_structure()
    out_dir = Path(structure.speaker_data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = output_service.base_name
    safe_speaker = safe_speaker_filename(speaker)
    return _write_llm_pair(
        json_final=out_dir / f"{base}_{safe_speaker}_{artifact_filename}.json",
        md_final=out_dir / f"{base}_{safe_speaker}_{artifact_filename}.md",
        payload=payload,
        markdown=markdown,
        output_service=output_service,
    )


def write_llm_artifacts(
    output_service: OutputService,
    *,
    artifact_stem: str,
    payload: Dict[str, Any],
    markdown: str,
) -> Tuple[str, str]:
    """
    Write global JSON and Markdown under ``data/global/`` using the pair
    promotion contract.
    """
    structure = output_service.get_output_structure()
    out_dir = Path(structure.global_data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = output_service.base_name
    return _write_llm_pair(
        json_final=out_dir / f"{base}_{artifact_stem}.json",
        md_final=out_dir / f"{base}_{artifact_stem}.md",
        payload=payload,
        markdown=markdown,
        output_service=output_service,
    )
