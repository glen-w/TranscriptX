"""
Interactive configuration editor for TranscriptX.

This module provides a comprehensive interactive configuration editor
that allows users to customize all TranscriptX settings.
"""

import questionary
from rich import print

from transcriptx.core.utils.config import get_config
from transcriptx.cli.config_editors import (
    edit_analysis_config,
    edit_transcription_config,
    edit_audio_preprocessing_config,
    edit_input_config,
    edit_output_config,
    edit_group_analysis_config,
    edit_logging_config,
    edit_dashboard_config,
    edit_workflow_config,
    show_current_config,
    save_config_interactive,
)


def edit_config_interactive() -> None:
    """Interactive configuration editor."""
    config = get_config()

    print("\n[bold cyan]🔧 Configuration Editor[/bold cyan]")

    while True:
        choice = questionary.select(
            "What would you like to configure?",
            choices=[
                "📊 Analysis Settings",
                "🎧 Transcription Settings",
                "🎵 Audio Preprocessing Settings",
                "📥 Input Settings",
                "📁 Output Settings",
                "👥 Group Analysis Settings",
                "🌐 Dashboard Settings",
                "📝 Logging Settings",
                "⚙️  Workflow / CLI Settings",
                "⚙️  Profile Management",
                "👀 View Current Configuration",
                "💾 Save Configuration",
                "🔙 Back to Main Menu",
            ],
        ).ask()

        try:
            if choice == "📊 Analysis Settings":
                edit_analysis_config(config)
            elif choice == "🎧 Transcription Settings":
                edit_transcription_config(config)
            elif choice == "🎵 Audio Preprocessing Settings":
                edit_audio_preprocessing_config(config)
            elif choice == "📥 Input Settings":
                edit_input_config(config)
            elif choice == "📁 Output Settings":
                edit_output_config(config)
            elif choice == "👥 Group Analysis Settings":
                edit_group_analysis_config(config)
            elif choice == "🌐 Dashboard Settings":
                edit_dashboard_config(config)
            elif choice == "📝 Logging Settings":
                edit_logging_config(config)
            elif choice == "⚙️  Workflow / CLI Settings":
                edit_workflow_config(config)
            elif choice == "⚙️  Profile Management":
                from transcriptx.cli.profile_manager_ui import manage_profiles_interactive

                manage_profiles_interactive()
            elif choice == "👀 View Current Configuration":
                show_current_config(config)
            elif choice == "💾 Save Configuration":
                save_config_interactive(config)
            elif choice == "🔙 Back to Main Menu":
                break
            else:
                print("[red]Invalid selection. Please try again.[/red]")
        except Exception as exc:
            print(f"[red]❌ Configuration editor error: {exc}[/red]")
