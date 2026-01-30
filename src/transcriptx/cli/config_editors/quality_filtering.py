"""Quality filtering configuration editor."""

import copy
import questionary
from rich import print

from transcriptx.utils.text_utils import strip_emojis


# Built-in profiles that cannot be deleted
BUILT_IN_PROFILES = {
    "balanced",
    "academic",
    "business",
    "casual",
    "technical",
    "interview",
}


def edit_quality_filtering_config(config):
    """Edit quality filtering profile configuration."""
    print("\n[bold cyan]🎯 Quality Filtering Profiles[/bold cyan]")

    while True:
        choice = questionary.select(
            "Quality Filtering Options:",
            choices=[
                "👀 View Active Profile",
                "🔄 Switch Profile",
                "📋 View Profile Details",
                "✏️ Edit Profile",
                "➕ Create Custom Profile",
                "🗑️ Delete Custom Profile",
                "📊 List All Profiles",
                "⚙️ Toggle Quality Filtering",
                "🔙 Back",
            ],
        ).ask()

        if choice == "👀 View Active Profile":
            active_profile = getattr(
                config.analysis, "quality_filtering_profile", "balanced"
            )
            msg = f"\nCurrent active profile: {active_profile}"
            print(strip_emojis(msg) if not config.use_emojis else msg)
            profiles = getattr(config.analysis, "quality_filtering_profiles", {})
            if active_profile in profiles:
                desc = profiles[active_profile].get("description", "No description")
                msg = f"Description: {desc}"
                print(strip_emojis(msg) if not config.use_emojis else msg)

        elif choice == "🔄 Switch Profile":
            switch_quality_profile(config, BUILT_IN_PROFILES)

        elif choice == "📋 View Profile Details":
            view_quality_profile_details(config)

        elif choice == "✏️ Edit Profile":
            edit_quality_profile_interactive(config, BUILT_IN_PROFILES)

        elif choice == "➕ Create Custom Profile":
            create_custom_quality_profile(config)

        elif choice == "🗑️ Delete Custom Profile":
            delete_custom_quality_profile(config, BUILT_IN_PROFILES)

        elif choice == "📊 List All Profiles":
            list_quality_profiles_interactive(config, BUILT_IN_PROFILES)

        elif choice == "⚙️ Toggle Quality Filtering":
            current = getattr(config.analysis, "use_quality_filtering", True)
            msg = f"Quality filtering is currently: {'Enabled' if current else 'Disabled'}"
            print(strip_emojis(msg) if not config.use_emojis else msg)
            new_value = questionary.confirm(
                "Enable quality filtering?", default=current
            ).ask()
            config.analysis.use_quality_filtering = new_value
            msg = f"Quality filtering {'enabled' if new_value else 'disabled'}"
            print(strip_emojis(msg) if not config.use_emojis else msg)

        elif choice == "🔙 Back":
            break


def switch_quality_profile(config, built_in_profiles):
    """Switch the active quality filtering profile."""
    profiles = getattr(config.analysis, "quality_filtering_profiles", {})
    if not profiles:
        msg = "No profiles available."
        print(strip_emojis(msg) if not config.use_emojis else msg)
        return

    current_profile = getattr(config.analysis, "quality_filtering_profile", "balanced")

    # Create choices with descriptions - use questionary.Choice for proper value mapping
    choices = []
    for name, profile_data in profiles.items():
        desc = profile_data.get("description", "")
        marker = "✓ " if name == current_profile else "  "
        profile_type = " (Built-in)" if name in built_in_profiles else " (Custom)"
        display_text = f"{marker}{name}{profile_type} - {desc}"
        choices.append(questionary.Choice(title=display_text, value=name))

    selected = questionary.select(
        "Select profile:",
        choices=choices,
    ).ask()

    if selected and selected in profiles:
        config.analysis.quality_filtering_profile = selected
        msg = f"✓ Switched to profile: {selected}"
        print(strip_emojis(msg) if not config.use_emojis else msg)


def view_quality_profile_details(config):
    """View detailed information about a quality filtering profile."""
    profiles = getattr(config.analysis, "quality_filtering_profiles", {})
    if not profiles:
        msg = "No profiles available."
        print(strip_emojis(msg) if not config.use_emojis else msg)
        return

    profile_name = questionary.select(
        "Select profile to view:",
        choices=list(profiles.keys()),
    ).ask()

    if profile_name and profile_name in profiles:
        profile = profiles[profile_name]
        msg = f"\n[bold]Profile: {profile_name}[/bold]"
        print(strip_emojis(msg) if not config.use_emojis else msg)

        if "description" in profile:
            msg = f"Description: {profile['description']}"
            print(strip_emojis(msg) if not config.use_emojis else msg)

        if "weights" in profile:
            msg = "\nWeights:"
            print(strip_emojis(msg) if not config.use_emojis else msg)
            for key, value in profile["weights"].items():
                msg = f"  • {key}: {value}"
                print(strip_emojis(msg) if not config.use_emojis else msg)

        if "thresholds" in profile:
            msg = "\nThresholds:"
            print(strip_emojis(msg) if not config.use_emojis else msg)
            for key, value in profile["thresholds"].items():
                # Handle tuple values
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    msg = f"  • {key}: ({value[0]}, {value[1]})"
                else:
                    msg = f"  • {key}: {value}"
                print(strip_emojis(msg) if not config.use_emojis else msg)

        if "indicators" in profile:
            msg = "\nIndicators:"
            print(strip_emojis(msg) if not config.use_emojis else msg)
            for key, value in profile["indicators"].items():
                if isinstance(value, list):
                    msg = f"  • {key}: {', '.join(value[:5])}"
                    if len(value) > 5:
                        msg += f" ... ({len(value)} total)"
                    print(strip_emojis(msg) if not config.use_emojis else msg)
                else:
                    msg = f"  • {key}: {value}"
                    print(strip_emojis(msg) if not config.use_emojis else msg)


def edit_quality_profile_interactive(config, built_in_profiles):
    """Edit a quality filtering profile interactively."""
    profiles = getattr(config.analysis, "quality_filtering_profiles", {})
    if not profiles:
        msg = "No profiles available."
        print(strip_emojis(msg) if not config.use_emojis else msg)
        return

    profile_name = questionary.select(
        "Select profile to edit:",
        choices=list(profiles.keys()),
    ).ask()

    if not profile_name or profile_name not in profiles:
        return

    # Check if it's a built-in profile - create a copy for editing
    if profile_name in built_in_profiles:
        msg = f"'{profile_name}' is a built-in profile. Creating a copy for editing..."
        print(strip_emojis(msg) if not config.use_emojis else msg)
        copy_name = questionary.text(
            "Enter name for the copy:",
            validate=lambda text: len(text.strip()) > 0
            and text.strip() not in profiles,
        ).ask()
        if not copy_name or copy_name.strip() in profiles:
            return
        copy_name = copy_name.strip()
        # Create a deep copy
        profiles[copy_name] = copy.deepcopy(profiles[profile_name])
        profiles[copy_name]["description"] = f"Copy of {profile_name}"
        profile_name = copy_name

    profile = profiles[profile_name]

    while True:
        choice = questionary.select(
            f"Edit Profile: {profile_name}",
            choices=[
                "📝 Edit Description",
                "⚖️ Edit Weights",
                "📏 Edit Thresholds",
                "🔤 Edit Indicators",
                "🔙 Back",
            ],
        ).ask()

        if choice == "📝 Edit Description":
            current_desc = profile.get("description", "")
            msg = f"Current description: {current_desc}"
            print(strip_emojis(msg) if not config.use_emojis else msg)
            new_desc = questionary.text("Enter new description:").ask()
            if new_desc:
                profile["description"] = new_desc

        elif choice == "⚖️ Edit Weights":
            edit_quality_profile_weights(profile, config)

        elif choice == "📏 Edit Thresholds":
            edit_quality_profile_thresholds(profile, config)

        elif choice == "🔤 Edit Indicators":
            edit_quality_profile_indicators(profile, config)

        elif choice == "🔙 Back":
            break


def edit_quality_profile_weights(profile, config):
    """Edit weight values for a quality profile."""
    if "weights" not in profile:
        profile["weights"] = {}

    weights = profile["weights"]

    while True:
        # Show current weights
        msg = "\nCurrent Weights:"
        print(strip_emojis(msg) if not config.use_emojis else msg)
        for key, value in weights.items():
            msg = f"  • {key}: {value}"
            print(strip_emojis(msg) if not config.use_emojis else msg)

        choice = questionary.select(
            "Edit Weights:",
            choices=[
                "➕ Add Weight",
                "✏️ Edit Weight",
                "🗑️ Remove Weight",
                "🔙 Back",
            ],
        ).ask()

        if choice == "➕ Add Weight":
            key = questionary.text("Enter weight name:").ask()
            if key:
                try:
                    value = float(questionary.text("Enter weight value:").ask())
                    weights[key] = value
                except (ValueError, TypeError):
                    msg = "Invalid value. Must be a number."
                    print(strip_emojis(msg) if not config.use_emojis else msg)

        elif choice == "✏️ Edit Weight":
            if not weights:
                msg = "No weights to edit."
                print(strip_emojis(msg) if not config.use_emojis else msg)
                continue
            key = questionary.select(
                "Select weight to edit:", choices=list(weights.keys())
            ).ask()
            if key:
                try:
                    value = float(
                        questionary.text(
                            f"Enter new value (current: {weights[key]}):"
                        ).ask()
                    )
                    weights[key] = value
                except (ValueError, TypeError):
                    msg = "Invalid value. Must be a number."
                    print(strip_emojis(msg) if not config.use_emojis else msg)

        elif choice == "🗑️ Remove Weight":
            if not weights:
                msg = "No weights to remove."
                print(strip_emojis(msg) if not config.use_emojis else msg)
                continue
            key = questionary.select(
                "Select weight to remove:", choices=list(weights.keys())
            ).ask()
            if key:
                del weights[key]

        elif choice == "🔙 Back":
            break


def edit_quality_profile_thresholds(profile, config):
    """Edit threshold values for a quality profile."""
    if "thresholds" not in profile:
        profile["thresholds"] = {}

    thresholds = profile["thresholds"]

    while True:
        # Show current thresholds
        msg = "\nCurrent Thresholds:"
        print(strip_emojis(msg) if not config.use_emojis else msg)
        for key, value in thresholds.items():
            if isinstance(value, (list, tuple)) and len(value) == 2:
                msg = f"  • {key}: ({value[0]}, {value[1]})"
            else:
                msg = f"  • {key}: {value}"
            print(strip_emojis(msg) if not config.use_emojis else msg)

        choice = questionary.select(
            "Edit Thresholds:",
            choices=[
                "➕ Add Threshold",
                "✏️ Edit Threshold",
                "🗑️ Remove Threshold",
                "🔙 Back",
            ],
        ).ask()

        if choice == "➕ Add Threshold":
            key = questionary.text("Enter threshold name:").ask()
            if key:
                threshold_type = questionary.select(
                    "Threshold type:",
                    choices=["Single value (integer)", "Range (two integers)"],
                ).ask()
                if threshold_type == "Single value (integer)":
                    try:
                        value = int(questionary.text("Enter threshold value:").ask())
                        thresholds[key] = value
                    except (ValueError, TypeError):
                        msg = "Invalid value. Must be an integer."
                        print(strip_emojis(msg) if not config.use_emojis else msg)
                else:
                    try:
                        min_val = int(questionary.text("Enter minimum value:").ask())
                        max_val = int(questionary.text("Enter maximum value:").ask())
                        thresholds[key] = (min_val, max_val)
                    except (ValueError, TypeError):
                        msg = "Invalid values. Must be integers."
                        print(strip_emojis(msg) if not config.use_emojis else msg)

        elif choice == "✏️ Edit Threshold":
            if not thresholds:
                msg = "No thresholds to edit."
                print(strip_emojis(msg) if not config.use_emojis else msg)
                continue
            key = questionary.select(
                "Select threshold to edit:", choices=list(thresholds.keys())
            ).ask()
            if key:
                current = thresholds[key]
                if isinstance(current, (list, tuple)) and len(current) == 2:
                    try:
                        min_val = int(
                            questionary.text(
                                f"Enter minimum value (current: {current[0]}):"
                            ).ask()
                        )
                        max_val = int(
                            questionary.text(
                                f"Enter maximum value (current: {current[1]}):"
                            ).ask()
                        )
                        thresholds[key] = (min_val, max_val)
                    except (ValueError, TypeError):
                        msg = "Invalid values. Must be integers."
                        print(strip_emojis(msg) if not config.use_emojis else msg)
                else:
                    try:
                        value = int(
                            questionary.text(
                                f"Enter new value (current: {current}):"
                            ).ask()
                        )
                        thresholds[key] = value
                    except (ValueError, TypeError):
                        msg = "Invalid value. Must be an integer."
                        print(strip_emojis(msg) if not config.use_emojis else msg)

        elif choice == "🗑️ Remove Threshold":
            if not thresholds:
                msg = "No thresholds to remove."
                print(strip_emojis(msg) if not config.use_emojis else msg)
                continue
            key = questionary.select(
                "Select threshold to remove:", choices=list(thresholds.keys())
            ).ask()
            if key:
                del thresholds[key]

        elif choice == "🔙 Back":
            break


def edit_quality_profile_indicators(profile, config):
    """Edit indicator word lists for a quality profile."""
    if "indicators" not in profile:
        profile["indicators"] = {}

    indicators = profile["indicators"]

    while True:
        # Show current indicators
        msg = "\nCurrent Indicators:"
        print(strip_emojis(msg) if not config.use_emojis else msg)
        for key, value in indicators.items():
            if isinstance(value, list):
                msg = f"  • {key}: {len(value)} words - {', '.join(value[:5])}"
                if len(value) > 5:
                    msg += "..."
                print(strip_emojis(msg) if not config.use_emojis else msg)
            else:
                msg = f"  • {key}: {value}"
                print(strip_emojis(msg) if not config.use_emojis else msg)

        choice = questionary.select(
            "Edit Indicators:",
            choices=[
                "➕ Add Indicator List",
                "✏️ Edit Indicator List",
                "🗑️ Remove Indicator List",
                "🔙 Back",
            ],
        ).ask()

        if choice == "➕ Add Indicator List":
            key = questionary.text("Enter indicator name:").ask()
            if key:
                words_str = questionary.text("Enter words (comma-separated):").ask()
                if words_str:
                    words = [w.strip() for w in words_str.split(",") if w.strip()]
                    indicators[key] = words

        elif choice == "✏️ Edit Indicator List":
            if not indicators:
                msg = "No indicators to edit."
                print(strip_emojis(msg) if not config.use_emojis else msg)
                continue
            key = questionary.select(
                "Select indicator to edit:", choices=list(indicators.keys())
            ).ask()
            if key:
                current = indicators[key]
                if isinstance(current, list):
                    current_str = ", ".join(current)
                    msg = f"Current words: {current_str}"
                    print(strip_emojis(msg) if not config.use_emojis else msg)
                    words_str = questionary.text(
                        "Enter new words (comma-separated):"
                    ).ask()
                    if words_str:
                        words = [w.strip() for w in words_str.split(",") if w.strip()]
                        indicators[key] = words
                else:
                    msg = f"Current value: {current}"
                    print(strip_emojis(msg) if not config.use_emojis else msg)
                    new_value = questionary.text("Enter new value:").ask()
                    if new_value:
                        indicators[key] = new_value

        elif choice == "🗑️ Remove Indicator List":
            if not indicators:
                msg = "No indicators to remove."
                print(strip_emojis(msg) if not config.use_emojis else msg)
                continue
            key = questionary.select(
                "Select indicator to remove:", choices=list(indicators.keys())
            ).ask()
            if key:
                del indicators[key]

        elif choice == "🔙 Back":
            break


def create_custom_quality_profile(config):
    """Create a new custom quality filtering profile."""
    profiles = getattr(config.analysis, "quality_filtering_profiles", {})

    profile_name = questionary.text(
        "Enter profile name:",
        validate=lambda text: len(text.strip()) > 0 and text.strip() not in profiles,
    ).ask()

    if not profile_name:
        return

    profile_name = profile_name.strip()

    description = questionary.text("Enter profile description (optional):").ask() or ""

    # Ask if user wants to copy from existing profile
    if profiles:
        copy_from = questionary.confirm(
            "Copy settings from an existing profile?", default=True
        ).ask()

        if copy_from:
            source_profile = questionary.select(
                "Select profile to copy from:", choices=list(profiles.keys())
            ).ask()

            if source_profile and source_profile in profiles:
                new_profile = copy.deepcopy(profiles[source_profile])
                new_profile["description"] = description
                profiles[profile_name] = new_profile
                msg = f"✓ Created profile '{profile_name}' from '{source_profile}'"
                print(strip_emojis(msg) if not config.use_emojis else msg)
                return

    # Create empty profile
    profiles[profile_name] = {
        "description": description,
        "weights": {},
        "thresholds": {},
        "indicators": {},
    }

    msg = f"✓ Created empty profile '{profile_name}'. You can now edit it."
    print(strip_emojis(msg) if not config.use_emojis else msg)


def delete_custom_quality_profile(config, built_in_profiles):
    """Delete a custom quality filtering profile."""
    profiles = getattr(config.analysis, "quality_filtering_profiles", {})

    # Filter out built-in profiles
    custom_profiles = [p for p in profiles.keys() if p not in built_in_profiles]

    if not custom_profiles:
        msg = "No custom profiles available to delete."
        print(strip_emojis(msg) if not config.use_emojis else msg)
        return

    profile_name = questionary.select(
        "Select profile to delete:", choices=custom_profiles
    ).ask()

    if profile_name:
        confirm = questionary.confirm(
            f"Are you sure you want to delete profile '{profile_name}'?", default=False
        ).ask()

        if confirm:
            # Check if it's the active profile
            active_profile = getattr(
                config.analysis, "quality_filtering_profile", "balanced"
            )
            if profile_name == active_profile:
                msg = "Cannot delete the active profile. Please switch to another profile first."
                print(strip_emojis(msg) if not config.use_emojis else msg)
                return

            del profiles[profile_name]
            msg = f"✓ Deleted profile '{profile_name}'"
            print(strip_emojis(msg) if not config.use_emojis else msg)


def list_quality_profiles_interactive(config, built_in_profiles):
    """List all quality filtering profiles."""
    profiles = getattr(config.analysis, "quality_filtering_profiles", {})
    active_profile = getattr(config.analysis, "quality_filtering_profile", "balanced")

    if not profiles:
        msg = "No profiles available."
        print(strip_emojis(msg) if not config.use_emojis else msg)
        return

    msg = "\n[bold]Quality Filtering Profiles:[/bold]"
    print(strip_emojis(msg) if not config.use_emojis else msg)

    for profile_name in sorted(profiles.keys()):
        profile = profiles[profile_name]
        marker = "✓ " if profile_name == active_profile else "  "
        profile_type = (
            " (Built-in)" if profile_name in built_in_profiles else " (Custom)"
        )
        desc = profile.get("description", "No description")
        msg = f"{marker}{profile_name}{profile_type} - {desc}"
        print(strip_emojis(msg) if not config.use_emojis else msg)
