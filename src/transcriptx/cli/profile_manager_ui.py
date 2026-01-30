"""
Interactive Profile Management UI for TranscriptX.

This module provides interactive functions for managing module-specific
configuration profiles, allowing users to create, save, load, and manage
named sets of configuration choices.
"""

import questionary
from pathlib import Path
from rich import print

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.profile_manager import get_profile_manager


# Module names and their display names
MODULE_DISPLAY_NAMES = {
    "topic_modeling": "Topic Modeling",
    "acts": "Dialogue Acts Classification",
    "tag_extraction": "Tag Extraction",
    "qa_analysis": "Q&A Analysis",
    "temporal_dynamics": "Temporal Dynamics",
    "vectorization": "Vectorization",
    "workflow": "Workflow Settings",
}


def manage_profiles_interactive(module_name: str | None = None):
    """
    Interactive profile management menu.

    Args:
        module_name: Optional module name to start with. If None, user selects.
    """
    config = get_config()
    profile_manager = get_profile_manager()

    # Select module if not provided
    if module_name is None:
        module_name = select_module_interactive()
        if not module_name:
            return

    display_name = MODULE_DISPLAY_NAMES.get(module_name, module_name)

    while True:
        choice = questionary.select(
            f"Profile Management: {display_name}",
            choices=[
                "👀 View Active Profile",
                "🔄 Switch Profile",
                "➕ Create New Profile",
                "💾 Save Current Settings as Profile",
                "🗑️ Delete Profile",
                "📋 List All Profiles",
                "✏️ Rename Profile",
                "📤 Export Profile",
                "📥 Import Profile",
                "🔙 Back to Main Menu",
            ],
        ).ask()

        if choice == "👀 View Active Profile":
            view_active_profile(module_name)
        elif choice == "🔄 Switch Profile":
            switch_profile_interactive(module_name)
        elif choice == "➕ Create New Profile":
            create_profile_interactive(module_name)
        elif choice == "💾 Save Current Settings as Profile":
            save_current_as_profile_interactive(module_name)
        elif choice == "🗑️ Delete Profile":
            delete_profile_interactive(module_name)
        elif choice == "📋 List All Profiles":
            list_profiles_interactive(module_name)
        elif choice == "✏️ Rename Profile":
            rename_profile_interactive(module_name)
        elif choice == "📤 Export Profile":
            export_profile_interactive(module_name)
        elif choice == "📥 Import Profile":
            import_profile_interactive(module_name)
        elif choice == "🔙 Back to Main Menu":
            break


def select_module_interactive() -> str | None:
    """Select a module for profile management."""
    choices = [
        ("Topic Modeling", "topic_modeling"),
        ("Dialogue Acts Classification", "acts"),
        ("Tag Extraction", "tag_extraction"),
        ("Q&A Analysis", "qa_analysis"),
        ("Temporal Dynamics", "temporal_dynamics"),
        ("Vectorization", "vectorization"),
        ("Workflow Settings", "workflow"),
    ]

    selected = questionary.select(
        "Select module for profile management:",
        choices=[choice[0] for choice in choices],
    ).ask()

    if selected:
        for display, name in choices:
            if display == selected:
                return name

    return None


def view_active_profile(module_name: str):
    """View the currently active profile for a module."""
    config = get_config()
    profile_manager = get_profile_manager()

    # Get active profile name
    active_profile_name = get_active_profile_name(config, module_name)

    print(f"\n[bold cyan]Active Profile: {active_profile_name}[/bold cyan]")

    # Load and display profile
    profile = profile_manager.load_profile(module_name, active_profile_name)
    if profile:
        if "description" in profile:
            print(f"[dim]Description: {profile['description']}[/dim]")
        if "config" in profile:
            print("\n[bold]Configuration:[/bold]")
            for key, value in profile["config"].items():
                print(f"  • {key}: {value}")
    else:
        print("[yellow]Using default configuration values.[/yellow]")


def switch_profile_interactive(module_name: str):
    """Switch the active profile for a module."""
    config = get_config()
    profile_manager = get_profile_manager()

    # List available profiles
    profiles = profile_manager.list_profiles(module_name)
    if not profiles:
        print("[yellow]No profiles available.[/yellow]")
        return

    # Get current active profile
    current_active = get_active_profile_name(config, module_name)

    # Select new profile
    selected = questionary.select(
        f"Select profile for {MODULE_DISPLAY_NAMES.get(module_name, module_name)}:",
        choices=profiles,
        default=current_active,
    ).ask()

    if selected and selected != current_active:
        # Update active profile
        set_active_profile(config, module_name, selected)
        print(f"[green]✓ Switched to profile: {selected}[/green]")

        # Reload config to apply profile
        from transcriptx.core.utils.config import set_config, TranscriptXConfig

        new_config = TranscriptXConfig()
        set_config(new_config)
        print("[green]✓ Configuration reloaded with new profile.[/green]")


def create_profile_interactive(module_name: str):
    """Create a new profile interactively."""
    profile_manager = get_profile_manager()

    # Get profile name
    profile_name = questionary.text(
        "Enter profile name:",
        validate=lambda text: len(text.strip()) > 0 and text.strip() != "default",
    ).ask()

    if not profile_name:
        return

    profile_name = profile_name.strip()

    # Check if profile already exists
    if profile_manager.profile_exists(module_name, profile_name):
        overwrite = questionary.confirm(
            f"Profile '{profile_name}' already exists. Overwrite?", default=False
        ).ask()
        if not overwrite:
            return

    # Get description
    description = questionary.text(
        "Enter profile description (optional):",
    ).ask()

    # Get source profile to copy from
    existing_profiles = profile_manager.list_profiles(module_name)
    source_profile = questionary.select(
        "Copy settings from existing profile:",
        choices=existing_profiles,
        default="default",
    ).ask()

    # Load source profile
    source_data = profile_manager.load_profile(module_name, source_profile)
    if source_data and "config" in source_data:
        config_dict = source_data["config"]
    else:
        # Use default config values
        config_dict = get_default_config_dict(module_name)

    # Save new profile
    if profile_manager.save_profile(
        module_name, profile_name, config_dict, description
    ):
        print(f"[green]✓ Created profile: {profile_name}[/green]")
    else:
        print(f"[red]✗ Failed to create profile: {profile_name}[/red]")


def save_current_as_profile_interactive(module_name: str):
    """Save current configuration settings as a new profile."""
    config = get_config()
    profile_manager = get_profile_manager()

    # Get profile name
    profile_name = questionary.text(
        "Enter profile name:",
        validate=lambda text: len(text.strip()) > 0 and text.strip() != "default",
    ).ask()

    if not profile_name:
        return

    profile_name = profile_name.strip()

    # Check if profile already exists
    if profile_manager.profile_exists(module_name, profile_name):
        overwrite = questionary.confirm(
            f"Profile '{profile_name}' already exists. Overwrite?", default=False
        ).ask()
        if not overwrite:
            return

    # Get description
    description = questionary.text(
        "Enter profile description (optional):",
    ).ask()

    # Get current config for module
    config_dict = get_current_config_dict(config, module_name)

    # Save profile
    if profile_manager.save_profile(
        module_name, profile_name, config_dict, description
    ):
        print(f"[green]✓ Saved current settings as profile: {profile_name}[/green]")
    else:
        print(f"[red]✗ Failed to save profile: {profile_name}[/red]")


def delete_profile_interactive(module_name: str):
    """Delete a profile."""
    profile_manager = get_profile_manager()

    # List profiles (excluding default)
    profiles = [p for p in profile_manager.list_profiles(module_name) if p != "default"]

    if not profiles:
        print(
            "[yellow]No profiles available to delete (default profile cannot be deleted).[/yellow]"
        )
        return

    # Select profile to delete
    selected = questionary.select(
        "Select profile to delete:",
        choices=profiles,
    ).ask()

    if selected:
        confirm = questionary.confirm(
            f"Are you sure you want to delete profile '{selected}'?", default=False
        ).ask()

        if confirm:
            if profile_manager.delete_profile(module_name, selected):
                print(f"[green]✓ Deleted profile: {selected}[/green]")
            else:
                print(f"[red]✗ Failed to delete profile: {selected}[/red]")


def list_profiles_interactive(module_name: str):
    """List all profiles for a module."""
    profile_manager = get_profile_manager()
    config = get_config()

    profiles = profile_manager.list_profiles(module_name)
    active_profile = get_active_profile_name(config, module_name)

    print(
        f"\n[bold cyan]Profiles for {MODULE_DISPLAY_NAMES.get(module_name, module_name)}:[/bold cyan]"
    )

    for profile_name in profiles:
        profile = profile_manager.load_profile(module_name, profile_name)
        marker = "✓" if profile_name == active_profile else " "
        description = profile.get("description", "") if profile else ""

        print(
            f"  {marker} {profile_name}" + (f" - {description}" if description else "")
        )


def rename_profile_interactive(module_name: str):
    """Rename a profile."""
    profile_manager = get_profile_manager()

    # List profiles (excluding default)
    profiles = [p for p in profile_manager.list_profiles(module_name) if p != "default"]

    if not profiles:
        print(
            "[yellow]No profiles available to rename (default profile cannot be renamed).[/yellow]"
        )
        return

    # Select profile to rename
    old_name = questionary.select(
        "Select profile to rename:",
        choices=profiles,
    ).ask()

    if not old_name:
        return

    # Get new name
    new_name = questionary.text(
        "Enter new profile name:",
        validate=lambda text: len(text.strip()) > 0 and text.strip() != "default",
    ).ask()

    if new_name:
        new_name = new_name.strip()
        if profile_manager.rename_profile(module_name, old_name, new_name):
            print(f"[green]✓ Renamed profile '{old_name}' to '{new_name}'[/green]")
        else:
            print(f"[red]✗ Failed to rename profile[/red]")


def export_profile_interactive(module_name: str):
    """Export a profile to a file."""
    profile_manager = get_profile_manager()

    # List profiles
    profiles = profile_manager.list_profiles(module_name)

    # Select profile to export
    selected = questionary.select(
        "Select profile to export:",
        choices=profiles,
    ).ask()

    if not selected:
        return

    # Get export path
    export_path = questionary.text(
        "Enter export file path:", default=f"{module_name}_{selected}.json"
    ).ask()

    if export_path:
        export_path_obj = Path(export_path)
        if profile_manager.export_profile(module_name, selected, export_path_obj):
            print(f"[green]✓ Exported profile to: {export_path}[/green]")
        else:
            print(f"[red]✗ Failed to export profile[/red]")


def import_profile_interactive(module_name: str):
    """Import a profile from a file."""
    profile_manager = get_profile_manager()

    # Get import path
    import_path = questionary.text(
        "Enter import file path:",
    ).ask()

    if not import_path:
        return

    import_path_obj = Path(import_path)
    if not import_path_obj.exists():
        print(f"[red]File not found: {import_path}[/red]")
        return

    # Get profile name
    profile_name = questionary.text(
        "Enter profile name for imported profile:",
        validate=lambda text: len(text.strip()) > 0 and text.strip() != "default",
    ).ask()

    if not profile_name:
        return

    profile_name = profile_name.strip()

    # Check if profile already exists
    overwrite = False
    if profile_manager.profile_exists(module_name, profile_name):
        overwrite = questionary.confirm(
            f"Profile '{profile_name}' already exists. Overwrite?", default=False
        ).ask()

    if profile_manager.import_profile(
        module_name, profile_name, import_path_obj, overwrite
    ):
        print(f"[green]✓ Imported profile: {profile_name}[/green]")
    else:
        print(f"[red]✗ Failed to import profile[/red]")


# Helper functions


def get_active_profile_name(config, module_name: str) -> str:
    """Get the active profile name for a module."""
    if module_name == "workflow":
        return getattr(config, "active_workflow_profile", "default")
    else:
        return getattr(config.analysis, f"active_{module_name}_profile", "default")


def set_active_profile(config, module_name: str, profile_name: str):
    """Set the active profile for a module."""
    if module_name == "workflow":
        config.active_workflow_profile = profile_name
    else:
        setattr(config.analysis, f"active_{module_name}_profile", profile_name)


def get_current_config_dict(config, module_name: str) -> dict:
    """Get current configuration as a dictionary for a module."""
    if module_name == "workflow":
        config_obj = config.workflow
    else:
        config_obj = getattr(config.analysis, module_name)

    # Convert dataclass to dict
    from dataclasses import asdict

    return asdict(config_obj)


def get_default_config_dict(module_name: str) -> dict:
    """Get default configuration dictionary for a module."""
    from transcriptx.core.utils.config import (
        TopicModelingConfig,
        ActsConfig,
        TagExtractionConfig,
        QAAnalysisConfig,
        TemporalDynamicsConfig,
        VectorizationConfig,
        WorkflowConfig,
    )
    from dataclasses import asdict

    config_map = {
        "topic_modeling": TopicModelingConfig,
        "acts": ActsConfig,
        "tag_extraction": TagExtractionConfig,
        "qa_analysis": QAAnalysisConfig,
        "temporal_dynamics": TemporalDynamicsConfig,
        "vectorization": VectorizationConfig,
        "workflow": WorkflowConfig,
    }

    config_class = config_map.get(module_name)
    if config_class:
        return asdict(config_class())

    return {}
