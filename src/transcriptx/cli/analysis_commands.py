"""
Non-interactive analysis CLI commands.
"""

from __future__ import annotations

from typing import List, Optional

import typer

app = typer.Typer(name="analysis", help="Analysis commands", no_args_is_help=True)


@app.command("run")
def run(
    transcript: str = typer.Argument(..., help="Path to transcript JSON"),
    modules: Optional[str] = typer.Option(
        None, "--modules", "-m", help="Comma-separated module names"
    ),
) -> None:
    """Deprecated alias for `transcriptx analyze`."""
    from transcriptx.core import run_analysis_pipeline, get_default_modules

    typer.echo(
        "⚠️ 'transcriptx analysis run' is deprecated. Use 'transcriptx analyze' instead."
    )
    selected_modules: List[str]
    if modules:
        selected_modules = [m.strip() for m in modules.split(",") if m.strip()]
    else:
        selected_modules = get_default_modules()
    run_analysis_pipeline(
        target=transcript,
        selected_modules=selected_modules,
        persist=False,
    )
