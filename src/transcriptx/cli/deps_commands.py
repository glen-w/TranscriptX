"""
Dependency and extra-install CLI commands for TranscriptX.

Provides:
- deps status: show which extras are available/missing and current core_mode
- deps install: install transcriptx[full] or selected extras (voice, emotion, nlp, ...)
"""

import subprocess
import sys

import typer
from rich.console import Console
from rich.table import Table

from transcriptx.core.utils.config import get_config
from transcriptx.core.pipeline.module_registry import is_extra_available

console = Console()

# Extras we support for status/install (matches pyproject optional-dependencies, excluding dev/docs)
EXTRAS_ORDER = [
    "voice",
    "emotion",
    "nlp",
    "ner",
    "bertopic",
    "maps",
    "visualization",
    "plotly",
    "ui",
]

app = typer.Typer(
    name="deps",
    help="Optional dependency status and install (extras)",
    no_args_is_help=True,
)


@app.command("status")
def deps_status() -> None:
    """Show which extras are available or missing and current core_mode."""
    cfg = get_config()
    core_mode = getattr(cfg, "core_mode", True)

    table = Table(title="Optional extras")
    table.add_column("Extra", style="cyan")
    table.add_column("Status", style="green")
    for name in EXTRAS_ORDER:
        available = is_extra_available(name)
        status = "[green]available[/green]" if available else "[red]missing[/red]"
        table.add_row(name, status)
    console.print(table)
    console.print(f"\n[bold]core_mode[/bold]: {core_mode}")
    console.print(
        "When core_mode is True, only core modules run; optional modules are excluded and auto-install is disabled."
    )
    console.print(
        "Use [cyan]transcriptx deps install --full[/cyan] or install specific extras, and [cyan]--no-core[/cyan] to disable core mode."
    )


@app.command("install")
def deps_install(
    full: bool = typer.Option(
        False, "--full", help="Install all extras (transcriptx[full])"
    ),
    extras: list[str] = typer.Argument(
        None, help="Extras to install, e.g. voice emotion nlp"
    ),
) -> None:
    """Install optional dependencies. Use --full for all extras, or list extras (voice emotion nlp ...)."""
    if full:
        target = "transcriptx[full]"
        console.print(f"Installing [cyan]{target}[/cyan]...")
        rc = subprocess.call(
            [sys.executable, "-m", "pip", "install", target],
            cwd=None,
        )
        if rc != 0:
            raise typer.Exit(rc)
        console.print("[green]Done.[/green]")
        return

    if not extras:
        console.print(
            "[yellow]Specify --full or list extras to install, e.g.: transcriptx deps install voice emotion nlp[/yellow]"
        )
        raise typer.Exit(1)

    # Normalize: accept "nlp" and "ner" etc.
    valid = set(EXTRAS_ORDER) | {"full"}
    chosen = []
    for e in extras:
        e = e.strip().lower()
        if e in valid:
            chosen.append(e)
        else:
            console.print(
                f"[red]Unknown extra: {e}. Known: {', '.join(EXTRAS_ORDER)}[/red]"
            )
            raise typer.Exit(1)

    if not chosen:
        raise typer.Exit(1)

    target = "transcriptx[" + ",".join(chosen) + "]"
    console.print(f"Installing [cyan]{target}[/cyan]...")
    rc = subprocess.call(
        [sys.executable, "-m", "pip", "install", target],
        cwd=None,
    )
    if rc != 0:
        raise typer.Exit(rc)
    console.print("[green]Done.[/green]")
