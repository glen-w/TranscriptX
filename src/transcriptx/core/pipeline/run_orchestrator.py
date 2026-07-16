"""Orchestrate prepare → plan → execute → persist for a run."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.domain.canonical_transcript import CanonicalTranscript
from transcriptx.core.pipeline.contracts import (
    ErrorKind,
    PersistenceOutcome,
    RunRequest,
    RunResult,
    RunStatus,
)
from transcriptx.core.pipeline.dag_pipeline_errors import PipelineSetupError
from transcriptx.core.pipeline.dag_pipeline_factory import create_dag_pipeline
from transcriptx.core.pipeline.run_options import SpeakerRunOptions
from transcriptx.core.pipeline.run_outcome import (
    combine_status as _combine_status,
    emit_terminal_event_best_effort,
)
from transcriptx.core.pipeline.run_phase_dtos import (
    ExecutedRun,
    PlannedRun,
    PreparedTranscript,
    PreparedWorkspace,
)
from transcriptx.core.pipeline.requirements_resolver import ModuleRequirementsResolver
from transcriptx.core.pipeline.run_bootstrap import RunBootstrapService
from transcriptx.core.pipeline.run_configurator import RunConfigurator
from transcriptx.core.pipeline.run_persistence import PersistenceLayer
from transcriptx.core.pipeline.run_presenter import PipelineRunPresenter
from transcriptx.core.pipeline.run_workspace import RunWorkspaceService
from transcriptx.core.pipeline.dag_pipeline_run import build_execute_pipeline_context
from transcriptx.core.pipeline.adapters.file_execution_plan_store import (
    FileExecutionPlanStore,
)
from transcriptx.core.viz.charts import require_plotly
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.run_report import RunReport

logger = get_logger()


@dataclass
class _RunComposerState:
    persistence_outcomes: List[PersistenceOutcome] = field(default_factory=list)
    termination_reason: Optional[str] = None
    execution_status: RunStatus = "succeeded"
    summary: Dict[str, Any] = field(default_factory=dict)
    dag_results: Dict[str, Any] = field(default_factory=dict)
    prepared_transcript: Optional[PreparedTranscript] = None
    prepared_workspace: Optional[PreparedWorkspace] = None
    planned: Optional[PlannedRun] = None
    executed: Optional[ExecutedRun] = None
    context: Optional[Any] = None
    persisted_main: bool = False
    terminal_event_attempted: bool = False


class RunOrchestrator:
    def __init__(self) -> None:
        self.bootstrap = RunBootstrapService()
        self.workspace = RunWorkspaceService()
        self.configurator = RunConfigurator()
        self.persistence = PersistenceLayer()
        self.presenter = PipelineRunPresenter()
        self.execution_plan_store = FileExecutionPlanStore()

    def _build_context(
        self,
        *,
        transcript_path: str,
        speaker_options: Any,
        output_dir: str,
        transcript_key: Optional[str],
        run_id: Optional[str],
    ):
        return build_execute_pipeline_context(
            logger,
            transcript_path=transcript_path,
            speaker_options=speaker_options,
            output_dir=output_dir,
            transcript_key=transcript_key,
            run_id=run_id,
        )

    def _emit_terminal_event_best_effort(
        self,
        *,
        on_event: Optional[Any],
        event: str,
        message: str,
        error: Optional[str] = None,
    ) -> None:
        emit_terminal_event_best_effort(
            on_event=on_event,
            event=event,
            message=message,
            error=error,
        )

    def _prepare_transcript(
        self, transcript_path: str, request: RunRequest
    ) -> PreparedTranscript:
        segments = self.bootstrap.load_segments(transcript_path)
        canonical = CanonicalTranscript.from_segments(segments)
        transcript_identity = (
            request.transcript_identity
            or self.bootstrap.compute_identity(transcript_path, segments)
        )
        transcript_key = transcript_identity.transcript_identity_hash
        run_id = (
            request.run_id_override
            if request.run_id_override
            else f"{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 100000000:08d}"
        )

        self.bootstrap.validate_managed(transcript_path)
        run_identity = self.bootstrap.register(
            transcript_path=transcript_path,
            transcript_key=transcript_key,
            run_id=run_id,
        )
        return PreparedTranscript(
            transcript_path=transcript_path,
            canonical=canonical,
            transcript_identity=transcript_identity,
            transcript_key=transcript_key,
            run_id=run_identity.run_id,
            source_basename=run_identity.source_basename,
            slug=run_identity.slug,
        )

    def _prepare_workspace(
        self, prepared_transcript: PreparedTranscript, request: RunRequest
    ) -> PreparedWorkspace:
        workspace = self.workspace.create(
            transcript_path=prepared_transcript.transcript_path,
            slug=prepared_transcript.slug,
            run_id=prepared_transcript.run_id,
            output_dir_override=request.output_dir_override,
        )
        with self.workspace.scoped_transcript_output_dir(
            prepared_transcript.transcript_path, workspace.output_dir
        ):
            config_resolution = self.configurator.resolve_and_apply(
                Path(workspace.output_dir)
            )
            config = config_resolution.config
            if getattr(config.output, "dynamic_charts", "auto") == "on":
                require_plotly()
        return PreparedWorkspace(
            output_dir=workspace.output_dir,
            config=config,
            config_snapshot=config_resolution.snapshot,
            draft_override_used=bool(config_resolution.draft_override),
        )

    def _build_execution_plan(
        self,
        prepared_transcript: PreparedTranscript,
        prepared_workspace: PreparedWorkspace,
        request: RunRequest,
        speaker_options: Any,
    ) -> PlannedRun:
        run_report = RunReport(
            transcript_hash=prepared_transcript.transcript_key,
            run_id=prepared_transcript.run_id,
        )
        requirements_resolver = ModuleRequirementsResolver(
            capabilities=prepared_transcript.canonical.capabilities,
            has_db=False,
        )
        dag_pipeline = create_dag_pipeline()
        plan = dag_pipeline.get_execution_plan(request.selected_modules)
        execution_plan_outcome = self.execution_plan_store.save(
            plan, prepared_workspace.output_dir
        )
        review = dag_pipeline.compute_review_before_run(
            transcript_path=prepared_transcript.transcript_path,
            selected_modules=request.selected_modules,
            output_dir=prepared_workspace.output_dir,
            requirements_resolver=requirements_resolver,
            speaker_options=speaker_options,
            transcript_key=prepared_transcript.transcript_key,
            run_id=prepared_transcript.run_id,
        )
        self.presenter.show_pre_run_review(review)
        return PlannedRun(
            dag_pipeline=dag_pipeline,
            plan=plan,
            requirements_resolver=requirements_resolver,
            review=review,
            run_report=run_report,
            execution_plan_outcome=execution_plan_outcome,
        )

    def _execution_status_from_results(self, dag_results: Dict[str, Any]) -> RunStatus:
        if dag_results.get("status") == "aborted":
            return "aborted"
        if dag_results.get("status") == "failed":
            return "failed"
        if dag_results.get("errors"):
            return "partial"
        return "succeeded"

    def _execute_plan(
        self,
        planned: PlannedRun,
        prepared_transcript: PreparedTranscript,
        prepared_workspace: PreparedWorkspace,
        request: RunRequest,
        speaker_options: Any,
        on_event: Optional[Any],
    ) -> ExecutedRun:
        resolved_speaker_options = speaker_options or SpeakerRunOptions()
        context = None
        try:
            context, named_speaker_count = self._build_context(
                transcript_path=prepared_transcript.transcript_path,
                speaker_options=resolved_speaker_options,
                output_dir=prepared_workspace.output_dir,
                transcript_key=prepared_transcript.transcript_key,
                run_id=prepared_transcript.run_id,
            )
            dag_results = planned.dag_pipeline.execute_pipeline(
                transcript_path=prepared_transcript.transcript_path,
                selected_modules=request.selected_modules,
                speaker_options=resolved_speaker_options,
                output_dir=prepared_workspace.output_dir,
                transcript_key=prepared_transcript.transcript_key,
                run_id=prepared_transcript.run_id,
                run_report=planned.run_report,
                requirements_resolver=planned.requirements_resolver,
                on_event=on_event,
                context=context,
                named_speaker_count=named_speaker_count,
                execution_plan=planned.plan,
            )
        except BaseException:
            if context is not None:
                try:
                    context.close()
                except Exception:
                    logger.exception(
                        "PipelineContext.close failed during execution error"
                    )
            raise

        execution_status = self._execution_status_from_results(dag_results)
        summary = self.presenter.build_summary(
            transcript_path=prepared_transcript.transcript_path,
            selected_modules=request.selected_modules,
            modules_run=dag_results.get("modules_run", []),
            errors=dag_results.get("errors", []),
            skipped_modules=dag_results.get("skipped_modules", []),
        )
        self.presenter.show_post_run_summary(
            summary, prepared_workspace.output_dir, dag_results
        )
        return ExecutedRun(
            dag_results=dag_results,
            context=context,
            named_speaker_count=named_speaker_count,
            execution_status=execution_status,
            summary=summary,
        )

    def _persist_success_outcome(
        self,
        executed: ExecutedRun,
        planned: PlannedRun,
        prepared_transcript: PreparedTranscript,
        prepared_workspace: PreparedWorkspace,
        request: RunRequest,
    ) -> List[PersistenceOutcome]:
        outcomes: List[PersistenceOutcome] = []
        outcomes.append(
            self.persistence.persist_run_outputs(
                output_dir=prepared_workspace.output_dir,
                run_id=prepared_transcript.run_id,
                transcript_key=prepared_transcript.transcript_key,
                selected_modules=request.selected_modules,
                results=executed.dag_results,
            )
        )
        outcomes.append(
            self.persistence.persist_processing_state(
                prepared_transcript.transcript_path,
                {
                    **executed.dag_results,
                    "transcript_key": prepared_transcript.transcript_key,
                    "run_id": prepared_transcript.run_id,
                    "output_dir": prepared_workspace.output_dir,
                },
            )
        )
        planned.run_report.errors.extend(executed.dag_results.get("errors", []))
        outcomes.append(
            self.persistence.persist_run_report(
                planned.run_report, prepared_workspace.output_dir
            )
        )
        outcomes.append(
            self.persistence.persist_manifest(
                output_dir=prepared_workspace.output_dir,
                selected_modules=request.selected_modules,
                transcript_path=prepared_transcript.transcript_path,
                source_basename=prepared_transcript.source_basename,
                run_id=prepared_transcript.run_id,
                transcript_key=prepared_transcript.transcript_key,
                transcript_identity_hash=prepared_transcript.transcript_identity.transcript_identity_hash,
                transcript_content_hash_full=prepared_transcript.transcript_identity.transcript_content_hash_full,
                transcript_file_hash=prepared_transcript.transcript_identity.transcript_file_hash,
                canonical_schema_version=prepared_transcript.canonical.schema_version,
                config_snapshot=prepared_workspace.config_snapshot,
                draft_override_used=prepared_workspace.draft_override_used,
            )
        )
        self.configurator.clear_draft_override(
            should_clear=prepared_workspace.draft_override_used
            and all(
                outcome.success for outcome in outcomes if outcome.name == "manifest"
            )
        )
        return outcomes

    def _persist_failure_outcome(
        self,
        execution_status: RunStatus,
        prepared_transcript: Optional[PreparedTranscript],
        prepared_workspace: Optional[PreparedWorkspace],
        request: RunRequest,
        dag_results: Dict[str, Any],
        persisted_main: bool,
    ) -> List[PersistenceOutcome]:
        if (
            execution_status not in {"failed", "aborted"}
            or prepared_workspace is None
            or persisted_main
        ):
            return []
        return [
            self.persistence.persist_run_outputs(
                output_dir=prepared_workspace.output_dir,
                run_id=(
                    prepared_transcript.run_id
                    if prepared_transcript is not None
                    else "unknown_run"
                ),
                transcript_key=(
                    prepared_transcript.transcript_key
                    if prepared_transcript is not None
                    else "unknown_transcript"
                ),
                selected_modules=request.selected_modules,
                results=dag_results
                or {
                    "errors": ["pipeline_failed_before_execution"],
                    "modules_run": [],
                    "execution_order": [],
                    "cache_hits": [],
                    "module_results": {},
                    "skipped_modules": [],
                },
            )
        ]

    def _build_result(
        self,
        *,
        transcript_path: str,
        request: RunRequest,
        prepared_transcript: Optional[PreparedTranscript],
        prepared_workspace: Optional[PreparedWorkspace],
        executed: Optional[ExecutedRun],
        dag_results: Dict[str, Any],
        summary: Dict[str, Any],
        persistence_outcomes: List[PersistenceOutcome],
        execution_status: RunStatus,
        termination_reason: Optional[str],
        duration: float,
    ) -> RunResult:
        final_status = _combine_status(execution_status, persistence_outcomes)
        if execution_status == "aborted" and any(
            (not outcome.success) and outcome.severity == "required"
            for outcome in persistence_outcomes
        ):
            termination_reason = termination_reason or "cancellation"
        return RunResult(
            status=final_status,
            execution_status=execution_status,
            final_status=final_status,
            transcript_path=transcript_path,
            transcript_key=(
                prepared_transcript.transcript_key
                if prepared_transcript is not None
                else ""
            ),
            run_id=(
                prepared_transcript.run_id if prepared_transcript is not None else ""
            ),
            output_dir=(
                prepared_workspace.output_dir if prepared_workspace is not None else ""
            ),
            selected_modules=list(request.selected_modules),
            modules_run=list(dag_results.get("modules_run", [])),
            skipped_modules=list(dag_results.get("skipped_modules", [])),
            errors=list(dag_results.get("errors", [])),
            module_results=dict(dag_results.get("module_results", {})),
            execution_order=list(dag_results.get("execution_order", [])),
            cache_hits=list(dag_results.get("cache_hits", [])),
            duration=duration,
            summary=executed.summary if executed is not None else summary,
            persistence_outcomes=persistence_outcomes,
            termination_reason=termination_reason,
        )

    def _run_success_path(
        self,
        state: _RunComposerState,
        *,
        transcript_path: str,
        request: RunRequest,
        speaker_options: Any,
        on_event: Optional[Any],
    ) -> None:
        state.prepared_transcript = self._prepare_transcript(transcript_path, request)
        state.prepared_workspace = self._prepare_workspace(
            state.prepared_transcript, request
        )
        from transcriptx.core.utils.run_writer_locks import per_run_lock

        # Hold per-run lock for the full write lifetime (artifacts + manifests).
        with per_run_lock(state.prepared_workspace.output_dir):
            with self.workspace.scoped_transcript_output_dir(
                transcript_path, state.prepared_workspace.output_dir
            ):
                state.planned = self._build_execution_plan(
                    state.prepared_transcript,
                    state.prepared_workspace,
                    request,
                    speaker_options,
                )
                state.persistence_outcomes.append(state.planned.execution_plan_outcome)
                state.executed = self._execute_plan(
                    state.planned,
                    state.prepared_transcript,
                    state.prepared_workspace,
                    request,
                    speaker_options,
                    on_event,
                )
                state.context = state.executed.context
                state.dag_results = state.executed.dag_results
                state.summary = state.executed.summary
                state.execution_status = state.executed.execution_status
                state.persistence_outcomes.extend(
                    self._persist_success_outcome(
                        state.executed,
                        state.planned,
                        state.prepared_transcript,
                        state.prepared_workspace,
                        request,
                    )
                )
                state.persisted_main = True

    def _handle_keyboard_interrupt(
        self, state: _RunComposerState, *, on_event: Optional[Any]
    ) -> None:
        state.execution_status = "aborted"
        state.termination_reason = "cancellation"
        if not state.terminal_event_attempted:
            self._emit_terminal_event_best_effort(
                on_event=on_event,
                event="run_failed",
                message="Pipeline cancelled",
                error="cancellation",
            )

    def _handle_setup_error(
        self,
        state: _RunComposerState,
        error: PipelineSetupError,
        *,
        on_event: Optional[Any],
    ) -> None:
        logger.error("Pipeline setup error: %s", error)
        state.execution_status = "failed"
        state.dag_results.setdefault("errors", []).append(str(error))
        if not state.terminal_event_attempted:
            self._emit_terminal_event_best_effort(
                on_event=on_event,
                event="run_failed",
                message="Pipeline failed during setup",
                error=str(error),
            )

    def _handle_unexpected_error(
        self, state: _RunComposerState, error: Exception, *, on_event: Optional[Any]
    ) -> None:
        logger.exception("Pipeline orchestration failed")
        state.execution_status = "failed"
        state.dag_results.setdefault("errors", []).append(str(error))
        if not state.terminal_event_attempted:
            self._emit_terminal_event_best_effort(
                on_event=on_event,
                event="run_failed",
                message="Pipeline orchestration failed",
                error=str(error),
            )
        if state.prepared_workspace is not None:
            state.persistence_outcomes.append(
                PersistenceOutcome(
                    name="run_result_envelope",
                    success=False,
                    severity="required",
                    error_kind=ErrorKind.PERSISTENCE,
                    error_message=str(error),
                )
            )

    def _finalize_state(self, state: _RunComposerState, request: RunRequest) -> None:
        state.persistence_outcomes.extend(
            self._persist_failure_outcome(
                state.execution_status,
                state.prepared_transcript,
                state.prepared_workspace,
                request,
                state.dag_results,
                state.persisted_main,
            )
        )
        if state.context is not None:
            try:
                state.context.close()
            except Exception as error:
                state.dag_results.setdefault("errors", []).append(
                    f"PipelineContext.close failed: {error}"
                )

    def run(
        self,
        *,
        transcript_path: str,
        request: RunRequest,
        speaker_options: Any = None,
        on_event: Optional[Any] = None,
    ) -> RunResult:
        start_time = time.time()
        state = _RunComposerState()

        def on_event_wrapped(event: Dict[str, Any]) -> None:
            if event.get("event") in {"run_completed", "run_failed"}:
                state.terminal_event_attempted = True
            if on_event is not None:
                on_event(event)

        try:
            self._run_success_path(
                state,
                transcript_path=transcript_path,
                request=request,
                speaker_options=speaker_options,
                on_event=on_event_wrapped,
            )
        except KeyboardInterrupt:
            self._handle_keyboard_interrupt(state, on_event=on_event)
        except PipelineSetupError as error:
            self._handle_setup_error(state, error, on_event=on_event)
        except Exception as error:
            self._handle_unexpected_error(state, error, on_event=on_event)
        finally:
            self._finalize_state(state, request)
        return self._build_result(
            transcript_path=transcript_path,
            request=request,
            prepared_transcript=state.prepared_transcript,
            prepared_workspace=state.prepared_workspace,
            executed=state.executed,
            dag_results=state.dag_results,
            summary=state.summary,
            persistence_outcomes=state.persistence_outcomes,
            execution_status=state.execution_status,
            termination_reason=state.termination_reason,
            duration=time.time() - start_time,
        )
