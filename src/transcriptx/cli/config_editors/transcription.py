"""Transcription configuration editor."""

from __future__ import annotations

import questionary
from rich import print as rich_print

from typing import Callable, Optional, cast

from transcriptx.cli.settings import (
    SettingItem,
    create_bool_editor,
    create_choice_editor,
    create_int_editor,
    create_secret_editor,
    create_str_editor,
    settings_menu_loop,
)
from ._dirty_tracker import is_dirty, mark_dirty


def _create_language_editor() -> Callable[[SettingItem], str | None]:
    """Create a language editor for a global, explicit language code."""
    common_languages = [
        "en",
        "fr",
        "es",
        "de",
        "it",
        "pt",
        "ru",
        "ja",
        "zh",
        "ko",
        "ar",
        "hi",
        "nl",
        "sv",
        "pl",
        "tr",
        "custom",
    ]

    def editor(item: SettingItem) -> str | None:
        rich_print(
            "[dim]Select a global language for transcription. This is intentionally explicit (no auto-detect). 'custom' allows entering a language code.[/dim]"
        )
        current_value = item.getter()
        selection_choices = [
            questionary.Choice(title=str(lang), value=lang) for lang in common_languages
        ]
        default_value = (
            current_value
            if current_value in common_languages
            else ("custom" if current_value else "en")
        )

        try:
            selected = cast(
                Optional[str],
                questionary.select(
                f"Select {item.label.lower()}",
                choices=selection_choices,
                default=default_value,
                ).ask(),
            )

            if selected is None:
                return None

            if selected == "custom":
                # Prompt for custom language code
                custom_lang = cast(
                    Optional[str],
                    questionary.text(
                        "Enter language code (e.g., 'cs' for Czech, 'fi' for Finnish)",
                        default=current_value if current_value not in common_languages else "",
                    ).ask(),
                )
                if custom_lang is None or not custom_lang.strip():
                    return None
                return custom_lang.strip()

            return selected
        except KeyboardInterrupt:
            return None

    return editor


def edit_transcription_config(config) -> None:
    """Edit transcription configuration."""
    def _format_token(value: object) -> str:
        return "SET" if value else "NOT SET"

    items = [
        SettingItem(
            order=1,
            key="transcription.model_name",
            label="Model",
            getter=lambda: config.transcription.model_name,
            setter=lambda value: setattr(config.transcription, "model_name", value),
            editor=create_choice_editor(
                ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
                hint="Whisper model size.",
            ),
        ),
        SettingItem(
            order=2,
            key="transcription.compute_type",
            label="Compute type",
            getter=lambda: config.transcription.compute_type,
            setter=lambda value: setattr(config.transcription, "compute_type", value),
            editor=create_choice_editor(
                ["float16", "float32", "int8"],
                hint="Compute precision.",
            ),
        ),
        SettingItem(
            order=3,
            key="transcription.language",
            label="Language",
            getter=lambda: config.transcription.language or "en",
            setter=lambda value: setattr(config.transcription, "language", value or "en"),
            editor=_create_language_editor(),
        ),
        SettingItem(
            order=4,
            key="transcription.batch_size",
            label="Batch size",
            getter=lambda: config.transcription.batch_size,
            setter=lambda value: setattr(config.transcription, "batch_size", value),
            editor=create_int_editor(min_val=1, hint="Positive integer."),
        ),
        SettingItem(
            order=5,
            key="transcription.diarize",
            label="Speaker diarization",
            getter=lambda: config.transcription.diarize,
            setter=lambda value: setattr(config.transcription, "diarize", value),
            editor=create_bool_editor(hint="Enable speaker diarization."),
        ),
        SettingItem(
            order=6,
            key="transcription.min_speakers",
            label="Min speakers",
            getter=lambda: config.transcription.min_speakers,
            setter=lambda value: setattr(config.transcription, "min_speakers", value),
            editor=create_int_editor(min_val=1, hint="Minimum number of speakers."),
        ),
        SettingItem(
            order=7,
            key="transcription.max_speakers",
            label="Max speakers",
            getter=lambda: config.transcription.max_speakers,
            setter=lambda value: setattr(config.transcription, "max_speakers", value),
            editor=create_int_editor(min_val=1, hint="Maximum number of speakers; leave empty for no limit.", allow_none=True),
        ),
        SettingItem(
            order=8,
            key="transcription.model_download_policy",
            label="Model download policy",
            getter=lambda: config.transcription.model_download_policy,
            setter=lambda value: setattr(
                config.transcription, "model_download_policy", value
            ),
            editor=create_choice_editor(
                ["anonymous", "require_token"],
                hint="Require token or allow anonymous model downloads.",
            ),
        ),
        SettingItem(
            order=9,
            key="transcription.huggingface_token",
            label="HuggingFace token",
            getter=lambda: config.transcription.huggingface_token,
            setter=lambda value: setattr(config.transcription, "huggingface_token", value),
            editor=create_secret_editor(
                hint="Token for model downloads (required if policy is require_token)."
            ),
            formatter=_format_token,
        ),
    ]

    settings_menu_loop(
        title="🎧 Transcription Settings",
        items=items,
        on_back=lambda: None,
        dirty_tracker=is_dirty,
        mark_dirty=mark_dirty,
    )
