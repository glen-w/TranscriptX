"""Run-finalization coordinator: chart descriptions → synthesis → manifest."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from transcriptx.core.analysis.chart_descriptions.generate import (
    ChartDescriptionsAttemptResult,
    run_chart_descriptions,
)
from transcriptx.core.analysis.chart_descriptions.inventory_builder import (
    build_logical_chart_inventory,
)
from transcriptx.core.analysis.chart_descriptions.lock import (
    RunFinalizationLockTimeout,
    run_finalization_lock,
)
from transcriptx.core.analysis.chart_descriptions.publisher import (
    gc_old_committed_generations,
)
from transcriptx.core.analysis.chart_descriptions.schemas import MODULE_ID
from transcriptx.core.pipeline.manifest_builder import write_output_manifest
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


@dataclass
class FinalizationResult:
    chart_descriptions: ChartDescriptionsAttemptResult | None = None
    synthesis_meta: dict[str, Any] = field(default_factory=dict)
    manifest_path: Path | None = None
    module_results: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    lock_timeout: bool = False


def _llm_enabled(config: Any) -> bool:
    llm = getattr(config, "llm", None)
    if not bool(getattr(llm, "enabled", False)):
        return False
    provider = str(getattr(llm, "provider", "") or "").lower()
    if provider in {"", "null", "none"}:
        return False
    return True


def _chart_descriptions_selected(selected_modules: list[str]) -> bool:
    return MODULE_ID in selected_modules


def _chart_cfg(config: Any) -> Any:
    return getattr(getattr(config, "analysis", None), "chart_descriptions", None)


def run_finalization_coordinator(
    *,
    run_dir: Path,
    run_id: str,
    transcript_key: str,
    selected_modules: list[str],
    modules_enabled: list[str],
    config: Any,
    run_kind: str,
    run_group_synthesis: bool = False,
    completed_agg_ids: set[str] | None = None,
    aggregation_warnings: list[dict[str, Any]] | None = None,
    member_charts: list[dict[str, Any]] | None = None,
    user_overview: list[str] | None = None,
    already_holding_lock: bool = False,
) -> FinalizationResult:
    """Own chart-description publication → group synthesis → single manifest write.

    Caller must not hold nested chart/synthesis locks. When ``already_holding_lock``
    is True, caller already holds ``run_finalization_lock``.
    """
    result = FinalizationResult()
    # Seed with caller warnings for synthesis context, but return only
    # warnings appended during this finalization (callers may extend).
    warnings = list(aggregation_warnings or [])
    _incoming_warning_count = len(warnings)
    completed_agg_ids = set(completed_agg_ids or ())

    def _body() -> None:
        supplemental: list[dict[str, str]] = []
        finalizer_outcomes: dict[str, Any] = {}

        # --- Chart descriptions (only when module selected) ---
        cd_selected = _chart_descriptions_selected(selected_modules)
        if cd_selected:
            cd_cfg = _chart_cfg(config)
            cd_enabled = bool(getattr(cd_cfg, "enabled", True)) if cd_cfg else True
            chart_set = str(getattr(cd_cfg, "chart_set", "all") if cd_cfg else "all")
            llm_on = _llm_enabled(config)

            try:
                inventory, skips = build_logical_chart_inventory(
                    run_dir,
                    run_kind=run_kind,  # type: ignore[arg-type]
                    run_target_id=transcript_key or run_id,
                    member_charts=member_charts,
                )
                for skip in skips:
                    warnings.append(
                        {
                            "code": "CHART_INVENTORY_SKIP",
                            "message": str(skip.get("reason") or "skip"),
                            "details": skip,
                        }
                    )
                snapshot_hash = inventory.snapshot_sha256()
                snapshot_hash2 = inventory.snapshot_sha256()
                if snapshot_hash != snapshot_hash2:
                    raise RuntimeError("inventory snapshot mutated during finalization")

                cd_result = run_chart_descriptions(
                    run_root=run_dir,
                    run_id=run_id,
                    inventory=inventory,
                    inventory_snapshot_sha256=snapshot_hash,
                    chart_set=chart_set,
                    selected=True,
                    enabled=cd_enabled,
                    llm_enabled=llm_on,
                    config=config,
                    user_overview=user_overview,
                )
                result.chart_descriptions = cd_result
                if cd_result.module_result:
                    result.module_results[MODULE_ID] = cd_result.module_result
                if cd_result.published:
                    supplemental.extend(cd_result.inventory_entries)
                    finalizer_outcomes["chart_descriptions"] = {
                        "generation_id": cd_result.generation_id,
                        "attempt_epoch": cd_result.attempt_epoch,
                        "overall_status": cd_result.overall_status,
                        "attempt_status": cd_result.attempt_status,
                    }
                    if cd_result.generation_id:
                        try:
                            gc_old_committed_generations(
                                run_dir,
                                active_generation_id=cd_result.generation_id,
                            )
                        except Exception:
                            logger.exception("chart_descriptions GC failed")
                else:
                    finalizer_outcomes["chart_descriptions"] = {
                        "attempt_status": "failed",
                        "error_code": cd_result.error_code,
                        "error_message_safe": cd_result.error_message_safe,
                        "published": False,
                    }
                    warnings.append(
                        {
                            "code": "CHART_DESCRIPTIONS_FATAL",
                            "message": cd_result.error_message_safe
                            or "chart descriptions publish failed",
                        }
                    )
                warnings.extend(cd_result.warnings or [])
            except Exception as exc:
                logger.exception("chart_descriptions finalizer failed")
                warnings.append(
                    {
                        "code": "CHART_DESCRIPTIONS_FATAL",
                        "message": str(exc)[:240],
                    }
                )
                finalizer_outcomes["chart_descriptions"] = {
                    "attempt_status": "failed",
                    "error_code": "FINALIZER_EXCEPTION",
                    "error_message_safe": str(exc)[:240],
                }

        # --- Group LLM synthesis (optional) ---
        if run_group_synthesis:
            try:
                from transcriptx.core.analysis.group_llm_synthesis.finalize_hook import (
                    run_synthesis_publish_and_manifest,
                )

                # Use synthesis body without nested lock / without its own manifest
                synthesis_meta = _run_synthesis_only(
                    run_dir=run_dir,
                    run_id=run_id,
                    transcript_key=transcript_key,
                    selected_modules=selected_modules,
                    completed_agg_ids=completed_agg_ids,
                    config=config,
                    aggregation_warnings=warnings,
                )
                result.synthesis_meta = synthesis_meta or {}
                inv = list(synthesis_meta.get("inventory_entries") or [])
                supplemental.extend(inv)
                finalizer_outcomes["group_llm_synthesis"] = {
                    k: v
                    for k, v in (synthesis_meta or {}).items()
                    if k != "inventory_entries"
                }
            except Exception as exc:
                logger.exception("group llm synthesis during coordinator failed")
                warnings.append(
                    {
                        "code": "GROUP_LLM_SYNTHESIS_FATAL",
                        "message": str(exc)[:240],
                    }
                )

        # --- Single manifest write ---
        try:
            result.manifest_path = write_output_manifest(
                run_dir,
                run_id,
                transcript_key,
                modules_enabled,
                supplemental_inventory_entries=supplemental,
                finalizer_outcomes=finalizer_outcomes,
            )
        except Exception as exc:
            logger.exception("manifest write after publication failed")
            warnings.append(
                {
                    "code": "MANIFEST_WRITE_FAILED",
                    "message": str(exc)[:240],
                }
            )

        result.warnings = warnings[_incoming_warning_count:]

    if already_holding_lock:
        _body()
        return result

    try:
        with run_finalization_lock(run_dir):
            _body()
    except RunFinalizationLockTimeout as exc:
        result.lock_timeout = True
        result.warnings.append(
            {"code": "RUN_FINALIZATION_LOCK_TIMEOUT", "message": str(exc)[:240]}
        )
        # Still attempt base manifest without supplemental inventory
        try:
            result.manifest_path = write_output_manifest(
                run_dir,
                run_id,
                transcript_key,
                modules_enabled,
            )
        except Exception:
            logger.exception("base manifest write after lock timeout failed")
    return result


def _run_synthesis_only(
    *,
    run_dir: Path,
    run_id: str,
    transcript_key: str,
    selected_modules: list[str],
    completed_agg_ids: set[str],
    config: Any,
    aggregation_warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run group synthesis publish without acquiring synthesis lock or writing manifest."""
    from transcriptx.core.analysis.group_llm_synthesis.generation import (
        gc_old_committed_generations as synth_gc,
    )
    from transcriptx.core.analysis.group_llm_synthesis.synthesize import (
        run_group_llm_synthesis,
    )

    want_global = (
        "llm_summary" in selected_modules and "llm_summary" in completed_agg_ids
    )
    want_speakers = (
        "llm_speaker_summary" in selected_modules
        and "llm_speaker_summary" in completed_agg_ids
    )
    synthesis_meta: dict[str, Any] = {}
    if not (want_global or want_speakers):
        return synthesis_meta

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
        "inventory_entries": list(attempt.inventory_entries),
    }
    for w in attempt.warnings:
        if isinstance(w, dict) and w.get("code"):
            aggregation_warnings.append(w)
    if attempt.published and attempt.generation_id:
        try:
            synth_gc(run_dir, active_generation_id=attempt.generation_id)
        except Exception:
            logger.exception("synthesis GC failed")
    return synthesis_meta
