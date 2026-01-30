"""
Diagnostics and audit CLI commands.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.run_manifest import (
    get_dependency_versions,
    load_run_manifest,
    verify_run_manifest,
)
from transcriptx.core.utils.path_utils import get_transcript_dir

console = Console()

doctor_app = typer.Typer(
    name="doctor",
    help="Environment and configuration diagnostics",
    invoke_without_command=True,
    no_args_is_help=False,
)

audit_app = typer.Typer(
    name="audit",
    help="Audit a PipelineRun for integrity and reproducibility",
    invoke_without_command=True,
    no_args_is_help=False,
)


@doctor_app.callback()
def doctor(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON report"),
) -> None:
    """Run basic environment and configuration diagnostics."""
    config = get_config()
    report = {
        "config_snapshot_available": hasattr(config, "to_dict"),
        "dependency_versions": get_dependency_versions(),
    }
    if json_output:
        print(json.dumps(report, indent=2))
        return
    summary = (
        f"Config snapshot: {'yes' if report['config_snapshot_available'] else 'no'}\n"
        f"Dependencies tracked: {len(report['dependency_versions'])}"
    )
    console.print(Panel(summary, title="TranscriptX Doctor"))


@audit_app.callback()
def audit(
    run_id: int = typer.Argument(..., help="PipelineRun ID to audit"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON report"),
) -> None:
    """Audit a PipelineRun for artifact integrity and manifest coverage."""
    from transcriptx.database.database import get_session
    from transcriptx.database.models import PipelineRun, ModuleRun, TranscriptFile
    from transcriptx.database.artifact_validation import ArtifactValidationService

    session = get_session()
    pipeline_run = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not pipeline_run:
        session.close()
        raise typer.Exit(code=1)

    transcript = (
        session.query(TranscriptFile)
        .filter(TranscriptFile.id == pipeline_run.transcript_file_id)
        .first()
    )
    transcript_path = transcript.file_path if transcript else None
    output_dir = get_transcript_dir(transcript_path) if transcript_path else None

    # Manifest validation
    manifest_path = None
    manifest_report = {"present": False, "valid": False, "errors": [], "warnings": []}
    if output_dir:
        manifest_path = f"{output_dir}/.transcriptx/manifest.json"
        try:
            manifest = load_run_manifest(Path(manifest_path))
            manifest_report["present"] = True
            verification = verify_run_manifest(manifest)
            manifest_report["valid"] = verification["valid"]
            manifest_report["errors"] = verification["errors"]
            manifest_report["warnings"] = verification["warnings"]
        except Exception as e:
            manifest_report["errors"] = [str(e)]

    # Artifact validation
    artifact_report = {"p0": [], "p1": [], "warnings": []}
    if transcript_path:
        validator = ArtifactValidationService()
        try:
            report = validator.validate(
                transcript_path, pipeline_run_id=run_id, strict=False
            )
            artifact_report = {
                "p0": report.p0_errors,
                "p1": report.p1_errors,
                "warnings": report.warnings,
            }
        finally:
            validator.close()

    module_runs = (
        session.query(ModuleRun).filter(ModuleRun.pipeline_run_id == run_id).all()
    )
    module_status = []
    for run in module_runs:
        error_info = {}
        if run.outputs_json and isinstance(run.outputs_json, dict):
            error_info = run.outputs_json.get("error") or {}
        module_status.append(
            {
                "module_name": run.module_name,
                "status": run.status,
                "has_error": bool(error_info),
                "has_traceback": bool(error_info.get("traceback_text")),
            }
        )

    audit_report = {
        "pipeline_run_id": run_id,
        "pipeline_status": pipeline_run.status,
        "transcript_path": transcript_path,
        "manifest_path": manifest_path,
        "manifest": manifest_report,
        "artifact_validation": artifact_report,
        "module_runs": module_status,
    }
    if json_output:
        print(json.dumps(audit_report, indent=2))
        session.close()
        return

    summary = (
        f"PipelineRun: {run_id} ({pipeline_run.status})\n"
        f"Manifest: {'ok' if manifest_report['present'] and manifest_report['valid'] else 'missing/invalid'}\n"
        f"Artifacts: P0={len(artifact_report['p0'])}, P1={len(artifact_report['p1'])}, W={len(artifact_report['warnings'])}"
    )
    console.print(Panel(summary, title="TranscriptX Audit"))
    session.close()
