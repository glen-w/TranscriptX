from pathlib import Path

import questionary
from rich import print
from transcriptx.core.utils.config import get_config
from transcriptx.cli.config_editor import edit_config_interactive
from transcriptx.core import (
    get_available_modules,
    get_default_modules,
    is_extra_available,
)
from transcriptx.core.pipeline.module_registry import (
    effective_min_named_speakers,
    get_description,
    get_module_info,
)
from transcriptx.core.utils.audio_availability import has_resolvable_audio
from transcriptx.core.analysis.selection import (
    apply_analysis_mode_settings as apply_analysis_mode_settings_core,
    filter_modules_for_speaker_count,
)
from transcriptx.core.utils.speaker_extraction import count_named_speakers
from transcriptx.io import load_segments
from transcriptx.io.transcript_loader import extract_speaker_map_from_transcript
from transcriptx.cli.speaker_workflow import run_speaker_identification_on_paths

# Selection intent: "recommended" | "all_eligible" | "manual". Used to re-resolve
# modules after speaker identification so newly eligible modules are included.
MODULE_SELECTION_RECOMMENDED = "recommended"
MODULE_SELECTION_ALL_ELIGIBLE = "all_eligible"
MODULE_SELECTION_MANUAL = "manual"


def _named_speaker_count_for_path(path) -> int:
    """
    Return named speaker count for a transcript file, applying the file's
    speaker_map so SPEAKER_XX segment labels count as named when mapped.
    """
    path_str = str(path)
    segments = load_segments(path_str)
    speaker_map = extract_speaker_map_from_transcript(path_str)
    resolved = [dict(seg) for seg in segments]
    for seg in resolved:
        speaker = seg.get("speaker")
        if speaker is not None and speaker in speaker_map:
            seg["speaker"] = speaker_map[speaker]
    return count_named_speakers(resolved)


def resolve_modules_for_selection_kind(
    transcript_paths: list,
    selection_kind: str,
    *,
    for_group: bool = False,
) -> list[str]:
    """
    Return the module list for a given selection kind using current transcript state.
    Use after speaker identification to re-evaluate eligibility (e.g. more named speakers).
    """
    if selection_kind not in (
        MODULE_SELECTION_RECOMMENDED,
        MODULE_SELECTION_ALL_ELIGIBLE,
    ):
        return []
    available_modules = get_available_modules()
    audio_available = has_resolvable_audio(transcript_paths)
    counts: list[int] = []
    for path in transcript_paths:
        try:
            counts.append(_named_speaker_count_for_path(path))
        except Exception:
            continue
    named_speaker_count = min(counts) if counts else None

    def _eligible(info):
        if getattr(info, "post_processing_only", False):
            return False
        if for_group and not info.supports_group:
            return False
        if info.requires_audio and audio_available is False:
            return False
        return True

    if selection_kind == MODULE_SELECTION_RECOMMENDED:
        selected = get_default_modules(
            transcript_paths,
            audio_resolver=has_resolvable_audio,
            for_group=for_group,
        )
        if named_speaker_count is not None:
            selected = filter_modules_for_speaker_count(selected, named_speaker_count)
        return selected
    # all_eligible
    sorted_modules = sorted(available_modules, key=lambda m: get_description(m) or "")
    eligible_modules: list[str] = []
    for module in sorted_modules:
        info = get_module_info(module)
        if info and _eligible(info):
            eligible_modules.append(module)
    if named_speaker_count is not None:
        eligible_modules = filter_modules_for_speaker_count(
            eligible_modules, named_speaker_count
        )
    return [m for m in available_modules if m in eligible_modules]


def _module_display_name(module_id: str) -> str:
    """Return user-facing name: underscores as spaces (display only)."""
    return module_id.replace("_", " ")


def format_modules_columns(modules: list[str], columns: int = 4) -> str:
    """Format a list of module names in columns for clearer display (e.g. 4 columns)."""
    if not modules:
        return ""
    modules = sorted(modules)
    display = [_module_display_name(m) for m in modules]
    n = len(display)
    rows = (n + columns - 1) // columns
    # Distribute into columns: col 0 = first `rows` items, col 1 = next `rows`, etc.
    cols: list[list[str]] = []
    for c in range(columns):
        start = c * rows
        end = min(start + rows, n)
        cols.append(display[start:end])
    # Pad each column to max width within that column
    for c in range(columns):
        if cols[c]:
            width = max(len(x) for x in cols[c])
            cols[c] = [x.ljust(width) for x in cols[c]]
    # Pad column lengths so we can zip
    max_len = max(len(col) for col in cols)
    for c in range(columns):
        while len(cols[c]) < max_len:
            cols[c].append("")
    # Format row by row
    lines = []
    for r in range(max_len):
        line = "  ".join(cols[c][r] for c in range(columns)).rstrip()
        lines.append(line)
    return "\n".join(lines)


def select_analysis_modules(
    transcript_paths: list | None = None,
    *,
    for_group: bool = False,
) -> tuple[list[str], str]:
    available_modules = get_available_modules()
    sorted_modules = sorted(available_modules, key=lambda m: get_description(m) or "")

    audio_available = None
    named_speaker_count = None
    per_file_counts: list[tuple[str, int]] = []
    blocking_files: list[str] = []
    if transcript_paths:
        audio_available = has_resolvable_audio(transcript_paths)
        for path in transcript_paths:
            try:
                count = _named_speaker_count_for_path(path)
                per_file_counts.append((str(path), count))
            except Exception:
                per_file_counts.append((str(path), 0))
        if per_file_counts:
            named_speaker_count = min(c for _, c in per_file_counts)
            blocking_files = [Path(p).name for p, c in per_file_counts if c == 0]

    def _eligible(info):
        if getattr(info, "post_processing_only", False):
            return False
        if for_group and not info.supports_group:
            return False
        if info.requires_audio and audio_available is False:
            return False
        return True

    eligible_base: list[str] = []
    for module in sorted_modules:
        info = get_module_info(module)
        if info and _eligible(info):
            eligible_base.append(module)
    eligible_modules = list(eligible_base)
    if named_speaker_count is not None:
        eligible_modules = filter_modules_for_speaker_count(
            eligible_modules, named_speaker_count
        )
    # For 0 named speakers: modules available now vs unlocked after mapping (for user summary).
    modules_available_without_speakers: list[str] = []
    modules_unlocked_with_speakers: list[str] = []
    if named_speaker_count is not None and named_speaker_count < 1:
        modules_available_without_speakers = list(eligible_modules)
        modules_unlocked_with_speakers = [
            m for m in eligible_base if m not in eligible_modules
        ]

    # Modules to show in the list: all non–post-processing (and group-compatible if for_group).
    # Full list is always shown; ineligible ones are disabled with a reason.
    def _show_in_list(info):
        if not info:
            return True
        if getattr(info, "post_processing_only", False):
            return False
        if for_group and not info.supports_group:
            return False
        return True

    modules_to_display: list[str] = []
    for module in sorted_modules:
        info = get_module_info(module)
        if info and _show_in_list(info):
            modules_to_display.append(module)
        elif not info:
            modules_to_display.append(module)

    def _disabled_reason(module: str) -> str | None:
        """Return reason string if module is not runnable, else None."""
        info = get_module_info(module)
        if not info:
            return None
        if info.requires_audio and audio_available is False:
            return "requires audio"
        missing_extras = [
            e for e in (info.required_extras or []) if not is_extra_available(e)
        ]
        if missing_extras:
            return f"requires {', '.join(missing_extras)} (installs on first run)"
        if named_speaker_count is not None:
            min_required = effective_min_named_speakers(info)
            if named_speaker_count < min_required:
                if blocking_files:
                    return f"needs {min_required}+ named speakers (caused by: {', '.join(blocking_files)})"
                return f"needs {min_required}+ named speakers"
        return None

    # Inform user what's available with/without speaker identification and advise accordingly.
    if transcript_paths and len(per_file_counts) >= 1:
        lines = ["[bold]Speaker status[/bold]"]
        lines.append("Named speaker counts (file-based):")
        for p, c in per_file_counts:
            display_name = Path(p).name
            suffix = "  ← no names (limits which modules can run)" if c == 0 else ""
            lines.append(f"  {display_name}: {c}{suffix}")
        lines.append("")
        if named_speaker_count is not None and named_speaker_count < 1:
            n_now = len(modules_available_without_speakers)
            n_locked = len(modules_unlocked_with_speakers)
            if n_now > 0:
                names_now = ", ".join(
                    get_description(m) or _module_display_name(m)
                    for m in sorted(modules_available_without_speakers)[:8]
                )
                if n_now > 8:
                    names_now += f", … (+{n_now - 8} more)"
                lines.append(
                    f"[green]Available now[/green] (no speaker names): {n_now} module(s) — {names_now}"
                )
            else:
                lines.append(
                    "[yellow]Available now[/yellow] (no speaker names): 0 modules."
                )
            if n_locked > 0:
                names_locked = ", ".join(
                    get_description(m) or _module_display_name(m)
                    for m in sorted(modules_unlocked_with_speakers)[:8]
                )
                if n_locked > 8:
                    names_locked += f", … (+{n_locked - 8} more)"
                lines.append(
                    f"[cyan]Unlocked after speaker mapping[/cyan]: {n_locked} module(s) — {names_locked}"
                )
            lines.append("")
            if n_now > 0 and n_locked > 0:
                lines.append(
                    "[dim]You can run analysis now with the modules above, or map speakers first to enable per-speaker analysis.[/dim]"
                )
            elif n_now == 0 and n_locked > 0:
                lines.append(
                    "[dim]Map speakers first (option below) to enable analysis modules.[/dim]"
                )
            elif n_now > 0:
                lines.append("[dim]No extra modules require speaker names.[/dim]")
        else:
            lines.append(f"Effective named speaker count (min): {named_speaker_count}")
        print("\n".join(lines))

    # Full paths for transcripts with 0 named speakers (for "run speaker mapping" option).
    blocking_paths = [p for (p, c) in per_file_counts if c == 0]

    # First ask scope with a single-choice menu so "Recommended" and "All eligible" are mutually exclusive.
    no_eligible_due_to_speakers = (
        named_speaker_count is not None
        and named_speaker_count < 1
        and len(eligible_modules) == 0
    )
    scope_choices = [
        questionary.Choice(
            title="⭐ Recommended modules (default set)",
            value="recommended",
            shortcut_key=False,
        ),
    ]
    if no_eligible_due_to_speakers:
        scope_choices.append(
            questionary.Choice(
                title="📚 All eligible modules (none — map speakers first)",
                value="all_eligible",
                shortcut_key=False,
                disabled="0 named speakers; no modules eligible",
            )
        )
    else:
        scope_choices.append(
            questionary.Choice(
                title="📚 All eligible modules",
                value="all_eligible",
                shortcut_key=False,
            )
        )
    scope_choices.append(
        questionary.Choice(
            title="✏️ Choose modules manually",
            value="manual",
            shortcut_key=False,
        ),
    )
    if blocking_paths:
        scope_choices.append(
            questionary.Choice(
                title="🗣️ Map speakers on transcript(s) without names (unlock full modules)",
                value="run_speaker_mapping",
                shortcut_key=False,
            )
        )
    while True:
        try:
            scope = questionary.select(
                "\nHow do you want to select modules?",
                choices=scope_choices,
                default="recommended",
            ).ask()
            if scope is None:
                print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
                return ([], MODULE_SELECTION_MANUAL)
            if scope == "recommended":
                selected = get_default_modules(
                    transcript_paths,
                    audio_resolver=has_resolvable_audio,
                    for_group=for_group,
                )
                if named_speaker_count is not None:
                    selected = filter_modules_for_speaker_count(
                        selected, named_speaker_count
                    )
                if not selected and no_eligible_due_to_speakers:
                    print(
                        "\n[yellow]No recommended modules are available with 0 named speakers.[/yellow]"
                    )
                    print(
                        "[dim]Map speakers first (option below), or choose 'Choose modules manually' to see modules and their requirements.[/dim]"
                    )
                    continue
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
                return (selected, MODULE_SELECTION_RECOMMENDED)
            if scope == "all_eligible":
                return (
                    [m for m in available_modules if m in eligible_modules],
                    MODULE_SELECTION_ALL_ELIGIBLE,
                )
            if scope == "run_speaker_mapping":
                updated_blocking = run_speaker_identification_on_paths(blocking_paths)
                updated_map = dict(zip(blocking_paths, updated_blocking))
                updated_transcript_paths = [
                    updated_map.get(str(p), str(p)) for p in transcript_paths
                ]
                return select_analysis_modules(
                    updated_transcript_paths, for_group=for_group
                )
            # scope == "manual": show checkbox with Configure settings + module list only
            break
        except KeyboardInterrupt:
            print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
            return ([], MODULE_SELECTION_MANUAL)

    # Build choices for manual multi-select: settings then full module list.
    # Disable shortcut_key to avoid questionary IndexError when choices exceed its ~36 shortcut keys.
    manual_choices: list = [
        questionary.Choice(
            title="⚙️ Configure settings", value="settings", shortcut_key=False
        ),
    ]
    for i, module in enumerate(modules_to_display, 1):
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
        title = f"{i}. {description}{badge_str}"
        disabled_reason = _disabled_reason(module)
        choice_kw: dict = {"title": title, "value": module, "shortcut_key": False}
        if disabled_reason:
            choice_kw["disabled"] = disabled_reason
        manual_choices.append(questionary.Choice(**choice_kw))

    while True:
        try:
            selection = questionary.checkbox(
                "\nSelect modules (Space to toggle, Enter to confirm)",
                choices=manual_choices,
            ).ask()
            if selection is None:
                print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
                return ([], MODULE_SELECTION_MANUAL)
            if "settings" in selection:
                edit_config_interactive()
                continue
            selected_modules = [m for m in selection if m != "settings"]
            if not selected_modules:
                print(
                    "[yellow]No modules selected. Choose at least one (or use 'Configure settings' then try again).[/yellow]"
                )
                continue
            return (selected_modules, MODULE_SELECTION_MANUAL)
        except KeyboardInterrupt:
            print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
            return ([], MODULE_SELECTION_MANUAL)


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
    config = get_config()
    if hasattr(config, "analysis"):
        config.analysis.analysis_mode = mode
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
    print(f"[dim]{profile_descriptions.get(profile_choice, 'Unknown profile')}[/dim]")
    print(f"\n[dim]Applied {mode} analysis settings to configuration[/dim]")


def apply_analysis_mode_settings_non_interactive(
    mode: str, profile: str | None = None
) -> None:
    """
    Apply analysis mode settings without interactive prompts (delegates to core).

    Args:
        mode: Analysis mode - 'quick' or 'full'
        profile: Semantic profile for full mode (only used with mode='full')
    """
    apply_analysis_mode_settings_core(mode, profile=profile)
