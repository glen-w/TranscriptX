"""Shared save / persist helpers for emotion-family producers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from transcriptx.core.analysis.emotion_family.errors import (
    EmotionFamilyGenerationValidationError,
    EmotionFamilyPersistError,
)
from transcriptx.core.analysis.emotion_family.generational_store import (
    INDEX_FILENAME,
    load_index,
    persist_generation_from_results,
    record_attempt_only,
    update_enriched_projection_status,
    validate_generation_integrity,
)
from transcriptx.core.analysis.emotion_family.run_status import RunStatus
from transcriptx.core.utils.logger import log_warning


def _module_dir_from_output_service(output_service: Any) -> Any | None:
    structure = output_service.get_output_structure()
    module_dir = getattr(structure, "module_dir", None)
    if module_dir is None and isinstance(structure, dict):
        module_dir = structure.get("module_dir")
    return module_dir


def apply_pending_projections(
    results: dict[str, Any],
    *,
    apply_one: Callable[[dict[str, Any], dict[str, Any]], None],
) -> int:
    """Apply and consume ``_pending_projections`` after canonical activation."""
    pending = results.pop("_pending_projections", None) or []
    for seg, proj in pending:
        apply_one(seg, proj)
    return len(pending)


def persist_canonical_then_enrich(
    *,
    results: dict[str, Any],
    output_service: Any,
    module_id: str,
    log_prefix: str,
    write_enriched: Callable[[], None],
    after_enrich: Callable[[], None] | None = None,
    clear_owned_fields: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    """
    Canonical commit is fatal. Enriched projection write is non-fatal/repairable.
    Secondary after_enrich callbacks are independently non-fatal.

    On successful canonical persist, strips ``_canonical_rows`` / ``canonical_rows``
    from the in-memory result. Projection / secondary failure sets status fields
    without deactivating the generation or flipping run_status.

    On persist failure, drops pending projections without applying them and
    optionally clears owned fields on shared segments.
    """
    try:
        persist_payload = dict(results)
        if "canonical_rows" not in persist_payload:
            persist_payload["canonical_rows"] = (
                persist_payload.get("_canonical_rows") or []
            )
        persist_generation_from_results(persist_payload, output_service, module_id)
    except Exception as exc:
        log_warning(log_prefix, f"generational persist failed: {exc}")
        results["run_status"] = RunStatus.FAILED.value
        results["usable_output"] = False
        results.setdefault("warnings", []).append(f"persist_failed: {exc}")
        results["enriched_projection_status"] = "skipped"
        results["secondary_output_status"] = "skipped"
        results.pop("_pending_projections", None)
        if clear_owned_fields is not None:
            for key in (
                "segments_with_emotion",
                "segments_with_contextual_emotion",
                "segments_with_fine_grained_emotion",
            ):
                for seg in results.get(key) or []:
                    if isinstance(seg, dict):
                        clear_owned_fields(seg)
        module_dir = _module_dir_from_output_service(output_service)
        if module_dir is not None:
            try:
                record_attempt_only(
                    module_dir,
                    module_id=module_id,
                    generation_id=str(results.get("artifact_generation_id") or ""),
                    run_status=RunStatus.FAILED.value,
                    usable_output=False,
                    extra={"persist_error": str(exc)},
                )
            except Exception:
                pass
        raise EmotionFamilyPersistError(
            f"{module_id} canonical persist failed: {exc}"
        ) from exc

    # Canonical is authoritative; drop private write buffer from returned result.
    results.pop("_canonical_rows", None)
    results.pop("canonical_rows", None)

    module_dir = _module_dir_from_output_service(output_service)
    generation_id = str(results.get("artifact_generation_id") or "")

    try:
        write_enriched()
        results["enriched_projection_status"] = "ok"
    except Exception as exc:
        log_warning(log_prefix, f"enriched projection write failed: {exc}")
        results["enriched_projection_status"] = "failed"
        results.setdefault("warnings", []).append(f"enriched_projection_failed: {exc}")

    secondary_status = "ok"
    if after_enrich is not None:
        try:
            after_enrich()
        except Exception as exc:
            log_warning(log_prefix, f"secondary output failed: {exc}")
            secondary_status = "failed"
            results.setdefault("warnings", []).append(f"secondary_output_failed: {exc}")
    results["secondary_output_status"] = secondary_status

    if module_dir is not None and generation_id:
        try:
            update_enriched_projection_status(
                module_dir,
                module_id=module_id,
                generation_id=generation_id,
                enriched_projection_status=str(
                    results.get("enriched_projection_status") or "failed"
                ),
                secondary_output_status=secondary_status,
            )
        except Exception as exc:
            log_warning(
                log_prefix,
                f"could not persist enriched_projection_status: {exc}",
            )


def repair_enriched_projections(
    module_dir: Path | str,
    *,
    module_id: str,
    segments: list[dict[str, Any]],
    project_row: Callable[..., dict[str, Any]],
    apply_projection: Callable[[dict[str, Any], dict[str, Any]], None],
    clear_projection: Callable[[dict[str, Any]], None],
    generation_id: str | None = None,
    schema_version: str | None = None,
) -> dict[str, Any]:
    """
    Rebuild enriched projections from a validated complete generation.

    Does not rewrite canonical rows/manifest or change activation. Idempotent:
    clears owned fields then re-applies projections for matching segment IDs.
    """
    module_path = Path(module_dir)
    index = load_index(module_path / INDEX_FILENAME)
    if index is None:
        raise EmotionFamilyGenerationValidationError(
            f"no artifact index under {module_path}"
        )
    gid = generation_id or index.current_complete_generation
    if not gid:
        raise EmotionFamilyGenerationValidationError(
            "no current_complete_generation to repair from"
        )
    if index.current_complete_generation and gid != index.current_complete_generation:
        raise EmotionFamilyGenerationValidationError(
            "repair only allowed for current_complete_generation"
        )

    rows, manifest = validate_generation_integrity(module_path, gid)
    if str(manifest.get("module_id") or "") != module_id:
        raise EmotionFamilyGenerationValidationError(
            f"module_id mismatch: expected {module_id}, got {manifest.get('module_id')}"
        )
    schema = schema_version or str(manifest.get("schema_version") or "")
    semantics = str(manifest.get("semantics_version") or "")
    by_id = {str(r.get("segment_id")): r for r in rows if r.get("segment_id")}

    applied = 0
    for seg in segments:
        clear_projection(seg)
        sid = str(seg.get("id") or seg.get("segment_id") or "")
        row = by_id.get(sid)
        if row is None:
            continue
        project_kwargs: dict[str, Any] = {
            "artifact_generation_id": gid,
            "schema_version": schema,
        }
        if semantics:
            project_kwargs["semantics_version"] = semantics
        proj = project_row(row, **project_kwargs)
        apply_projection(seg, proj)
        applied += 1

    update_enriched_projection_status(
        module_path,
        module_id=module_id,
        generation_id=gid,
        enriched_projection_status="ok",
        secondary_output_status=None,
    )
    return {
        "module_id": module_id,
        "artifact_generation_id": gid,
        "segments_repaired": applied,
        "enriched_projection_status": "ok",
    }
