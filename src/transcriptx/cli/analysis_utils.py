import questionary
from rich import print
from transcriptx.core.utils.config import get_config
from transcriptx.cli.config_editor import edit_config_interactive
from transcriptx.core import get_available_modules, get_default_modules
from transcriptx.core.pipeline.module_registry import get_description, get_module_info
from transcriptx.core.utils.audio_availability import has_resolvable_audio
from transcriptx.core.analysis.voice.deps import check_voice_optional_deps
from transcriptx.core.analysis.selection import (
    apply_analysis_mode_settings as apply_analysis_mode_settings_core,
    filter_modules_by_mode,
)


def select_analysis_modules(transcript_paths: list | None = None) -> list[str]:
    available_modules = get_available_modules()
    sorted_modules = sorted(available_modules, key=lambda m: get_description(m) or "")

    audio_available = None
    if transcript_paths:
        audio_available = has_resolvable_audio(transcript_paths)
    voice_cfg = getattr(getattr(get_config(), "analysis", None), "voice", None)
    egemaps_enabled = bool(getattr(voice_cfg, "egemaps_enabled", True))
    deps = check_voice_optional_deps(egemaps_enabled=egemaps_enabled)
    missing_deps = deps.get("missing_optional_deps") if not deps.get("ok") else []

    def _dep_resolver(info):
        if not info.requires_audio:
            return True
        return not missing_deps

    # Build choices for multi-select (checkbox): special options then one per module.
    # Use checked=True to preselect "All modules"; checkbox does not accept default=[...].
    choices = [
        questionary.Choice(title="⚙️ Configure settings", value="settings"),
        questionary.Choice(
            title="🚀 All modules (recommended)", value="all", checked=True
        ),
    ]
    for i, module in enumerate(sorted_modules, 1):
        description = get_description(module) or module
        info = get_module_info(module)
        badges: list[str] = []
        if info:
            if info.requires_audio:
                badges.append("requires audio")
                if audio_available is False:
                    badges.append("audio missing")
                if missing_deps:
                    badges.append(f"deps missing: {', '.join(missing_deps)}")
            if info.cost_tier == "heavy":
                badges.append("heavy")
        badge_str = f" ({'; '.join(badges)})" if badges else ""
        choices.append(
            questionary.Choice(title=f"{i}. {description}{badge_str}", value=module)
        )

    while True:
        try:
            selection = questionary.checkbox(
                "\nSelect modules (Space to toggle, Enter to confirm)",
                choices=choices,
            ).ask()
            if selection is None:
                print("\n[cyan]Cancelled. Returning to previous menu.[/cyan]")
                return []
            if "settings" in selection:
                edit_config_interactive()
                continue
            selected_modules = [m for m in selection if m not in ("settings", "all")]
            if "all" in selection and not selected_modules:
                # Only "all" checked -> run recommended set from core
                selected = get_default_modules(
                    transcript_paths,
                    audio_resolver=has_resolvable_audio,
                    dep_resolver=_dep_resolver,
                )
                heavy = [
                    m
                    for m in selected
                    if (get_module_info(m) is not None)
                    and get_module_info(m).cost_tier == "heavy"
                ]
                if heavy:
                    print(
                        f"[yellow]⚠️ Heavy modules included: {', '.join(heavy)}[/yellow]"
                    )
                return selected
            if "all" in selection and selected_modules:
                # "All" and specific modules both checked -> use only the specific ones
                pass
            if not selected_modules:
                print("[yellow]No modules selected. Choose at least one or pick 'All modules'.[/yellow]")
                continue
            return selected_modules
        except KeyboardInterrupt:
            print("\n[cyan]Cancelled. Returning to previous menu.[/cyan]")
            return []


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


def apply_analysis_mode_settings(mode: str) -> None:
    """Interactive: prompt for mode (and profile if full), then apply via core."""
    if mode == "quick":
        apply_analysis_mode_settings_core(mode)
        print(f"\n[dim]Applied {mode} analysis settings to configuration[/dim]")
        return
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
    apply_analysis_mode_settings_core(mode, profile=profile_choice)
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


def apply_analysis_mode_settings_non_interactive(mode: str, profile: str | None = None) -> None:
    """
    Apply analysis mode settings without interactive prompts (delegates to core).

    Args:
        mode: Analysis mode - 'quick' or 'full'
        profile: Semantic profile for full mode (only used with mode='full')
    """
    apply_analysis_mode_settings_core(mode, profile=profile)
