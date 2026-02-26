"""
Speaker Management Module for TranscriptX CLI.

This module provides comprehensive speaker management functionality, including:
- Viewing speakers in alphabetical order
- Editing speaker information (name, notes, etc.)
- Viewing transcripts containing a speaker
- Adding new speakers

Key Features:
- Interactive speaker selection and management
- Database-driven speaker operations
- User-friendly interface with rich formatting
- Graceful error handling
"""

from typing import Set
from collections import defaultdict

import questionary
from rich import print
from rich.table import Table

from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.database import init_database, get_session
from transcriptx.database.repositories import (
    SpeakerRepository,
    TranscriptSegmentRepository,
    TranscriptFileRepository,
)
from .speaker_workflow import run_speaker_identification_workflow

logger = get_logger()


def _show_speaker_management_menu() -> None:
    """Display and handle speaker management main menu."""
    while True:
        try:
            choice = questionary.select(
                "Speaker Management",
                choices=[
                    "🗣️ Identify Speakers",
                    "👥 Manage Speakers",
                    "⬅️ Back to main menu",
                ],
            ).ask()
        except KeyboardInterrupt:
            print("\n[cyan]Returning to main menu...[/cyan]")
            break

        if choice == "🗣️ Identify Speakers":
            run_speaker_identification_workflow()
        elif choice == "👥 Manage Speakers":
            _show_manage_speakers_menu()
        elif choice == "⬅️ Back to main menu":
            break


def _show_manage_speakers_menu() -> None:
    """Display and handle manage speakers submenu."""
    while True:
        try:
            choice = questionary.select(
                "Manage Speakers",
                choices=[
                    "📋 View Speakers",
                    "🔍 Select Speaker",
                    "➕ Add New Speaker",
                    "⬅️ Back",
                ],
            ).ask()
        except KeyboardInterrupt:
            print("\n[cyan]Returning to speaker management menu...[/cyan]")
            break

        if choice == "📋 View Speakers":
            _view_speakers_list()
        elif choice == "🔍 Select Speaker":
            _select_and_manage_speaker()
        elif choice == "➕ Add New Speaker":
            _add_new_speaker()
        elif choice == "⬅️ Back":
            break


def _view_speakers_list() -> None:
    """Display alphabetical list of all speakers."""
    try:
        init_database()
        session = get_session()
        try:
            speaker_repo = SpeakerRepository(session)
            speakers = speaker_repo.find_speakers(active_only=True)

            if not speakers:
                print("\n[yellow]No speakers found in database.[/yellow]")
                print(
                    "[cyan]Use 'Identify Speakers' to create speakers from transcripts.[/cyan]"
                )
                return

            print("\n[bold cyan]📋 Speakers List[/bold cyan]")
            print(f"[dim]Found {len(speakers)} active speaker(s)[/dim]\n")

            # Create a table for better display
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID", style="dim", width=6)
            table.add_column("Name", style="cyan", width=30)
            table.add_column("Display Name", style="green", width=30)
            table.add_column("Email", style="yellow", width=25)
            table.add_column("Organization", style="blue", width=20)

            for speaker in speakers:
                table.add_row(
                    str(speaker.id),
                    speaker.name,
                    speaker.display_name or "-",
                    speaker.email or "-",
                    speaker.organization or "-",
                )

            print(table)
            print()

        finally:
            session.close()

    except Exception as e:
        log_error("CLI", f"Failed to view speakers list: {e}", exception=e)
        print(f"[red]❌ Failed to view speakers: {e}[/red]")


def _select_and_manage_speaker() -> None:
    """Select a speaker and show management options."""
    try:
        init_database()
        session = get_session()
        try:
            speaker_repo = SpeakerRepository(session)
            speakers = speaker_repo.find_speakers(active_only=True)

            if not speakers:
                print("\n[yellow]No speakers found in database.[/yellow]")
                print(
                    "[cyan]Use 'Identify Speakers' to create speakers from transcripts.[/cyan]"
                )
                return

            # Create choices with speaker name and ID
            choices = [f"{speaker.name} (ID: {speaker.id})" for speaker in speakers]
            choices.append("⬅️ Back")

            selection = questionary.select(
                "Select a speaker:",
                choices=choices,
            ).ask()

            if not selection or selection == "⬅️ Back":
                return

            # Extract speaker ID from selection
            try:
                speaker_id = int(selection.split("(ID: ")[1].split(")")[0])
            except (IndexError, ValueError):
                print("[red]❌ Failed to parse speaker ID[/red]")
                return

            speaker = speaker_repo.get_speaker_by_id(speaker_id)
            if not speaker:
                print(f"[red]❌ Speaker with ID {speaker_id} not found[/red]")
                return

            # Show speaker management options
            _show_speaker_actions_menu(speaker)

        finally:
            session.close()

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled.[/cyan]")
    except Exception as e:
        log_error("CLI", f"Failed to select speaker: {e}", exception=e)
        print(f"[red]❌ Failed to select speaker: {e}[/red]")


def _show_speaker_actions_menu(speaker) -> None:
    """Show actions menu for a selected speaker."""
    while True:
        try:
            print(f"\n[bold cyan]Speaker: {speaker.name}[/bold cyan]")
            if speaker.display_name:
                print(f"[dim]Display Name: {speaker.display_name}[/dim]")
            if speaker.personal_note:
                print(f"[dim]Note: {speaker.personal_note}[/dim]")
            if speaker.email:
                print(f"[dim]Email: {speaker.email}[/dim]")
            if speaker.organization:
                print(f"[dim]Organization: {speaker.organization}[/dim]")
            if speaker.role:
                print(f"[dim]Role: {speaker.role}[/dim]")

            choice = questionary.select(
                "What would you like to do?",
                choices=[
                    "✏️ Edit Name/Notes",
                    "📄 View Transcripts",
                    "⬅️ Back",
                ],
            ).ask()

            if choice == "✏️ Edit Name/Notes":
                _edit_speaker_info(speaker)
            elif choice == "📄 View Transcripts":
                _view_speaker_transcripts(speaker)
            elif choice == "⬅️ Back":
                break

        except KeyboardInterrupt:
            print("\n[cyan]Returning to speaker selection...[/cyan]")
            break


def _edit_speaker_info(speaker) -> None:
    """Edit speaker information (name, notes, etc.)."""
    try:
        init_database()
        session = get_session()
        try:
            speaker_repo = SpeakerRepository(session)

            # Refresh speaker from database
            speaker = speaker_repo.get_speaker_by_id(speaker.id)
            if not speaker:
                print("[red]❌ Speaker not found[/red]")
                return

            print(f"\n[bold cyan]Editing: {speaker.name}[/bold cyan]")
            print("[dim]Press Enter to keep current value, or type new value[/dim]\n")

            # Get current values
            current_name = speaker.name
            current_display_name = speaker.display_name or ""
            current_personal_note = speaker.personal_note or ""
            current_email = speaker.email or ""
            current_organization = speaker.organization or ""
            current_role = speaker.role or ""

            # Prompt for new values
            new_name = questionary.text(
                f"Name [{current_name}]:",
                default=current_name,
            ).ask()

            new_display_name = questionary.text(
                f"Display Name [{current_display_name}]:",
                default=current_display_name,
            ).ask()

            new_personal_note = questionary.text(
                f"Personal Note [{current_personal_note}]:",
                default=current_personal_note,
            ).ask()

            new_email = questionary.text(
                f"Email [{current_email}]:",
                default=current_email,
            ).ask()

            new_organization = questionary.text(
                f"Organization [{current_organization}]:",
                default=current_organization,
            ).ask()

            new_role = questionary.text(
                f"Role [{current_role}]:",
                default=current_role,
            ).ask()

            # Validate name is not empty
            if not new_name or not new_name.strip():
                print("[red]❌ Name cannot be empty[/red]")
                return

            # Prepare update dictionary
            update_data = {
                "name": new_name.strip(),
                "display_name": (
                    new_display_name.strip() if new_display_name.strip() else None
                ),
                "personal_note": (
                    new_personal_note.strip() if new_personal_note.strip() else None
                ),
                "email": new_email.strip() if new_email.strip() else None,
                "organization": (
                    new_organization.strip() if new_organization.strip() else None
                ),
                "role": new_role.strip() if new_role.strip() else None,
            }

            # Update speaker
            updated_speaker = speaker_repo.update_speaker(speaker.id, **update_data)

            if updated_speaker:
                print("\n[green]✅ Speaker updated successfully![/green]")
                print(f"[cyan]Name: {updated_speaker.name}[/cyan]")
            else:
                print("[red]❌ Failed to update speaker[/red]")

        finally:
            session.close()

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled.[/cyan]")
    except Exception as e:
        log_error("CLI", f"Failed to edit speaker: {e}", exception=e)
        print(f"[red]❌ Failed to edit speaker: {e}[/red]")


def _view_speaker_transcripts(speaker) -> None:
    """Show list of transcripts containing the speaker."""
    try:
        init_database()
        session = get_session()
        try:
            segment_repo = TranscriptSegmentRepository(session)
            file_repo = TranscriptFileRepository(session)

            # Get all segments for this speaker
            segments = segment_repo.get_segments_by_speaker(speaker.id)

            # If no database segments found, search JSON transcript files
            if not segments:
                logger.info(
                    f"No database segments found for {speaker.name}, searching JSON files..."
                )
                transcripts_found = _search_transcripts_in_json_files(speaker)

                if transcripts_found:
                    return
                else:
                    print(
                        f"\n[yellow]No transcripts found for speaker: {speaker.name}[/yellow]"
                    )
                    print(
                        "[dim]Note: Transcripts may need to be imported into the database.[/dim]"
                    )
                    return

            # Get unique transcript file IDs
            transcript_file_ids: Set[int] = {seg.transcript_file_id for seg in segments}

            # Get transcript files
            transcript_files = []
            for file_id in transcript_file_ids:
                transcript_file = file_repo.get_transcript_file_by_id(file_id)
                if transcript_file:
                    transcript_files.append(transcript_file)

            # Count segments per transcript
            segments_per_file = defaultdict(int)
            for seg in segments:
                segments_per_file[seg.transcript_file_id] += 1

            print(f"\n[bold cyan]📄 Transcripts for: {speaker.name}[/bold cyan]")
            print(
                f"[dim]Found {len(transcript_files)} transcript(s) with {len(segments)} total segment(s)[/dim]\n"
            )

            # Create a table
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("File Name", style="cyan", width=40)
            table.add_column("Path", style="dim", width=50)
            table.add_column("Segments", style="green", width=10)

            for transcript_file in sorted(
                transcript_files, key=lambda f: f.file_name.lower()
            ):
                segment_count = segments_per_file[transcript_file.id]
                # Truncate path if too long
                path_display = transcript_file.file_path
                if len(path_display) > 50:
                    path_display = "..." + path_display[-47:]

                table.add_row(
                    transcript_file.file_name,
                    path_display,
                    str(segment_count),
                )

            print(table)
            print()

        finally:
            session.close()

    except Exception as e:
        log_error("CLI", f"Failed to view speaker transcripts: {e}", exception=e)
        print(f"[red]❌ Failed to view transcripts: {e}[/red]")


def _search_transcripts_in_json_files(speaker) -> bool:
    """
    Search for transcripts containing the speaker in JSON files.

    Args:
        speaker: Speaker object from database

    Returns:
        True if transcripts were found and displayed, False otherwise
    """
    try:
        from pathlib import Path
        from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR, OUTPUTS_DIR
        from transcriptx.io.transcript_loader import load_segments

        transcripts_dir = Path(DIARISED_TRANSCRIPTS_DIR)
        outputs_dir = Path(OUTPUTS_DIR)
        if not transcripts_dir.exists():
            return False

        # Get possible speaker name variations to match
        speaker_names = {speaker.name}
        if speaker.display_name:
            speaker_names.add(speaker.display_name)
        # Also check first_name and surname if available
        if hasattr(speaker, "first_name") and speaker.first_name:
            speaker_names.add(speaker.first_name)
        if hasattr(speaker, "surname") and speaker.surname:
            speaker_names.add(speaker.surname)
            # Also try first_name + surname combination
            if hasattr(speaker, "first_name") and speaker.first_name:
                speaker_names.add(f"{speaker.first_name} {speaker.surname}")

        # Search all JSON files in transcripts directory
        transcript_files = list(transcripts_dir.glob("*.json"))
        matching_transcripts = []

        for transcript_file in transcript_files:
            try:
                segments = load_segments(str(transcript_file))
                if not segments:
                    continue

                # Use database-driven speaker extraction
                from transcriptx.core.utils.speaker_extraction import (
                    extract_speaker_info,
                    get_speaker_display_name,
                )

                # Check if any segment has this speaker
                matching_segments = []
                for seg in segments:
                    # Extract speaker info using database-driven approach
                    speaker_info = extract_speaker_info(seg)
                    if speaker_info is None:
                        continue

                    # Get display name
                    display_name = get_speaker_display_name(
                        speaker_info.grouping_key, [seg], segments
                    )

                    # Check if display name matches any of the search names
                    if display_name in speaker_names:
                        matching_segments.append(seg)
                        continue

                    # Also check the raw speaker field as fallback
                    seg_speaker = seg.get("speaker")
                    if seg_speaker and str(seg_speaker) in speaker_names:
                        matching_segments.append(seg)

                if matching_segments:
                    matching_transcripts.append(
                        {
                            "file": transcript_file,
                            "segments": matching_segments,
                            "total_segments": len(segments),
                        }
                    )
            except Exception as e:
                logger.debug(f"Failed to load {transcript_file}: {e}")
                continue

        if not matching_transcripts:
            return False

        # Display results
        print(f"\n[bold cyan]📄 Transcripts for: {speaker.name}[/bold cyan]")
        print(
            f"[dim]Found {len(matching_transcripts)} transcript(s) in JSON files[/dim]"
        )
        print(
            "[yellow]Note: These transcripts are not yet stored in the database.[/yellow]\n"
        )

        # Create a table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("File Name", style="cyan", width=40)
        table.add_column("Path", style="dim", width=50)
        table.add_column("Segments", style="green", width=10)

        for match in sorted(matching_transcripts, key=lambda m: m["file"].name.lower()):
            file_path = str(match["file"])
            # Truncate path if too long
            path_display = file_path
            if len(path_display) > 50:
                path_display = "..." + path_display[-47:]

            table.add_row(
                match["file"].name,
                path_display,
                str(len(match["segments"])),
            )

        print(table)
        print()
        return True

    except Exception as e:
        logger.error(f"Failed to search JSON transcript files: {e}")
        return False


def _add_new_speaker() -> None:
    """Interactive speaker creation."""
    try:
        init_database()
        session = get_session()
        try:
            speaker_repo = SpeakerRepository(session)

            print("\n[bold cyan]➕ Add New Speaker[/bold cyan]\n")

            # Prompt for required fields
            name = questionary.text(
                "Name (required):",
                validate=lambda text: len(text.strip()) > 0 if text else False,
            ).ask()

            if not name or not name.strip():
                print("[red]❌ Name is required. Cancelled.[/red]")
                return

            # Prompt for optional fields
            display_name = questionary.text(
                "Display Name (optional):",
            ).ask()

            personal_note = questionary.text(
                "Personal Note (optional):",
            ).ask()

            email = questionary.text(
                "Email (optional):",
            ).ask()

            organization = questionary.text(
                "Organization (optional):",
            ).ask()

            role = questionary.text(
                "Role (optional):",
            ).ask()

            # Create speaker
            new_speaker = speaker_repo.create_speaker(
                name=name.strip(),
                display_name=(
                    display_name.strip()
                    if display_name and display_name.strip()
                    else None
                ),
                personal_note=(
                    personal_note.strip()
                    if personal_note and personal_note.strip()
                    else None
                ),
                email=email.strip() if email and email.strip() else None,
                organization=(
                    organization.strip()
                    if organization and organization.strip()
                    else None
                ),
                role=role.strip() if role and role.strip() else None,
            )

            if new_speaker:
                print("\n[green]✅ Speaker created successfully![/green]")
                print(f"[cyan]Name: {new_speaker.name}[/cyan]")
                print(f"[cyan]ID: {new_speaker.id}[/cyan]")
            else:
                print("[red]❌ Failed to create speaker[/red]")

        finally:
            session.close()

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled.[/cyan]")
    except Exception as e:
        log_error("CLI", f"Failed to add speaker: {e}", exception=e)
        print(f"[red]❌ Failed to add speaker: {e}[/red]")
