import questionary

from transcriptx.cli.config_editors import (
    edit_analysis_config,
)


def edit_config(config):
    """Legacy entrypoint maintained for compatibility."""
    while True:
        try:
            choice = questionary.select(
                "Analysis Options:",
                choices=[
                    "Sentiment Analysis",
                    "Emotion Analysis",
                    "NER Analysis",
                    "Word Cloud Settings",
                    "Understandability Metrics",
                    "Network Analysis",
                    "General Settings",
                    "🔙 Back",
                ],
            ).ask()
            if choice in {
                "Sentiment Analysis",
                "Emotion Analysis",
                "NER Analysis",
                "Word Cloud Settings",
                "Understandability Metrics",
                "Network Analysis",
                "General Settings",
            }:
                edit_analysis_config(config)
            elif choice == "🔙 Back":
                break
        except KeyboardInterrupt:
            print("\n[cyan]Cancelled. Returning to previous menu.[/cyan]")
            break
