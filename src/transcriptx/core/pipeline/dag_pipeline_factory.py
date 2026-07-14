"""Factory helpers to construct and run DAG pipelines."""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.pipeline.dag_pipeline import DAGPipeline
from transcriptx.core.pipeline.dag_pipeline_run import (
    build_execute_pipeline_context,
    resolve_output_dir_for_run,
)
from transcriptx.core.pipeline.dag_registry import (
    build_dag_registry_from_module_registry,
)
from transcriptx.core.pipeline.run_options import SpeakerRunOptions


def create_dag_pipeline() -> DAGPipeline:
    return DAGPipeline(registry=build_dag_registry_from_module_registry())


def run_dag_pipeline(
    transcript_path: str,
    selected_modules: List[str],
    speaker_options: "SpeakerRunOptions | None" = None,
) -> Dict[str, Any]:
    dag = create_dag_pipeline()
    resolved_speaker_options = speaker_options or SpeakerRunOptions()
    context = None
    try:
        context, named_speaker_count = build_execute_pipeline_context(
            dag.logger,
            transcript_path=transcript_path,
            speaker_options=resolved_speaker_options,
            output_dir=resolve_output_dir_for_run(transcript_path, None),
            transcript_key=None,
            run_id=None,
        )
        return dag.execute_pipeline(
            transcript_path=transcript_path,
            selected_modules=selected_modules,
            speaker_options=resolved_speaker_options,
            context=context,
            named_speaker_count=named_speaker_count,
        )
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
