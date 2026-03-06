"""Speaker mapping module."""

from typing import Optional

import questionary
from colorama import Fore, init
from rich.console import Console

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.speaker import (
    parse_speaker_name,
    format_speaker_display_name,
)
from .utils import _is_test_environment

# Lazy imports to avoid circular dependencies:
# - choose_mapping_action imported in load_or_create_speaker_map
# - offer_and_edit_tags imported in load_or_create_speaker_map

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# Color cycle for speaker identification
# Each speaker gets a distinct color during the mapping process
COLOR_CYCLE = [
    Fore.CYAN,
    Fore.MAGENTA,
    Fore.YELLOW,
    Fore.GREEN,
    Fore.BLUE,
    Fore.LIGHTRED_EX,
]

console = Console()
logger = get_logger()


def _create_or_link_speaker_with_disambiguation(
    full_name: str, batch_mode: bool = False
) -> tuple[Optional[int], str]:
    """
    Create or link to a speaker in the database with disambiguation support.

    Parses the name, checks for duplicates, and handles disambiguation if needed.

    Args:
        full_name: Full name entered by user
        batch_mode: If True, skip interactive prompts

    Returns:
        Tuple of (speaker_db_id, display_name) where speaker_db_id may be None
    """
    try:
        from transcriptx.database import get_session
        from transcriptx.database.repositories import SpeakerRepository

        # Parse name into first_name and surname
        first_name, surname = parse_speaker_name(full_name)

        if not first_name:
            # Invalid name, return None
            return None, full_name

        # Get database session and repository
        session = get_session()
        speaker_repo = SpeakerRepository(session)

        # Check for duplicates
        existing_speakers = speaker_repo.find_speakers_by_name(
            first_name, surname, active_only=True
        )

        if existing_speakers and not batch_mode and not _is_test_environment():
            # Duplicates found - show disambiguation UI
            console.print(f'\n⚠️  Found existing speakers with name "{full_name}":')
            for idx, speaker in enumerate(existing_speakers, 1):
                note = speaker.personal_note or "(no note)"
                display = format_speaker_display_name(
                    first_name=speaker.first_name,
                    surname=speaker.surname,
                    display_name=speaker.display_name,
                    name=speaker.name,
                )
                console.print(f'  {idx}. {display} - Note: "{note}"')

            choices = [
                f"Select existing speaker {i}"
                for i in range(1, len(existing_speakers) + 1)
            ]
            choices.append("Create new person")

            action = questionary.select(
                "\nIs this the same person?", choices=choices
            ).ask()

            if action.startswith("Select existing"):
                # User selected an existing speaker
                idx = int(action.split()[-1]) - 1
                selected_speaker = existing_speakers[idx]
                display_name = format_speaker_display_name(
                    first_name=selected_speaker.first_name,
                    surname=selected_speaker.surname,
                    display_name=selected_speaker.display_name,
                    name=selected_speaker.name,
                )
                return selected_speaker.id, display_name
            else:
                # User wants to create new person - prompt for personal note
                personal_note = (
                    questionary.text(
                        "Enter a note to help identify this person (e.g., 'Works in Sales', 'Client from XYZ Corp'):",
                        default="",
                    )
                    .ask()
                    .strip()
                )
        elif existing_speakers and (batch_mode or _is_test_environment()):
            # In batch/test mode, just use the first existing speaker
            selected_speaker = existing_speakers[0]
            display_name = format_speaker_display_name(
                first_name=selected_speaker.first_name,
                surname=selected_speaker.surname,
                display_name=selected_speaker.display_name,
                name=selected_speaker.name,
            )
            return selected_speaker.id, display_name
        else:
            # No duplicates - create new speaker
            personal_note = None
            if not batch_mode and not _is_test_environment():
                personal_note = (
                    questionary.text(
                        "Enter a note to help identify this person (optional, press Enter to skip):",
                        default="",
                    )
                    .ask()
                    .strip()
                    or None
                )

        # Create new speaker
        display_name = format_speaker_display_name(
            first_name=first_name, surname=surname, name=full_name
        )

        speaker = speaker_repo.create_speaker(
            name=full_name,
            display_name=display_name,
            first_name=first_name,
            surname=surname,
            personal_note=personal_note,
        )

        return speaker.id, display_name

    except Exception as e:
        logger.error(f"❌ Failed to create/link speaker: {e}")
        # Fallback: return None and use the name as-is
        return None, full_name
