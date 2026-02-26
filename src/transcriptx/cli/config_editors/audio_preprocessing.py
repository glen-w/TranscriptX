"""Audio preprocessing configuration editor."""

import questionary
from rich import print

from transcriptx.cli.settings import (
    SettingItem,
    create_bool_editor,
    create_choice_editor,
    create_float_editor,
    create_int_editor,
    settings_menu_loop,
)
from ._dirty_tracker import is_dirty, mark_dirty


def _select_preprocessing_mode(
    prompt: str, current_mode: str, help_text: str = ""
) -> str:
    """Helper to select preprocessing mode (auto/suggest/off)."""
    choices = [
        ("auto", "🚀 Auto - Always apply if needed"),
        ("suggest", "💡 Suggest - Assess and suggest to user"),
        ("off", "❌ Off - Never apply"),
    ]

    current_choice = None
    for value, label in choices:
        if value == current_mode:
            current_choice = label
            break

    if help_text:
        print(f"[dim]{help_text}[/dim]")

    selected = questionary.select(
        prompt,
        choices=[label for _, label in choices],
        default=current_choice or choices[0][1],
    ).ask()

    # Map back to value
    for value, label in choices:
        if label == selected:
            return value

    return current_mode  # Fallback


def edit_audio_preprocessing_config(config):
    """Edit audio preprocessing configuration."""
    preprocessing_choices = ["auto", "suggest", "off"]
    global_choices = ["selected", "auto", "suggest", "off"]

    def make_mode_editor(label: str, is_global: bool = False):
        def editor(item: SettingItem):
            if (
                not is_global
                and config.audio_preprocessing.preprocessing_mode != "selected"
            ):
                print("[yellow]⚠️  Global mode overrides per-step settings[/yellow]")
            return create_choice_editor(
                global_choices if is_global else preprocessing_choices,
                hint=label,
            )(item)

        return editor

    items = [
        SettingItem(
            order=1,
            key="audio_preprocessing.preprocessing_mode",
            label="Global preprocessing mode",
            getter=lambda: config.audio_preprocessing.preprocessing_mode,
            setter=lambda value: setattr(
                config.audio_preprocessing, "preprocessing_mode", value
            ),
            editor=make_mode_editor(
                "Global mode: selected/auto/suggest/off.", is_global=True
            ),
        ),
        SettingItem(
            order=2,
            key="audio_preprocessing.convert_to_mono",
            label="Convert to mono mode",
            getter=lambda: config.audio_preprocessing.convert_to_mono,
            setter=lambda value: setattr(
                config.audio_preprocessing, "convert_to_mono", value
            ),
            editor=make_mode_editor(
                "Auto: Always convert | Suggest: Assess and suggest | Off: Never convert"
            ),
        ),
        SettingItem(
            order=3,
            key="audio_preprocessing.downsample",
            label="Downsample mode",
            getter=lambda: config.audio_preprocessing.downsample,
            setter=lambda value: setattr(
                config.audio_preprocessing, "downsample", value
            ),
            editor=make_mode_editor(
                "Auto: Always downsample | Suggest: Assess and suggest | Off: Never downsample"
            ),
        ),
        SettingItem(
            order=4,
            key="audio_preprocessing.target_sample_rate",
            label="Target sample rate",
            getter=lambda: config.audio_preprocessing.target_sample_rate,
            setter=lambda value: setattr(
                config.audio_preprocessing, "target_sample_rate", value
            ),
            editor=create_int_editor(
                min_val=1, hint="Sample rate in Hz (e.g., 16000)."
            ),
        ),
        SettingItem(
            order=5,
            key="audio_preprocessing.skip_if_already_compliant",
            label="Skip if compliant",
            getter=lambda: config.audio_preprocessing.skip_if_already_compliant,
            setter=lambda value: setattr(
                config.audio_preprocessing, "skip_if_already_compliant", value
            ),
            editor=create_bool_editor(hint="Skip if audio already compliant."),
        ),
        SettingItem(
            order=6,
            key="audio_preprocessing.normalize_mode",
            label="Normalize mode",
            getter=lambda: config.audio_preprocessing.normalize_mode,
            setter=lambda value: setattr(
                config.audio_preprocessing, "normalize_mode", value
            ),
            editor=make_mode_editor(
                "Auto: Always normalize | Suggest: Assess and suggest | Off: Never normalize"
            ),
        ),
        SettingItem(
            order=7,
            key="audio_preprocessing.target_lufs",
            label="Target LUFS",
            getter=lambda: config.audio_preprocessing.target_lufs,
            setter=lambda value: setattr(
                config.audio_preprocessing, "target_lufs", value
            ),
            editor=create_float_editor(
                min_val=-20.0, max_val=-16.0, hint="Range: -20 to -16."
            ),
        ),
        SettingItem(
            order=8,
            key="audio_preprocessing.limiter_enabled",
            label="Limiter enabled",
            getter=lambda: config.audio_preprocessing.limiter_enabled,
            setter=lambda value: setattr(
                config.audio_preprocessing, "limiter_enabled", value
            ),
            editor=create_bool_editor(hint="Enable peak limiter."),
        ),
        SettingItem(
            order=9,
            key="audio_preprocessing.limiter_peak_db",
            label="Limiter peak (dB)",
            getter=lambda: config.audio_preprocessing.limiter_peak_db,
            setter=lambda value: setattr(
                config.audio_preprocessing, "limiter_peak_db", value
            ),
            editor=create_float_editor(hint="Peak limiter threshold in dB."),
        ),
        SettingItem(
            order=10,
            key="audio_preprocessing.denoise_mode",
            label="Denoise mode",
            getter=lambda: config.audio_preprocessing.denoise_mode,
            setter=lambda value: setattr(
                config.audio_preprocessing, "denoise_mode", value
            ),
            editor=make_mode_editor(
                "Auto: Always denoise | Suggest: Assess and suggest | Off: Never denoise"
            ),
        ),
        SettingItem(
            order=11,
            key="audio_preprocessing.denoise_strength",
            label="Denoise strength",
            getter=lambda: config.audio_preprocessing.denoise_strength,
            setter=lambda value: setattr(
                config.audio_preprocessing, "denoise_strength", value
            ),
            editor=create_choice_editor(
                ["low", "medium", "high"], hint="Select denoise strength."
            ),
        ),
        SettingItem(
            order=12,
            key="audio_preprocessing.highpass_mode",
            label="High-pass mode",
            getter=lambda: config.audio_preprocessing.highpass_mode,
            setter=lambda value: setattr(
                config.audio_preprocessing, "highpass_mode", value
            ),
            editor=make_mode_editor(
                "Auto: Always apply | Suggest: Assess and suggest | Off: Never apply"
            ),
        ),
        SettingItem(
            order=13,
            key="audio_preprocessing.highpass_cutoff",
            label="High-pass cutoff (Hz)",
            getter=lambda: config.audio_preprocessing.highpass_cutoff,
            setter=lambda value: setattr(
                config.audio_preprocessing, "highpass_cutoff", value
            ),
            editor=create_int_editor(min_val=70, max_val=100, hint="Range: 70-100 Hz."),
        ),
        SettingItem(
            order=14,
            key="audio_preprocessing.lowpass_mode",
            label="Low-pass mode",
            getter=lambda: config.audio_preprocessing.lowpass_mode,
            setter=lambda value: setattr(
                config.audio_preprocessing, "lowpass_mode", value
            ),
            editor=make_mode_editor(
                "Auto: Always apply | Suggest: Assess and suggest | Off: Never apply"
            ),
        ),
        SettingItem(
            order=15,
            key="audio_preprocessing.lowpass_cutoff",
            label="Low-pass cutoff (Hz)",
            getter=lambda: config.audio_preprocessing.lowpass_cutoff,
            setter=lambda value: setattr(
                config.audio_preprocessing, "lowpass_cutoff", value
            ),
            editor=create_int_editor(min_val=1, hint="Low-pass cutoff in Hz."),
        ),
        SettingItem(
            order=16,
            key="audio_preprocessing.bandpass_mode",
            label="Band-pass mode",
            getter=lambda: config.audio_preprocessing.bandpass_mode,
            setter=lambda value: setattr(
                config.audio_preprocessing, "bandpass_mode", value
            ),
            editor=make_mode_editor(
                "Auto: Always apply | Suggest: Assess and suggest | Off: Never apply"
            ),
        ),
        SettingItem(
            order=17,
            key="audio_preprocessing.bandpass_low",
            label="Band-pass low cutoff (Hz)",
            getter=lambda: config.audio_preprocessing.bandpass_low,
            setter=lambda value: setattr(
                config.audio_preprocessing, "bandpass_low", value
            ),
            editor=create_int_editor(min_val=1, hint="Low cutoff in Hz."),
        ),
        SettingItem(
            order=18,
            key="audio_preprocessing.bandpass_high",
            label="Band-pass high cutoff (Hz)",
            getter=lambda: config.audio_preprocessing.bandpass_high,
            setter=lambda value: setattr(
                config.audio_preprocessing, "bandpass_high", value
            ),
            editor=create_int_editor(min_val=1, hint="High cutoff in Hz."),
        ),
    ]

    settings_menu_loop(
        title="🎵 Audio Preprocessing Settings",
        items=items,
        on_back=lambda: None,
        dirty_tracker=is_dirty,
        mark_dirty=mark_dirty,
    )
