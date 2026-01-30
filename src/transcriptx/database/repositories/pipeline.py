"""
Repository classes for TranscriptX database operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


from transcriptx.core.utils.logger import get_logger
from ..models import PipelineRun, ModuleRun, ArtifactIndex, PerformanceSpan

logger = get_logger()


from .base import BaseRepository


class PipelineRunRepository(BaseRepository):
    """Repository for pipeline runs."""

    def create_pipeline_run(
        self,
        transcript_file_id: int,
        pipeline_version: Optional[str],
        pipeline_config_hash: Optional[str],
        pipeline_input_hash: Optional[str],
        cli_args_json: Optional[Dict[str, Any]] = None,
    ) -> PipelineRun:
        try:
            run = PipelineRun(
                transcript_file_id=transcript_file_id,
                pipeline_version=pipeline_version,
                pipeline_config_hash=pipeline_config_hash,
                pipeline_input_hash=pipeline_input_hash,
                cli_args_json=cli_args_json or {},
                status="in_progress",
            )
            self.session.add(run)
            self.session.flush()
            self.session.commit()
            return run
        except Exception as e:
            self._handle_error("create_pipeline_run", e)

    def update_status(self, pipeline_run_id: int, status: str) -> None:
        try:
            run = (
                self.session.query(PipelineRun)
                .filter(PipelineRun.id == pipeline_run_id)
                .first()
            )
            if not run:
                raise ValueError(f"PipelineRun {pipeline_run_id} not found")
            run.status = status
            self.session.flush()
            self.session.commit()
        except Exception as e:
            self._handle_error("update_status", e)

    def find_latest_by_input_hash(
        self, transcript_file_id: int, pipeline_input_hash: str
    ) -> Optional[PipelineRun]:
        try:
            return (
                self.session.query(PipelineRun)
                .filter(
                    PipelineRun.transcript_file_id == transcript_file_id,
                    PipelineRun.pipeline_input_hash == pipeline_input_hash,
                    PipelineRun.status == "completed",
                )
                .order_by(PipelineRun.created_at.desc())
                .first()
            )
        except Exception as e:
            self._handle_error("find_latest_by_input_hash", e)


class ModuleRunRepository(BaseRepository):
    """Repository for module runs."""

    def find_cacheable_run(
        self,
        transcript_file_id: int,
        module_name: str,
        module_version: str,
        module_input_hash: str,
    ) -> Optional[ModuleRun]:
        try:
            return (
                self.session.query(ModuleRun)
                .filter(
                    ModuleRun.transcript_file_id == transcript_file_id,
                    ModuleRun.module_name == module_name,
                    ModuleRun.module_version == module_version,
                    ModuleRun.module_input_hash == module_input_hash,
                    ModuleRun.status == "completed",
                    ModuleRun.is_cacheable == True,
                    ModuleRun.superseded_at.is_(None),
                )
                .order_by(ModuleRun.created_at.desc())
                .first()
            )
        except Exception as e:
            self._handle_error("find_cacheable_run", e)

    def create_module_run(
        self,
        pipeline_run_id: int,
        transcript_file_id: int,
        module_name: str,
        module_version: str,
        module_config_hash: str,
        module_input_hash: str,
        replaces_module_run_id: Optional[int] = None,
        is_cacheable: bool = True,
        cache_reason: Optional[str] = None,
    ) -> ModuleRun:
        try:
            run = ModuleRun(
                pipeline_run_id=pipeline_run_id,
                transcript_file_id=transcript_file_id,
                module_name=module_name,
                module_version=module_version,
                module_config_hash=module_config_hash,
                module_input_hash=module_input_hash,
                status="in_progress",
                is_cacheable=is_cacheable,
                cache_reason=cache_reason,
                replaces_module_run_id=replaces_module_run_id,
            )
            self.session.add(run)
            self.session.flush()
            self.session.commit()
            return run
        except Exception as e:
            self._handle_error("create_module_run", e)

    def update_completion(
        self,
        module_run_id: int,
        status: str,
        duration_seconds: Optional[float] = None,
        output_hash: Optional[str] = None,
        is_cacheable: Optional[bool] = None,
    ) -> None:
        try:
            run = (
                self.session.query(ModuleRun)
                .filter(ModuleRun.id == module_run_id)
                .first()
            )
            if not run:
                raise ValueError(f"ModuleRun {module_run_id} not found")
            run.status = status
            if duration_seconds is not None:
                run.duration_seconds = duration_seconds
            if output_hash:
                run.output_hash = output_hash
            if is_cacheable is not None:
                run.is_cacheable = is_cacheable
            self.session.flush()
            self.session.commit()
        except Exception as e:
            self._handle_error("update_completion", e)

    def mark_superseded(self, module_run_id: int, superseded_at: datetime) -> None:
        try:
            run = (
                self.session.query(ModuleRun)
                .filter(ModuleRun.id == module_run_id)
                .first()
            )
            if not run:
                raise ValueError(f"ModuleRun {module_run_id} not found")
            run.is_cacheable = False
            run.superseded_at = superseded_at
            self.session.flush()
            self.session.commit()
        except Exception as e:
            self._handle_error("mark_superseded", e)


class PerformanceSpanRepository(BaseRepository):
    """Repository for span-shaped performance logs."""

    def start_span(
        self,
        trace_id: str,
        span_id: str,
        name: str,
        start_time: datetime,
        parent_span_id: Optional[str] = None,
        kind: Optional[str] = None,
        attributes_json: Optional[Dict[str, Any]] = None,
        pipeline_run_id: Optional[int] = None,
        module_run_id: Optional[int] = None,
        transcript_file_id: Optional[int] = None,
    ) -> PerformanceSpan:
        try:
            span = PerformanceSpan(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                name=name,
                kind=kind,
                status_code="OK",
                start_time=start_time,
                attributes_json=attributes_json or {},
                pipeline_run_id=pipeline_run_id,
                module_run_id=module_run_id,
                transcript_file_id=transcript_file_id,
            )
            self.session.add(span)
            self.session.flush()
            self.session.commit()
            return span
        except Exception as e:
            self.session.rollback()
            self._handle_error("start_span", e)

    def end_span_ok(
        self,
        span_id: str,
        end_time: datetime,
        attributes_patch: Optional[Dict[str, Any]] = None,
        events_patch: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Mark a span as successfully completed.

        This method updates the span with end_time, duration, and any additional
        attributes/events. If this method fails, the span will remain incomplete,
        which may indicate a database issue or the span was never created.

        Args:
            span_id: The span ID to update
            end_time: When the span completed
            attributes_patch: Additional attributes to merge
            events_patch: Additional events to append

        Raises:
            ValueError: If span not found
            Exception: For database errors (logged and re-raised)
        """
        try:
            span = (
                self.session.query(PerformanceSpan)
                .filter(PerformanceSpan.span_id == span_id)
                .first()
            )
            if not span:
                error_msg = f"PerformanceSpan {span_id} not found - span may have been deleted or never created"
                logger.warning(error_msg)
                raise ValueError(error_msg)

            # Calculate duration
            if span.start_time:
                span.duration_ms = (end_time - span.start_time).total_seconds() * 1000.0
            else:
                logger.warning(
                    f"Span {span_id} has no start_time, cannot calculate duration"
                )
                span.duration_ms = None

            span.end_time = end_time
            span.status_code = "OK"

            # Merge attributes
            if attributes_patch:
                span.attributes_json = {
                    **(span.attributes_json or {}),
                    **attributes_patch,
                }

            # Append events
            if events_patch:
                span.events_json = (span.events_json or []) + events_patch

            self.session.flush()
            self.session.commit()
            logger.debug(
                f"Successfully completed span {span_id} (duration: {span.duration_ms:.2f}ms)"
            )
        except ValueError:
            # Re-raise ValueError (span not found) without rollback since no DB changes were made
            raise
        except Exception as e:
            self.session.rollback()
            logger.error(
                f"Failed to complete span {span_id}: {type(e).__name__}: {e}. "
                f"Span will remain incomplete in database."
            )
            self._handle_error("end_span_ok", e)

    def end_span_error(
        self,
        span_id: str,
        end_time: datetime,
        exc: Optional[BaseException] = None,
        attributes_patch: Optional[Dict[str, Any]] = None,
        events_patch: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        try:
            span = (
                self.session.query(PerformanceSpan)
                .filter(PerformanceSpan.span_id == span_id)
                .first()
            )
            if not span:
                raise ValueError(f"PerformanceSpan {span_id} not found")
            span.end_time = end_time
            span.duration_ms = (end_time - span.start_time).total_seconds() * 1000.0
            span.status_code = "ERROR"
            if exc is not None:
                span.status_message = str(exc)
            if attributes_patch:
                span.attributes_json = {
                    **(span.attributes_json or {}),
                    **attributes_patch,
                }
            if events_patch:
                span.events_json = (span.events_json or []) + events_patch
            self.session.flush()
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            self._handle_error("end_span_error", e)

    def update_span_attributes(
        self,
        span_id: str,
        attributes_patch: Dict[str, Any],
    ) -> None:
        """
        Update span attributes while the span is still active.
        This allows metadata to be persisted immediately rather than waiting for span completion.

        Args:
            span_id: The span ID to update
            attributes_patch: Dictionary of attributes to merge into existing attributes

        Raises:
            ValueError: If span not found
            Exception: For database errors (logged and re-raised)
        """
        try:
            span = (
                self.session.query(PerformanceSpan)
                .filter(PerformanceSpan.span_id == span_id)
                .first()
            )
            if not span:
                error_msg = (
                    f"PerformanceSpan {span_id} not found - cannot update attributes"
                )
                logger.warning(error_msg)
                raise ValueError(error_msg)
            if attributes_patch:
                span.attributes_json = {
                    **(span.attributes_json or {}),
                    **attributes_patch,
                }
            self.session.flush()
            self.session.commit()
            logger.debug(
                f"Updated attributes for span {span_id}: {list(attributes_patch.keys())}"
            )
        except ValueError:
            # Re-raise ValueError (span not found) without rollback since no DB changes were made
            raise
        except Exception as e:
            self.session.rollback()
            logger.error(
                f"Failed to update attributes for span {span_id}: {type(e).__name__}: {e}"
            )
            self._handle_error("update_span_attributes", e)

    def query_spans(
        self,
        name: Optional[str] = None,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        status_code: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        pipeline_run_id: Optional[int] = None,
        module_run_id: Optional[int] = None,
        transcript_file_id: Optional[int] = None,
        attributes_filter: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> List[PerformanceSpan]:
        try:
            query = self.session.query(PerformanceSpan)

            if name:
                query = query.filter(PerformanceSpan.name == name)
            if trace_id:
                query = query.filter(PerformanceSpan.trace_id == trace_id)
            if span_id:
                query = query.filter(PerformanceSpan.span_id == span_id)
            if status_code:
                query = query.filter(PerformanceSpan.status_code == status_code)
            if start_date:
                query = query.filter(PerformanceSpan.start_time >= start_date)
            if end_date:
                query = query.filter(PerformanceSpan.start_time <= end_date)
            if pipeline_run_id is not None:
                query = query.filter(PerformanceSpan.pipeline_run_id == pipeline_run_id)
            if module_run_id is not None:
                query = query.filter(PerformanceSpan.module_run_id == module_run_id)
            if transcript_file_id is not None:
                query = query.filter(
                    PerformanceSpan.transcript_file_id == transcript_file_id
                )

            query = query.order_by(PerformanceSpan.start_time.desc())
            if limit:
                query = query.limit(limit)

            results = query.all()
            if not attributes_filter:
                return results

            filtered = []
            for span in results:
                attrs = span.attributes_json or {}
                if all(
                    attrs.get(key) == value for key, value in attributes_filter.items()
                ):
                    filtered.append(span)
            return filtered
        except Exception as e:
            self._handle_error("query_spans", e)

    def mark_stale_spans(
        self, cutoff_time: datetime, status_message: str = "abandoned/crashed"
    ) -> int:
        try:
            spans = (
                self.session.query(PerformanceSpan)
                .filter(
                    PerformanceSpan.end_time.is_(None),
                    PerformanceSpan.start_time < cutoff_time,
                )
                .all()
            )
            for span in spans:
                span.end_time = cutoff_time
                span.duration_ms = (
                    cutoff_time - span.start_time
                ).total_seconds() * 1000.0
                span.status_code = "ERROR"
                span.status_message = status_message
            if spans:
                self.session.flush()
                self.session.commit()
            return len(spans)
        except Exception as e:
            self.session.rollback()
            self._handle_error("mark_stale_spans", e)


class ArtifactIndexRepository(BaseRepository):
    """Repository for artifact registrations."""

    def create_artifact(
        self,
        module_run_id: int,
        transcript_file_id: int,
        artifact_key: str,
        relative_path: str,
        artifact_root: Optional[str],
        artifact_type: Optional[str],
        artifact_role: str,
        content_hash: Optional[str],
    ) -> ArtifactIndex:
        try:
            artifact = ArtifactIndex(
                module_run_id=module_run_id,
                transcript_file_id=transcript_file_id,
                artifact_key=artifact_key,
                relative_path=relative_path,
                artifact_root=artifact_root,
                artifact_type=artifact_type,
                artifact_role=artifact_role,
                content_hash=content_hash,
            )
            self.session.add(artifact)
            self.session.flush()
            return artifact
        except Exception as e:
            self._handle_error("create_artifact", e)

    def get_primary_artifacts(self, module_run_id: int) -> List[ArtifactIndex]:
        try:
            return (
                self.session.query(ArtifactIndex)
                .filter(
                    ArtifactIndex.module_run_id == module_run_id,
                    ArtifactIndex.artifact_role == "primary",
                )
                .all()
            )
        except Exception as e:
            self._handle_error("get_primary_artifacts", e)
