"""
CLI commands for state backup management.
"""

from pathlib import Path
from transcriptx.core.utils.state_backup import (
    list_backups,
    restore_from_backup,
    verify_backup,
    create_backup,
)
from transcriptx.core.utils.paths import DATA_DIR
from transcriptx.core.utils.logger import get_logger
from rich.console import Console
from rich.table import Table
import questionary

logger = get_logger()
console = Console()

PROCESSING_STATE_FILE = Path(DATA_DIR) / "processing_state.json"


def list_state_backups() -> None:
    """List all available state backups."""
    backups = list_backups()

    if not backups:
        console.print("[yellow]No backups found.[/yellow]")
        return

    table = Table(title="State File Backups")
    table.add_column("Name", style="cyan")
    table.add_column("Size", style="magenta")
    table.add_column("Created", style="green")
    table.add_column("Valid", style="yellow")

    for backup in backups:
        is_valid = verify_backup(Path(backup["path"]))
        size_mb = backup["size"] / (1024 * 1024)
        table.add_row(
            backup["name"],
            f"{size_mb:.2f} MB",
            backup["created"],
            "✅" if is_valid else "❌",
        )

    console.print(table)


def restore_state_backup() -> None:
    """Restore state from a backup."""
    backups = list_backups()

    if not backups:
        console.print("[yellow]No backups available.[/yellow]")
        return

    # Let user select backup
    choices = [f"{b['name']} ({b['created']})" for b in backups]

    selected = questionary.select("Select backup to restore:", choices=choices).ask()

    if not selected:
        return

    # Find selected backup
    backup_index = choices.index(selected)
    backup_path = Path(backups[backup_index]["path"])

    # Confirm restore
    if not questionary.confirm(
        f"Restore state from {backup_path.name}? This will overwrite current state.",
        default=False,
    ).ask():
        return

    # Restore
    if restore_from_backup(backup_path):
        console.print(f"[green]✅ State restored from {backup_path.name}[/green]")
    else:
        console.print(f"[red]❌ Failed to restore from {backup_path.name}[/red]")


def create_manual_backup() -> None:
    """Manually create a backup of the current state."""
    backup_path = create_backup()

    if backup_path:
        console.print(f"[green]✅ Backup created: {backup_path.name}[/green]")
    else:
        console.print("[red]❌ Failed to create backup[/red]")
