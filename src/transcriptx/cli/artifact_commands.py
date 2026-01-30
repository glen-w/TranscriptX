"""
CLI commands for artifact validation.
"""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel


console = Console()
app = typer.Typer(
    name="artifacts", help="Artifact validation commands", no_args_is_help=True
)


@app.command("validate")
def validate_artifacts(
    transcript: str = typer.Option(
        ..., "--transcript", "-t", help="Transcript path, id, or content hash"
    ),
    pipeline_run: Optional[int] = typer.Option(
        None, "--pipeline-run", "-p", help="PipelineRun ID to scope validation"
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON report"),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as errors"),
) -> None:
    """Validate DB ↔ FS artifact integrity and provenance."""
    from transcriptx.database.artifact_validation import ArtifactValidationService

    service = ArtifactValidationService()
    try:
        report = service.validate(
            transcript, pipeline_run_id=pipeline_run, strict=strict
        )
    finally:
        service.close()

    if json_output:
        print(
            json.dumps(
                {
                    "p0_errors": report.p0_errors,
                    "p1_errors": report.p1_errors,
                    "warnings": report.warnings,
                    "checked_files": report.checked_files,
                    "checked_records": report.checked_records,
                },
                indent=2,
            )
        )
    else:
        summary = (
            f"P0: {len(report.p0_errors)} | P1: {len(report.p1_errors)} "
            f"| Warnings: {len(report.warnings)}\n"
            f"Checked records: {report.checked_records} | Files: {report.checked_files}"
        )
        console.print(Panel(summary, title="Artifact Validation"))
        for label, items in [
            ("P0 errors", report.p0_errors),
            ("P1 errors", report.p1_errors),
            ("Warnings", report.warnings),
        ]:
            if items:
                console.print(f"\n[bold]{label}:[/bold]")
                for item in items:
                    console.print(f" - {item}")

    raise typer.Exit(code=report.exit_code(strict=strict))
