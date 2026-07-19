"""Finalize hook: run synthesis + merge manifest under synthesis lock."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from transcriptx.core.analysis.aggregation.warnings import build_warning
from transcriptx.core.analysis.group_llm_synthesis import errors as synth_err
from transcriptx.core.analysis.group_llm_synthesis.generation import (
    gc_old_committed_generations,
)
from transcriptx.core.analysis.group_llm_synthesis.lock import (
    SynthesisLockTimeout,
    synthesis_lock,
)
from transcriptx.core.analysis.group_llm_synthesis.synthesize import (
    run_group_llm_synthesis,
)
from transcriptx.core.pipeline.manifest_builder import write_output_manifest
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def run_synthesis_publish_and_manifest(
    *,
    run_dir: Path,
    run_id: str,
    transcript_key: str,
    selected_modules: list[str],
    completed_agg_ids: set[str],
    config: Any,
    aggregation_warnings: list[dict[str, Any]],
    already_holding_lock: bool = False,
) -> dict[str, Any]:
    """Synthesize (if collect present) and write manifest with explicit entries.

    When ``already_holding_lock`` is True, caller holds ``synthesis_lock``.
    """
    want_global = (
        "llm_summary" in selected_modules and "llm_summary" in completed_agg_ids
    )
    want_speakers = (
        "llm_speaker_summary" in selected_modules
        and "llm_speaker_summary" in completed_agg_ids
    )
    synthesis_meta: dict[str, Any] = {}
    inventory: list[dict[str, str]] = []

    def _body() -> None:
        nonlocal synthesis_meta, inventory
        if want_global or want_speakers:
            attempt = run_group_llm_synthesis(
                run_root=run_dir,
                run_id=run_id,
                config=config,
                want_global=want_global,
                want_speakers=want_speakers,
            )
            synthesis_meta = {
                "attempt_status": attempt.attempt_status,
                "published": attempt.published,
                "generation_id": attempt.generation_id,
                "overall_status": attempt.overall_status,
                "error_code": attempt.error_code,
            }
            inventory = list(attempt.inventory_entries)
            for w in attempt.warnings:
                if isinstance(w, dict) and w.get("code"):
                    aggregation_warnings.append(
                        build_warning(
                            code=str(w["code"]),
                            message=str(
                                w.get("message")
                                or w.get("error_message_safe")
                                or w["code"]
                            ),
                            aggregation_key="group_llm_synthesis",
                            details=w,
                        )
                    )
            manifest_path = write_output_manifest(
                run_dir=run_dir,
                run_id=run_id,
                transcript_key=transcript_key,
                modules_enabled=selected_modules,
                synthesis_inventory_entries=inventory or None,
            )
            if (
                manifest_path is not None
                and attempt.published
                and attempt.generation_id
            ):
                gc_old_committed_generations(
                    run_dir,
                    active_generation_id=attempt.generation_id,
                )
        else:
            write_output_manifest(
                run_dir=run_dir,
                run_id=run_id,
                transcript_key=transcript_key,
                modules_enabled=selected_modules,
            )

    try:
        if already_holding_lock:
            _body()
        elif want_global or want_speakers:
            with synthesis_lock(run_dir):
                _body()
        else:
            _body()
    except SynthesisLockTimeout as exc:
        logger.warning("group LLM synthesis lock timeout: %s", exc)
        aggregation_warnings.append(
            build_warning(
                code=synth_err.SYNTHESIS_LOCK_TIMEOUT,
                message=str(exc),
                aggregation_key="group_llm_synthesis",
            )
        )
        synthesis_meta = {
            "attempt_status": "lock_timeout",
            "published": False,
            "error_code": synth_err.SYNTHESIS_LOCK_TIMEOUT,
        }
        write_output_manifest(
            run_dir=run_dir,
            run_id=run_id,
            transcript_key=transcript_key,
            modules_enabled=selected_modules,
        )
    return synthesis_meta
