"""
Group / multi-transcript analysis finalization: TranscriptSet, aggregation, artifacts.

Extracted from pipeline.run_analysis_pipeline for maintainability.
"""

from __future__ import annotations

import inspect
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.output.group_output_service import GroupOutputService
from transcriptx.core.observability.run_performance.recorder import (
    PENDING_RUN_ID,
    RecorderState,
    RunPerformanceRecorder,
)
from transcriptx.core.pipeline.manifest_builder import (
    write_output_manifest,
    write_run_results_summary,
)
from transcriptx.core.pipeline.module_outcomes import aggregate_group_module_lists
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap
from transcriptx.core.pipeline.target_resolver import AnalysisScope
from transcriptx.core.utils.config import TranscriptXConfig, get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.io import save_json

logger = get_logger()

PERFORMANCE_SIDECAR_WRITE_FAILED = "run_performance_write_failed"
PERFORMANCE_SIDECAR_RESULTS_UNAVAILABLE = "run_performance_results_unavailable"


def _member_completed(result: PerTranscriptResult) -> bool:
    return bool(
        str(result.run_id or "").strip() and str(result.output_dir or "").strip()
    )


def _build_group_performance_meta(
    per_transcript_results: Sequence[PerTranscriptResult],
) -> Any:
    from transcriptx.core.observability.run_performance.schema import (
        GroupPerformanceMeta,
    )

    member_count = len(per_transcript_results)
    members_completed = sum(1 for r in per_transcript_results if _member_completed(r))
    members_failed = member_count - members_completed
    partial = members_completed < member_count
    return GroupPerformanceMeta(
        member_count=member_count,
        members_completed=members_completed,
        members_failed=members_failed,
        partial=partial,
    )


def _derive_group_performance_statuses(
    *,
    per_transcript_results: Sequence[PerTranscriptResult],
    group_errors: Sequence[str],
    aggregation_disabled: bool,
    group_phase_terminal_failure: bool,
) -> tuple[Any, Any, Optional[str]]:
    from transcriptx.core.observability.run_performance.schema import (
        ExecutionStatus,
        FinalStatus,
    )

    meta = _build_group_performance_meta(per_transcript_results)
    member_count = meta.member_count
    members_completed = int(meta.members_completed or 0)

    if group_phase_terminal_failure:
        return (
            ExecutionStatus.failed,
            FinalStatus.failed,
            "group_phase_terminal_failure",
        )
    if member_count == 0:
        return ExecutionStatus.failed, FinalStatus.failed, "no_members"
    if members_completed == 0:
        return ExecutionStatus.failed, FinalStatus.failed, "all_members_failed"
    if meta.partial or group_errors:
        term = "partial_member_outcomes" if meta.partial else "group_errors_present"
        if aggregation_disabled:
            term = "aggregation_disabled_partial"
        return ExecutionStatus.partial, FinalStatus.partial, term
    if aggregation_disabled:
        return (
            ExecutionStatus.succeeded,
            FinalStatus.succeeded,
            "aggregation_disabled",
        )
    return ExecutionStatus.succeeded, FinalStatus.succeeded, None


def _write_group_performance_sidecar_under_lease(
    *,
    run_dir: Path,
    performance_recorder: Optional[RunPerformanceRecorder],
    per_transcript_results: Sequence[PerTranscriptResult],
    group_errors: Sequence[str],
    selected_modules: Sequence[str],
    aggregation_disabled: bool,
    group_phase_terminal_failure: bool = False,
) -> Optional[str]:
    """Stop/freeze/write group sidecar. Caller must already hold the group lease.

    Returns a coded warning string on optional telemetry loss, else None.
    Does not acquire any lock.
    """
    if performance_recorder is None:
        return None

    from transcriptx.core.observability.run_performance.io import write_run_performance
    from transcriptx.core.observability.run_performance.schema import (
        AnalysisContextSnapshot,
        CacheProvenance,
    )
    from transcriptx.core.pipeline.manifest_loader import load_run_results
    from transcriptx.core.utils.run_manifest import get_transcriptx_version

    def _stop_wall_best_effort() -> None:
        if performance_recorder.state == RecorderState.running:
            performance_recorder.stop_wall_clock()

    rr_path = Path(run_dir) / "run_results.json"
    if not rr_path.exists():
        # Required persistence boundary reached for the caller; stop even if we refuse write.
        _stop_wall_best_effort()
        logger.warning(
            "group run_performance skipped code=%s",
            PERFORMANCE_SIDECAR_RESULTS_UNAVAILABLE,
        )
        return PERFORMANCE_SIDECAR_RESULTS_UNAVAILABLE

    try:
        rr = load_run_results(rr_path)
    except Exception as exc:
        _stop_wall_best_effort()
        logger.warning(
            "group run_performance skipped code=%s err_type=%s",
            PERFORMANCE_SIDECAR_RESULTS_UNAVAILABLE,
            type(exc).__name__,
        )
        return PERFORMANCE_SIDECAR_RESULTS_UNAVAILABLE

    loaded_run_id = str(rr.get("run_id") or "").strip()
    if not loaded_run_id:
        _stop_wall_best_effort()
        logger.warning(
            "group run_performance skipped code=%s detail=missing_run_id",
            PERFORMANCE_SIDECAR_RESULTS_UNAVAILABLE,
        )
        return PERFORMANCE_SIDECAR_RESULTS_UNAVAILABLE

    # Stop outside the measured interval only after canonical results validate.
    _stop_wall_best_effort()

    try:
        if performance_recorder.run_id == PENDING_RUN_ID:
            performance_recorder.set_run_id(loaded_run_id)
        elif performance_recorder.run_id != loaded_run_id:
            logger.warning(
                "group run_performance skipped code=%s detail=run_id_mismatch",
                PERFORMANCE_SIDECAR_RESULTS_UNAVAILABLE,
            )
            return PERFORMANCE_SIDECAR_RESULTS_UNAVAILABLE
        group_meta = _build_group_performance_meta(per_transcript_results)
        exec_status, final_status, term = _derive_group_performance_statuses(
            per_transcript_results=per_transcript_results,
            group_errors=group_errors,
            aggregation_disabled=aggregation_disabled,
            group_phase_terminal_failure=group_phase_terminal_failure,
        )
        snap = performance_recorder.freeze(
            execution_status=exec_status,
            final_status=final_status,
            termination_reason_code=term,
            cache_provenance=CacheProvenance.unwired,
            analysis=AnalysisContextSnapshot(
                app_version=get_transcriptx_version(),
                requested_module_count=len(selected_modules),
            ),
            group=group_meta,
        )
        # Intentionally omit llm= (group LLM metrics not instrumented in v1).
        write_run_performance(Path(run_dir), snap)
        performance_recorder.mark_persisted(success=True)
        return None
    except Exception as exc:
        logger.warning(
            "group run_performance telemetry write failed code=%s err_type=%s",
            PERFORMANCE_SIDECAR_WRITE_FAILED,
            type(exc).__name__,
        )
        try:
            if performance_recorder.state == RecorderState.frozen:
                performance_recorder.mark_persisted(success=False)
        except Exception:
            pass
        return PERFORMANCE_SIDECAR_WRITE_FAILED


def _commit_group_run_results_and_performance(
    *,
    run_dir: Path,
    group_run_id: str,
    group_uuid: str,
    selected_modules: List[str],
    per_transcript_results: List[PerTranscriptResult],
    group_errors: List[str],
    aggregation_disabled: bool,
    performance_recorder: Optional[RunPerformanceRecorder],
    module_results: Optional[Dict[str, Any]] = None,
    write_manifest: bool = True,
    group_phase_terminal_failure: bool = False,
) -> Optional[str]:
    """Write canonical group run_results (+ optional manifest), then performance sidecar."""
    agg_run, agg_skipped = aggregate_group_module_lists(
        selected_modules, per_transcript_results
    )
    write_run_results_summary(
        run_dir=run_dir,
        run_id=group_run_id,
        transcript_key=group_uuid,
        modules_enabled=selected_modules,
        modules_run=agg_run,
        skipped_modules=agg_skipped,
        errors=group_errors,
        preset_explanation=None,
        module_results=module_results,
    )
    if write_manifest:
        write_output_manifest(
            run_dir=run_dir,
            run_id=group_run_id,
            transcript_key=group_uuid,
            modules_enabled=selected_modules,
        )
    return _write_group_performance_sidecar_under_lease(
        run_dir=run_dir,
        performance_recorder=performance_recorder,
        per_transcript_results=per_transcript_results,
        group_errors=group_errors,
        selected_modules=selected_modules,
        aggregation_disabled=aggregation_disabled,
        group_phase_terminal_failure=group_phase_terminal_failure,
    )


def _write_group_member_runs_json(
    run_dir: Path, per_transcript_results: List[PerTranscriptResult]
) -> None:
    """Record per-member transcript run directories for the Web UI (charts, etc.)."""
    payload = {
        "schema_version": 1,
        "members": [
            {
                "order_index": r.order_index,
                "transcript_path": r.transcript_path,
                "transcript_key": r.transcript_key,
                "run_id": r.run_id,
                "output_dir": r.output_dir,
            }
            for r in per_transcript_results
        ],
    }
    save_json(payload, str(run_dir / "group_member_runs.json"))


def _topo_sort_entries(entries: List[Any]) -> List[Any]:
    entry_map = {entry.agg_id: entry for entry in entries}
    incoming = {entry.agg_id: 0 for entry in entries}
    for entry in entries:
        for dep in entry.deps:
            if dep in incoming:
                incoming[entry.agg_id] += 1
    ready = sorted([key for key, count in incoming.items() if count == 0])
    ordered: List[Any] = []
    while ready:
        current = ready.pop(0)
        ordered.append(entry_map[current])
        for entry in entries:
            if current in entry.deps:
                incoming[entry.agg_id] -= 1
                if incoming[entry.agg_id] == 0:
                    ready.append(entry.agg_id)
                    ready.sort()
    if len(ordered) != len(entries):
        raise ValueError("Aggregation registry has cyclic dependencies.")
    return ordered


def _attach_session_identity(
    session_rows: List[Dict[str, Any]],
    per_transcript_results: List[PerTranscriptResult],
    transcript_set: TranscriptSet,
    get_transcript_id_fn: Callable[[PerTranscriptResult, TranscriptSet], Any],
) -> List[Dict[str, Any]]:
    by_path = {r.transcript_path: r for r in per_transcript_results}
    by_key = {r.transcript_key: r for r in per_transcript_results if r.transcript_key}
    by_index = {r.order_index: r for r in per_transcript_results}
    for row in session_rows:
        result = None
        if "transcript_path" in row and row["transcript_path"] in by_path:
            result = by_path[row["transcript_path"]]
        elif "session_path" in row and row["session_path"] in by_path:
            result = by_path[row["session_path"]]
        elif "transcript_key" in row and row["transcript_key"] in by_key:
            result = by_key[row["transcript_key"]]
        elif "order_index" in row and row["order_index"] in by_index:
            result = by_index[row["order_index"]]
        if result:
            row.setdefault("order_index", result.order_index)
            row.setdefault(
                "transcript_id", get_transcript_id_fn(result, transcript_set)
            )
    return session_rows


def _call_aggregate_fn(
    aggregate_fn: Callable[..., Dict[str, Any] | None],
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
    aggregations: Dict[str, Any],
) -> Dict[str, Any] | None:
    try:
        signature = inspect.signature(aggregate_fn)
    except (TypeError, ValueError):
        return aggregate_fn(
            per_transcript_results, canonical_speaker_map, transcript_set
        )
    parameters = list(signature.parameters.values())
    if any(param.kind == param.VAR_POSITIONAL for param in parameters):
        return aggregate_fn(
            per_transcript_results,
            canonical_speaker_map,
            transcript_set,
            aggregations,
        )
    if len(parameters) >= 4:
        return aggregate_fn(
            per_transcript_results,
            canonical_speaker_map,
            transcript_set,
            aggregations,
        )
    return aggregate_fn(per_transcript_results, canonical_speaker_map, transcript_set)


_ROW_KEYS = {"session_rows", "speaker_rows", "metrics_spec"}
_WRITER_EXTRA_KEYS = {
    "content_rows",
    "content_rows_name",
    "drop_csv_keys",
    "extra_tables",
    "schema_version",
}


def _row_payload(outcome: Dict[str, Any]) -> Dict[str, Any]:
    """
    Row writer payload: session/speaker rows and related CSV keys only.

    Chart generation uses a separate dict (``chart_outcome``). Optional pooled
    payloads are merged via ``merge_optional_chart_outcome_keys`` from a closed
    allowlist in ``transcriptx.core.pipeline.chart_outcome``—never pass the full
    aggregation outcome to chart generators.
    """
    allowed_keys = _ROW_KEYS | _WRITER_EXTRA_KEYS
    return {key: outcome[key] for key in allowed_keys if key in outcome}


def finalize_group_analysis(
    *,
    scope: AnalysisScope,
    members: Sequence[Any],
    resolved_paths: List[str],
    per_transcript_results: List[PerTranscriptResult],
    group_errors: List[str],
    selected_modules: List[str],
    config: Optional[TranscriptXConfig] = None,
    performance_recorder: Optional[RunPerformanceRecorder] = None,
) -> Dict[str, Any]:
    """Build TranscriptSet, optionally aggregate, write group artifacts; return result dict."""
    metadata: Dict[str, Any] = {}
    group_key: Optional[str] = None
    group_uuid: Optional[str] = None
    if scope.scope_type == "group":
        group_key = scope.key
        group_uuid = scope.uuid
        metadata["group_uuid"] = scope.uuid
        metadata["group_key"] = scope.key
    transcript_id_map: Dict[str, int] = {}
    transcript_uuid_map: Dict[str, str] = {}
    for member in members:
        if (
            getattr(member, "file_path", None)
            and getattr(member, "id", None) is not None
        ):
            transcript_id_map[str(member.file_path)] = int(member.id)
        if getattr(member, "file_path", None) and getattr(member, "uuid", None):
            transcript_uuid_map[str(member.file_path)] = str(member.uuid)
    if transcript_id_map:
        metadata["transcript_id_map"] = transcript_id_map
    if transcript_uuid_map:
        metadata["transcript_uuid_map"] = transcript_uuid_map
    transcript_set = TranscriptSet.create(
        transcript_ids=resolved_paths,
        name=scope.display_name,
        metadata=metadata,
        key=group_key,
    )

    group_config = config or get_config()
    if group_uuid is None:
        raise ValueError("Group scope is required for group output paths.")

    group_run_id = (
        f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    )
    if performance_recorder is not None:
        performance_recorder.set_run_id(group_run_id)
    member_uuids = [member.uuid for member in members]
    from transcriptx.core.utils.run_writer_locks import (
        RunWriterLock,
        run_lock_path_for_canonical_root,
    )
    from transcriptx.core.utils.paths import GROUP_OUTPUTS_DIR

    group_base = (
        Path(group_config.group_analysis.output_dir or GROUP_OUTPUTS_DIR)
        / group_uuid
        / group_run_id
    )
    _lock_path = run_lock_path_for_canonical_root(group_base)
    _lock_path.parent.mkdir(parents=True, exist_ok=True)
    _group_run_lock = RunWriterLock(_lock_path)
    if not _group_run_lock.acquire():
        raise RuntimeError(
            f"Could not acquire per-run lock for group output: {group_base}"
        )
    try:
        group_output_service = GroupOutputService(
            group_uuid=group_uuid,
            run_id=group_run_id,
            output_dir=group_config.group_analysis.output_dir,
            scaffold_by_session=group_config.group_analysis.scaffold_by_session,
            scaffold_by_speaker=group_config.group_analysis.scaffold_by_speaker,
            scaffold_comparisons=group_config.group_analysis.scaffold_comparisons,
        )
        transcript_set.metadata["group_output_dir"] = str(group_output_service.base_dir)
        transcript_set.metadata["group_run_id"] = group_run_id
        member_transcript_ids = [member.id for member in members]
        member_display_names = [member.file_name for member in members]
        qa_extra: Dict[str, Any] = {}
        try:
            from transcriptx.core.analysis.llm_custom_qa.questions_binding import (
                get_bound_custom_qa_questions,
            )

            effective_qa = get_bound_custom_qa_questions()
            if effective_qa is not None:
                qa_extra = effective_qa.to_metadata()
        except Exception:
            qa_extra = {}
        group_output_service.write_group_run_metadata(
            group_uuid=group_uuid,
            group_name_at_run=scope.display_name,
            group_key=group_key,
            member_transcript_ids=member_transcript_ids,
            member_display_names=member_display_names,
            selected_modules=selected_modules,
            extra_metadata=qa_extra or None,
        )
        _write_group_member_runs_json(
            Path(group_output_service.base_dir), per_transcript_results
        )

        if not group_config.group_analysis.enabled:
            summary_text = (
                f"Group key: {transcript_set.key}\n"
                f"Transcripts: {len(per_transcript_results)}\n"
                f"Run ID: {group_run_id}\n"
                "(Aggregation disabled in config.)\n"
            )
            group_output_service.save_summary(summary_text)
            group_output_service.write_group_manifest(
                group_id=group_uuid,
                group_key=group_key or transcript_set.key,
                transcript_file_uuids=member_uuids,
                transcript_paths=resolved_paths,
                run_id=group_run_id,
            )
            perf_warning = _commit_group_run_results_and_performance(
                run_dir=Path(group_output_service.base_dir),
                group_run_id=group_run_id,
                group_uuid=group_uuid,
                selected_modules=selected_modules,
                per_transcript_results=per_transcript_results,
                group_errors=group_errors,
                aggregation_disabled=True,
                performance_recorder=performance_recorder,
                write_manifest=True,
            )
            phase_meta: Dict[str, Any] = {
                "group_phase_terminal_failure": False,
                "aggregation_warning_count": 0,
                "chart_failure_count": 0,
                "terminal_errors": [],
            }
            if perf_warning:
                phase_meta["performance_sidecar_warning"] = perf_warning
            return {
                "status": "completed",
                "group_key": transcript_set.key,
                "group_uuid": group_uuid,
                "group_run_id": group_run_id,
                "group_output_dir": str(group_output_service.base_dir),
                "transcript_set": transcript_set.to_dict(),
                "transcripts": [result.to_dict() for result in per_transcript_results],
                "errors": group_errors,
                "warning": "Group analysis is disabled in config; aggregation skipped.",
                "aggregation_warnings": [],
                "group_phase_metadata": phase_meta,
            }

        from transcriptx.core.analysis.aggregation.registry import build_registry
        from transcriptx.core.analysis.aggregation.schema import get_transcript_id
        from transcriptx.core.analysis.aggregation.warnings import build_warning
        from transcriptx.core.analysis.group_charts.runner import (
            run_group_aggregate_charts,
        )
        from transcriptx.core.pipeline.chart_outcome import (
            merge_optional_chart_outcome_keys,
        )
        from transcriptx.core.output.group_row_writer import write_row_outputs
        from transcriptx.core.pipeline.speaker_normalizer import (
            normalize_speakers_across_transcripts,
        )

        canonical_speaker_map = normalize_speakers_across_transcripts(
            per_transcript_results
        )

        aggregation_warnings: List[Dict[str, Any]] = []
        aggregations: Dict[str, Any] = {}
        completed: set[str] = set()
        registry = build_registry()
        ordered = _topo_sort_entries(registry)
        run_dir = Path(group_output_service.base_dir)
        synthesis_meta: Dict[str, Any] = {}

        def _run_aggregation_loop(*, skip_synth_aggs: bool = False) -> None:
            _synth_agg_ids = frozenset({"llm_summary", "llm_speaker_summary"})
            for entry in ordered:
                if skip_synth_aggs and entry.agg_id in _synth_agg_ids:
                    continue
                if not entry.selector(selected_modules):
                    continue

                missing_deps = [dep for dep in entry.deps if dep not in completed]

                if missing_deps:
                    aggregation_warnings.append(
                        build_warning(
                            code="MISSING_DEP",
                            message=f"Missing dependencies: {', '.join(missing_deps)}",
                            aggregation_key=entry.agg_id,
                            missing_deps=missing_deps,
                            details={"missing_keys": missing_deps},
                        )
                    )

                    continue

                outcome = _call_aggregate_fn(
                    entry.aggregate_fn,
                    per_transcript_results,
                    canonical_speaker_map,
                    transcript_set,
                    aggregations,
                )

                if outcome is None:
                    continue

                if isinstance(outcome, dict) and outcome.get("warning"):
                    aggregation_warnings.append(outcome["warning"])

                    continue

                if isinstance(outcome, dict):
                    for w in outcome.get("aggregation_warnings") or []:
                        if isinstance(w, dict) and w.get("code"):
                            aggregation_warnings.append(w)

                if entry.output_type == "blob":
                    blob_name = outcome.get("blob_name", "summary")

                    blob_payload = outcome.get("blob_payload", {})

                    blob_dir = Path(group_output_service.base_dir) / entry.agg_id

                    blob_dir.mkdir(parents=True, exist_ok=True)

                    save_json(blob_payload, str(blob_dir / f"{blob_name}.json"))

                    stored = dict(outcome)

                    stored["output_type"] = "blob"

                    stored["artifact"] = str(blob_dir / f"{blob_name}.json")

                    aggregations[entry.agg_id] = stored

                    completed.add(entry.agg_id)

                    continue

                row_payload = _row_payload(outcome)

                session_rows = row_payload.get("session_rows", [])

                speaker_rows = row_payload.get("speaker_rows", [])

                metrics_spec = row_payload.get("metrics_spec")

                content_rows = row_payload.get("content_rows")

                content_rows_name = row_payload.get("content_rows_name")

                drop_csv_keys = row_payload.get("drop_csv_keys")

                extra_tables = row_payload.get("extra_tables")

                session_rows = _attach_session_identity(
                    session_rows,
                    per_transcript_results,
                    transcript_set,
                    get_transcript_id,
                )

                raw_schema_version = row_payload.get("schema_version", 1)
                try:
                    schema_version = int(raw_schema_version)
                except (TypeError, ValueError):
                    schema_version = 1

                _written, warning = write_row_outputs(
                    base_dir=Path(group_output_service.base_dir),
                    agg_id=entry.agg_id,
                    session_rows=session_rows,
                    speaker_rows=speaker_rows,
                    metrics_spec=metrics_spec,
                    content_rows=content_rows,
                    content_rows_name=content_rows_name,
                    bundle=True,
                    drop_csv_keys=drop_csv_keys,
                    extra_tables=extra_tables,
                    schema_version=schema_version,
                )

                if warning:
                    aggregation_warnings.append(warning)

                    continue

                chart_outcome = {
                    "session_rows": session_rows,
                    "speaker_rows": speaker_rows,
                    "metrics_spec": metrics_spec,
                    "content_rows": content_rows,
                    "content_rows_name": content_rows_name,
                }

                merge_optional_chart_outcome_keys(chart_outcome, outcome)

                try:
                    chart_result = run_group_aggregate_charts(
                        agg_id=entry.agg_id,
                        group_run_root=Path(group_output_service.base_dir),
                        group_run_id=group_run_id,
                        outcome=chart_outcome,
                        transcript_set=transcript_set,
                        group_uuid=group_uuid,
                        per_transcript_results=per_transcript_results,
                        canonical_speaker_map=canonical_speaker_map,
                    )

                    aggregation_warnings.extend(chart_result.warnings)

                except Exception as exc:
                    logger.warning(
                        "Group chart runner dispatch failed for %s: %s",
                        entry.agg_id,
                        exc,
                        exc_info=True,
                    )
                    aggregation_warnings.append(
                        build_warning(
                            code="GROUP_CHART_FAILED",
                            message=f"Group chart runner dispatch failed: {exc}",
                            aggregation_key=entry.agg_id,
                        )
                    )

                stored = dict(outcome)

                stored["output_type"] = "rows"

                aggregations[entry.agg_id] = stored

                completed.add(entry.agg_id)

        def _publish_manifest_only() -> None:
            write_output_manifest(
                run_dir=run_dir,
                run_id=group_run_id,
                transcript_key=group_uuid,
                modules_enabled=selected_modules,
            )

        # Aggregation/charts first; then one run-finalization lock owns
        # chart-descriptions → group synthesis → single manifest write.
        from transcriptx.core.analysis.chart_descriptions.coordinator import (
            run_finalization_coordinator,
        )
        from transcriptx.core.analysis.chart_descriptions.lock import (
            RunFinalizationLockTimeout,
            run_finalization_lock,
        )

        _run_aggregation_loop()
        try:
            with run_finalization_lock(run_dir):
                fin = run_finalization_coordinator(
                    run_dir=run_dir,
                    run_id=group_run_id,
                    transcript_key=group_uuid,
                    selected_modules=list(selected_modules),
                    modules_enabled=list(selected_modules),
                    config=group_config,
                    run_kind="group",
                    run_group_synthesis=True,
                    completed_agg_ids=completed,
                    aggregation_warnings=aggregation_warnings,
                    already_holding_lock=True,
                )
                synthesis_meta = dict(fin.synthesis_meta or {})
                aggregation_warnings.extend(fin.warnings or [])
        except RunFinalizationLockTimeout as exc:
            logger.warning(
                "run-finalization lock timeout during group finalize: %s", exc
            )
            aggregation_warnings.append(
                build_warning(
                    code="RUN_FINALIZATION_LOCK_TIMEOUT",
                    message=str(exc),
                    aggregation_key="run_finalization",
                )
            )
            synthesis_meta = {
                "attempt_status": "lock_timeout",
                "published": False,
                "error_code": "RUN_FINALIZATION_LOCK_TIMEOUT",
            }
            _publish_manifest_only()

        aggregation_warnings.sort(
            key=lambda w: (w.get("aggregation_key", ""), w.get("code", ""))
        )
        warnings_path = run_dir / "aggregation_warnings.json"
        save_json(aggregation_warnings, str(warnings_path))

        summary_text = (
            f"Group key: {transcript_set.key}\n"
            f"Transcripts: {len(per_transcript_results)}\n"
            f"Run ID: {group_run_id}\n"
        )
        group_output_service.save_summary(summary_text)
        group_output_service.write_group_manifest(
            group_id=group_uuid,
            group_key=group_key or transcript_set.key,
            transcript_file_uuids=member_uuids,
            transcript_paths=resolved_paths,
            run_id=group_run_id,
        )
        perf_warning = _commit_group_run_results_and_performance(
            run_dir=run_dir,
            group_run_id=group_run_id,
            group_uuid=group_uuid,
            selected_modules=selected_modules,
            per_transcript_results=per_transcript_results,
            group_errors=group_errors,
            aggregation_disabled=False,
            performance_recorder=performance_recorder,
            module_results=(
                {"group_llm_synthesis": synthesis_meta} if synthesis_meta else None
            ),
            write_manifest=False,
        )

        chart_failure_count = sum(
            1
            for w in aggregation_warnings
            if isinstance(w, dict) and w.get("code") == "GROUP_CHART_FAILED"
        )

        phase_meta = {
            "group_phase_terminal_failure": False,
            "aggregation_warning_count": len(aggregation_warnings),
            "chart_failure_count": chart_failure_count,
            "terminal_errors": list(group_errors),
        }
        if perf_warning:
            phase_meta["performance_sidecar_warning"] = perf_warning

        return {
            "status": "completed",
            "group_key": transcript_set.key,
            "group_uuid": group_uuid,
            "group_run_id": group_run_id,
            "group_output_dir": str(group_output_service.base_dir),
            "transcript_set": transcript_set.to_dict(),
            "transcripts": [result.to_dict() for result in per_transcript_results],
            "errors": group_errors,
            "aggregations": aggregations,
            "canonical_speaker_map": {
                "transcript_to_speakers": canonical_speaker_map.transcript_to_speakers,
                "canonical_to_display": canonical_speaker_map.canonical_to_display,
            },
            "meta": {
                "warnings_count": len(aggregation_warnings),
            },
            "aggregation_warnings": aggregation_warnings,
            "group_llm_synthesis": synthesis_meta,
            "group_phase_metadata": phase_meta,
        }

    finally:
        _group_run_lock.release()
