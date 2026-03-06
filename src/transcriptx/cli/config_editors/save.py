"""Configuration save utilities."""

from typing import Any

import questionary
from rich import print

from transcriptx.utils.text_utils import strip_emojis
from ._dirty_tracker import reset_dirty


def _default_save_path(config: Any) -> str:
    """Resolve default config save path: workflow setting or project config path."""
    from transcriptx.core.config.persistence import get_project_config_path

    path = (getattr(config.workflow, "default_config_save_path", None) or "").strip()
    return path or str(get_project_config_path())


def save_config_interactive(config: Any) -> None:
    """Save configuration interactively."""
    print("\n[bold cyan]💾 Save Configuration[/bold cyan]")

    default_path = _default_save_path(config)
    msg = "Enter configuration file path"
    print(strip_emojis(msg) if not config.use_emojis else msg)

    save_file = questionary.text(
        "Enter configuration file path",
        default=default_path,
    ).ask()

    if not save_file or not save_file.strip():
        save_file = default_path

    try:
        config.save_to_file(save_file.strip())
        reset_dirty()
        msg = f"✅ Configuration saved to {save_file}"
        print(strip_emojis(msg) if not config.use_emojis else msg)
    except Exception as e:
        msg = f"❌ Failed to save configuration: {e}"
        print(strip_emojis(msg) if not config.use_emojis else msg)
