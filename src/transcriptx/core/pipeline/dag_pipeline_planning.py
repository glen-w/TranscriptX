"""
Planning-only DAG helpers: pre-run review (what will run vs skip) without execution.

Separated from execution so lifecycle/review can be tested without running modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.pipeline.pipeline_context import PipelineContext
from transcriptx.core.pipeline.dag_pipeline_run import gating_named_speaker_count


def compute_review_before_run_for_pipeline(
    pipeline: Any,
    transcript_path: str,
    selected_modules: List[str],
    output_dir: str,
    requirements_resolver: Optional[Any] = None,
    speaker_options: Optional[Any] = None,
    transcript_key: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute review data (what will run vs be skipped) without executing.

    ``pipeline`` must provide ``finalize``, ``preflight_check``, ``resolve_dependencies``,
    ``nodes``, and ``logger`` like ``DAGPipeline``.
    """
    from transcriptx.core.pipeline.run_options import SpeakerRunOptions

    speaker_options = speaker_options or SpeakerRunOptions()
    transcript_name = Path(transcript_path).name
    modules_will_run: List[str] = []
    modules_skipped: List[Dict[str, str]] = []

    if not pipeline._finalized:
        try:
            pipeline.finalize()
        except ValueError:
            pass

    preflight = pipeline.preflight_check(selected_modules)
    try:
        execution_order = pipeline.resolve_dependencies(selected_modules)
    except ValueError:
        return {
            "transcript_name": transcript_name,
            "output_dir": output_dir,
            "modules_will_run": [],
            "modules_skipped": [
                {"module": "?", "reason": "dependency resolution failed"}
            ],
        }

    preflight_skipped: Dict[str, str] = {}
    for name in preflight.get("skipped_modules", []):
        preflight_skipped.setdefault(name, "not in registry")
    for name in preflight.get("missing_dependencies", []):
        preflight_skipped.setdefault(name, "missing optional dependency")

    context = None
    named_speaker_count: Optional[int] = None
    try:
        context = PipelineContext(
            transcript_path,
            include_unidentified_speakers=speaker_options.include_unidentified,
            anonymise_speakers=speaker_options.anonymise,
            batch_mode=True,
            output_dir=output_dir,
            transcript_key=transcript_key,
            run_id=run_id,
        )
        if context.validate():
            named_speaker_count = gating_named_speaker_count(transcript_path, context)
    except Exception:
        named_speaker_count = None
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass

    for module_name in execution_order:
        if module_name in preflight_skipped:
            modules_skipped.append(
                {
                    "module": module_name,
                    "reason": preflight_skipped[module_name],
                }
            )
            continue
        if module_name not in pipeline.nodes:
            modules_skipped.append(
                {
                    "module": module_name,
                    "reason": "not in registry",
                }
            )
            continue
        node = pipeline.nodes[module_name]
        if requirements_resolver:
            should_skip, reasons = requirements_resolver.should_skip(node.requirements)
            if should_skip:
                modules_skipped.append(
                    {
                        "module": module_name,
                        "reason": (
                            "; ".join(reasons) if reasons else "requirements not met"
                        ),
                    }
                )
                continue
        if named_speaker_count is not None:
            try:
                from transcriptx.core.pipeline.module_registry import (
                    effective_min_named_speakers,
                    get_module_info,
                )

                module_info = get_module_info(module_name)
                if module_info:
                    min_required = effective_min_named_speakers(module_info)
                    if named_speaker_count < min_required:
                        modules_skipped.append(
                            {
                                "module": module_name,
                                "reason": f"requires at least {min_required} named speakers",
                            }
                        )
                        continue
            except Exception:
                pass
        modules_will_run.append(module_name)

    return {
        "transcript_name": transcript_name,
        "output_dir": output_dir,
        "modules_will_run": modules_will_run,
        "modules_skipped": modules_skipped,
    }
