import questionary
from rich import print
from transcriptx.core.utils.config import get_config
from transcriptx.core import get_available_modules, get_default_modules
from transcriptx.core.pipeline.module_registry import get_description


def select_analysis_modules() -> list[str]:
    available_modules = get_available_modules()
    sorted_modules = sorted(available_modules, key=lambda m: get_description(m) or "")
    display_to_module = {i: module for i, module in enumerate(sorted_modules, 1)}

    # Build choices for questionary
    choices = ["all"]
    for i, module in enumerate(sorted_modules, 1):
        description = get_description(module) or module
        choices.append(f"{i}. {description}")

    while True:
        try:
            selection = questionary.select(
                "\nSelect modules (Use arrow keys)",
                choices=choices,
                default="all",
            ).ask()
            if selection.lower() == "all":
                return get_default_modules()
            display_index = int(selection.split(".")[0])
            selected_module = display_to_module[display_index]
            selected_modules = [selected_module]
            return selected_modules
        except KeyboardInterrupt:
            print("\n[cyan]Cancelled. Returning to previous menu.[/cyan]")
            return []
        except ValueError:
            print("[red]❌ Invalid selection. Please choose a valid option.[/red]")
            continue


def select_analysis_mode() -> str:
    print("\n[bold cyan]🔍 Analysis Mode Selection[/bold cyan]")
    print("[dim]Choose the level of analysis detail and processing intensity[/dim]")
    choice = questionary.select(
        "Select analysis mode:",
        choices=[
            questionary.Choice(
                title="⚡ Quick Analysis (Recommended) - Faster processing with lightweight models. Good for initial exploration.",
                value="quick",
            ),
            questionary.Choice(
                title="🔬 Full Analysis - Comprehensive analysis with larger models. Best for detailed insights.",
                value="full",
            ),
        ],
        default="quick",
    ).ask()
    if choice == "quick":
        print("\n[green]✅ Quick Analysis Mode Selected[/green]")
        print("[dim]Features:[/dim]")
        print("  • Lightweight spaCy model for NER")
        print("  • Simple semantic similarity analysis")
        print("  • Optimized for 600+ segment transcripts on CPU")
        print("  • Balanced semantic profile for general conversations")
        print("  • Skipped geocoding and advanced features")
        print("  • Optimized for speed and efficiency")
    else:
        print("\n[blue]🔬 Full Analysis Mode Selected[/blue]")
        print("[dim]Features:[/dim]")
        print("  • Full spaCy model for NER")
        print("  • Advanced semantic similarity with quality filtering")
        print("  • Higher segment limits for comprehensive analysis")
        print("  • Full geocoding and advanced features")
        print("  • Maximum accuracy and detail")
    return choice


def apply_analysis_mode_settings(mode: str):
    config = get_config()
    if mode == "quick":
        settings = config.analysis.quick_analysis_settings
        config.analysis.analysis_mode = "quick"
        config.analysis.semantic_similarity_method = settings["semantic_method"]
        config.analysis.max_segments_for_semantic = settings[
            "max_segments_for_semantic"
        ]
        config.analysis.max_semantic_comparisons = settings["max_semantic_comparisons"]
        config.analysis.ner_use_light_model = settings["ner_use_light_model"]
        config.analysis.ner_max_segments = settings["ner_max_segments"]
        config.analysis.ner_include_geocoding = not settings["skip_geocoding"]
        config.analysis.quality_filtering_profile = settings["semantic_profile"]
        print(f"\n[dim]Applied {mode} analysis settings to configuration[/dim]")
    else:
        settings = config.analysis.full_analysis_settings
        config.analysis.analysis_mode = "full"
        config.analysis.semantic_similarity_method = settings["semantic_method"]
        config.analysis.max_segments_for_semantic = settings[
            "max_segments_for_semantic"
        ]
        config.analysis.max_semantic_comparisons = settings["max_semantic_comparisons"]
        config.analysis.ner_use_light_model = settings["ner_use_light_model"]
        config.analysis.ner_max_segments = settings["ner_max_segments"]
        config.analysis.ner_include_geocoding = not settings["skip_geocoding"]
        # Apply increased segment limits for full mode
        if "max_segments_per_speaker" in settings:
            config.analysis.max_segments_per_speaker = settings["max_segments_per_speaker"]
        if "max_segments_for_cross_speaker" in settings:
            config.analysis.max_segments_for_cross_speaker = settings["max_segments_for_cross_speaker"]
        print("\n[bold cyan]🎯 Semantic Analysis Profile Selection[/bold cyan]")
        print("[dim]Choose a profile optimized for your conversation type:[/dim]")
        profile_choice = questionary.select(
            "Select semantic analysis profile:",
            choices=[
                questionary.Choice(
                    title="⚖️ Balanced (Recommended) - General purpose - good for most conversations",
                    value="balanced",
                ),
                questionary.Choice(
                    title="🎓 Academic - Optimized for research discussions and presentations",
                    value="academic",
                ),
                questionary.Choice(
                    title="💼 Business - Focused on meetings and professional discourse",
                    value="business",
                ),
                questionary.Choice(
                    title="😊 Casual - Suited for informal conversations and chats",
                    value="casual",
                ),
                questionary.Choice(
                    title="🔧 Technical - Enhanced for technical discussions and troubleshooting",
                    value="technical",
                ),
                questionary.Choice(
                    title="🎤 Interview - Optimized for job interviews, Q&A sessions, and structured conversations",
                    value="interview",
                ),
            ],
            default="balanced",
        ).ask()
        if profile_choice is None:
            print("\n[cyan]Cancelled.[/cyan]")
            raise KeyboardInterrupt()
        config.analysis.quality_filtering_profile = profile_choice
        profile_descriptions = {
            "balanced": "Balanced scoring for general conversations",
            "academic": "Optimized for academic discussions, research presentations, and debates",
            "business": "Optimized for business meetings, negotiations, and professional discussions",
            "casual": "Optimized for casual conversations, social discussions, and informal chats",
            "technical": "Optimized for technical discussions, code reviews, and troubleshooting sessions",
            "interview": "Optimized for job interviews, Q&A sessions, and structured conversations",
        }
        print(f"\n[green]✅ Selected profile: {profile_choice.title()}[/green]")
        print(
            f"[dim]{profile_descriptions.get(profile_choice, 'Unknown profile')}[/dim]"
        )
        print(f"\n[dim]Applied {mode} analysis settings to configuration[/dim]")


def apply_analysis_mode_settings_non_interactive(mode: str, profile: str | None = None):
    """
    Apply analysis mode settings without interactive prompts.

    Args:
        mode: Analysis mode - 'quick' or 'full'
        profile: Semantic profile for full mode - 'balanced', 'academic', 'business',
                 'casual', 'technical', 'interview' (only used with mode='full')
    """
    config = get_config()
    if mode == "quick":
        settings = config.analysis.quick_analysis_settings
        config.analysis.analysis_mode = "quick"
        config.analysis.semantic_similarity_method = settings["semantic_method"]
        config.analysis.max_segments_for_semantic = settings[
            "max_segments_for_semantic"
        ]
        config.analysis.max_semantic_comparisons = settings["max_semantic_comparisons"]
        config.analysis.ner_use_light_model = settings["ner_use_light_model"]
        config.analysis.ner_max_segments = settings["ner_max_segments"]
        config.analysis.ner_include_geocoding = not settings["skip_geocoding"]
        config.analysis.quality_filtering_profile = settings["semantic_profile"]
    else:
        settings = config.analysis.full_analysis_settings
        config.analysis.analysis_mode = "full"
        config.analysis.semantic_similarity_method = settings["semantic_method"]
        config.analysis.max_segments_for_semantic = settings[
            "max_segments_for_semantic"
        ]
        config.analysis.max_semantic_comparisons = settings["max_semantic_comparisons"]
        config.analysis.ner_use_light_model = settings["ner_use_light_model"]
        config.analysis.ner_max_segments = settings["ner_max_segments"]
        config.analysis.ner_include_geocoding = not settings["skip_geocoding"]
        # Apply increased segment limits for full mode
        if "max_segments_per_speaker" in settings:
            config.analysis.max_segments_per_speaker = settings["max_segments_per_speaker"]
        if "max_segments_for_cross_speaker" in settings:
            config.analysis.max_segments_for_cross_speaker = settings["max_segments_for_cross_speaker"]
        # Use provided profile or default to balanced
        profile_choice = profile or "balanced"
        if profile_choice not in [
            "balanced",
            "academic",
            "business",
            "casual",
            "technical",
            "interview",
        ]:
            profile_choice = "balanced"
        config.analysis.quality_filtering_profile = profile_choice


def filter_modules_by_mode(modules: list[str], mode: str) -> list[str]:
    config = get_config()
    if mode == "quick":
        settings = config.analysis.quick_analysis_settings
        if settings.get("skip_advanced_semantic", True):
            filtered_modules = [
                m for m in modules if m != "semantic_similarity_advanced"
            ]
            if (
                "semantic_similarity_advanced" in modules
                and "semantic_similarity" not in filtered_modules
            ):
                filtered_modules.append("semantic_similarity")
            return filtered_modules
    else:
        return modules
    return modules
