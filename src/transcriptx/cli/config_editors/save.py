"""Configuration save utilities."""

import questionary
from rich import print

from transcriptx.utils.text_utils import strip_emojis
from ._dirty_tracker import reset_dirty


def save_config_interactive(config):
    """Save configuration interactively."""
    print("\n[bold cyan]💾 Save Configuration[/bold cyan]")

    msg = "Enter configuration file path"
    print(strip_emojis(msg) if not config.use_emojis else msg)

    save_file = questionary.text("Enter configuration file path").ask()

    try:
        config.save_to_file(save_file)
        reset_dirty()
        msg = f"✅ Configuration saved to {save_file}"
        print(strip_emojis(msg) if not config.use_emojis else msg)
    except Exception as e:
        msg = f"❌ Failed to save configuration: {e}"
        print(strip_emojis(msg) if not config.use_emojis else msg)
