"""
Transcript management CLI commands for TranscriptX.

This module provides CLI commands for managing transcripts in the database,
including listing conversations, viewing details, and managing transcript data.

The commands support:
- Listing all conversations with filtering
- Viewing conversation details and summaries
- Managing transcript metadata
- Deleting conversations and associated data
- Exporting conversation data
"""

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from transcriptx.core.utils.logger import get_logger

logger = get_logger()
console = Console()

app = typer.Typer(
    name="transcript",
    help="Transcript management commands for TranscriptX",
    no_args_is_help=True,
)


def _get_transcript_manager():
    from transcriptx.database.database import init_database
    from transcriptx.database.transcript_manager import TranscriptManager

    init_database()
    return TranscriptManager()


@app.command()
def list(
    limit: Optional[int] = typer.Option(
        None, "--limit", "-l", help="Maximum number of conversations to show"
    ),
    status: Optional[str] = typer.Option(
        None, "--status", "-s", help="Filter by analysis status"
    ),
    show_details: bool = typer.Option(
        False, "--details", "-d", help="Show detailed information"
    ),
):
    """List all conversations in the database."""
    try:
        transcript_manager = _get_transcript_manager()

        # Get conversations
        conversations = transcript_manager.list_conversations(
            limit=limit, status_filter=status
        )

        if not conversations:
            console.print("📭 No conversations found in database")
            return

        # Create table
        table = Table(title="📋 Conversations in Database")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="green")
        table.add_column("Duration", style="yellow")
        table.add_column("Speakers", style="blue")
        table.add_column("Status", style="magenta")
        table.add_column("Created", style="dim")

        if show_details:
            table.add_column("Description", style="dim")
            table.add_column("Word Count", style="dim")

        # Add rows
        for conv in conversations:
            duration_min = (
                conv.get("duration_seconds", 0) / 60
                if conv.get("duration_seconds")
                else 0
            )
            duration_str = f"{duration_min:.1f}m" if duration_min > 0 else "N/A"

            row = [
                str(conv["id"]),
                (
                    conv["title"][:50] + "..."
                    if len(conv["title"]) > 50
                    else conv["title"]
                ),
                duration_str,
                str(conv.get("speaker_count", 0)),
                conv.get("analysis_status", "unknown"),
                conv["created_at"][:10] if conv.get("created_at") else "N/A",
            ]

            if show_details:
                row.extend(
                    [
                        (
                            conv.get("description", "")[:30] + "..."
                            if len(conv.get("description", "")) > 30
                            else conv.get("description", "")
                        ),
                        str(conv.get("word_count", 0)),
                    ]
                )

            table.add_row(*row)

        console.print(table)
        console.print(f"\n📊 Total conversations: {len(conversations)}")

    except Exception as e:
        logger.error(f"❌ Failed to list conversations: {e}")
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def show(conversation_id: int = typer.Option(..., "--conversation-id", "-c", help="Conversation ID to show")):
    """Show detailed information about a conversation."""
    try:
        # Initialize database
        transcript_manager = _get_transcript_manager()

        # Get conversation summary
        summary = transcript_manager.get_conversation_summary(conversation_id)

        if not summary:
            console.print(f"❌ Conversation {conversation_id} not found")
            return

        # Display conversation info
        conv_info = summary.get("conversation", {})
        console.print(
            Panel(
                f"[bold]Conversation {conversation_id}[/bold]\n"
                f"Title: {conv_info.get('title', 'N/A')}\n"
                f"Description: {conv_info.get('description', 'N/A')}\n"
                f"Duration: {conv_info.get('duration_seconds', 0) / 60:.1f} minutes\n"
                f"Word Count: {conv_info.get('word_count', 0):,}\n"
                f"Speakers: {conv_info.get('speaker_count', 0)}\n"
                f"Status: {conv_info.get('analysis_status', 'unknown')}\n"
                f"Created: {conv_info.get('created_at', 'N/A')}",
                title="📋 Conversation Details",
                border_style="blue",
            )
        )

        # Display speakers
        speakers = summary.get("speakers", [])
        if speakers:
            speaker_table = Table(title="🗣️ Speakers")
            speaker_table.add_column("ID", style="cyan")
            speaker_table.add_column("Name", style="green")
            speaker_table.add_column("Organization", style="yellow")
            speaker_table.add_column("Role", style="blue")

            for speaker in speakers:
                speaker_table.add_row(
                    str(speaker["id"]),
                    speaker["name"],
                    speaker.get("organization", ""),
                    speaker.get("role", ""),
                )

            console.print(speaker_table)

        # Display analysis results
        analysis_results = summary.get("analysis_results", [])
        if analysis_results:
            analysis_table = Table(title="🔍 Analysis Results")
            analysis_table.add_column("Type", style="cyan")
            analysis_table.add_column("Status", style="green")
            analysis_table.add_column("Processing Time", style="yellow")
            analysis_table.add_column("Created", style="dim")

            for result in analysis_results:
                processing_time = result.get("processing_time_seconds", 0)
                time_str = f"{processing_time:.2f}s" if processing_time else "N/A"

                analysis_table.add_row(
                    result["analysis_type"],
                    result["status"],
                    time_str,
                    result.get("created_at", "N/A")[:10],
                )

            console.print(analysis_table)

        # Display metadata
        metadata = summary.get("metadata", [])
        if metadata:
            metadata_table = Table(title="📝 Metadata")
            metadata_table.add_column("Key", style="cyan")
            metadata_table.add_column("Value", style="green")
            metadata_table.add_column("Category", style="yellow")

            for meta in metadata:
                metadata_table.add_row(
                    meta["key"],
                    (
                        meta["value"][:50] + "..."
                        if len(meta["value"]) > 50
                        else meta["value"]
                    ),
                    meta.get("category", ""),
                )

            console.print(metadata_table)

    except Exception as e:
        logger.error(f"❌ Failed to show conversation {conversation_id}: {e}")
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def delete(
    conversation_id: int = typer.Option(..., "--conversation-id", "-c", help="Conversation ID to delete"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force deletion without confirmation"
    ),
):
    """Delete a conversation and all associated data."""
    try:
        # Initialize database
        transcript_manager = _get_transcript_manager()

        # Get conversation info for confirmation
        summary = transcript_manager.get_conversation_summary(conversation_id)
        if not summary:
            console.print(f"❌ Conversation {conversation_id} not found")
            return

        conv_info = summary.get("conversation", {})

        if not force:
            # Ask for confirmation
            console.print(
                f"🗑️  About to delete conversation: {conv_info.get('title', 'Unknown')}"
            )
            console.print(
                f"   - Duration: {conv_info.get('duration_seconds', 0) / 60:.1f} minutes"
            )
            console.print(f"   - Speakers: {conv_info.get('speaker_count', 0)}")
            console.print(
                f"   - Analysis results: {len(summary.get('analysis_results', []))}"
            )

            if not typer.confirm("Are you sure you want to delete this conversation?"):
                console.print("❌ Deletion cancelled")
                return

        # Delete conversation
        with console.status("[bold red]Deleting conversation..."):
            success = transcript_manager.delete_conversation(conversation_id)

        if success:
            console.print(f"✅ Successfully deleted conversation {conversation_id}")
        else:
            console.print(f"❌ Failed to delete conversation {conversation_id}")

    except Exception as e:
        logger.error(f"❌ Failed to delete conversation {conversation_id}: {e}")
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def export(
    conversation_id: int = typer.Option(..., "--conversation-id", "-c", help="Conversation ID to export"),
    output_file: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Export conversation data to JSON file."""
    try:
        # Initialize database
        transcript_manager = _get_transcript_manager()

        # Get conversation summary
        summary = transcript_manager.get_conversation_summary(conversation_id)

        if not summary:
            console.print(f"❌ Conversation {conversation_id} not found")
            return

        # Determine output file
        if not output_file:
            conv_info = summary.get("conversation", {})
            title = conv_info.get("title", f"conversation_{conversation_id}")
            output_file = Path(f"{title.replace(' ', '_')}.json")

        # Export to JSON
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        console.print(f"✅ Exported conversation {conversation_id} to {output_file}")

    except Exception as e:
        logger.error(f"❌ Failed to export conversation {conversation_id}: {e}")
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def store(
    transcript_path: Path = typer.Option(..., "--transcript-path", help="Path to transcript JSON file"),
    title: Optional[str] = typer.Option(
        None, "--title", "-t", help="Custom conversation title"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Conversation description"
    ),
):
    """Store a transcript file in the database."""
    try:
        # Validate transcript file
        if not transcript_path.exists():
            console.print(f"❌ Transcript file not found: {transcript_path}")
            return

        # Initialize database
        transcript_manager = _get_transcript_manager()

        # Prepare metadata
        metadata = {}
        if title:
            metadata["custom_title"] = title
        if description:
            metadata["custom_description"] = description

        # Store transcript (speaker info comes from segments)
        with console.status("[bold green]Storing transcript in database..."):
            conversation, speakers = transcript_manager.store_transcript(
                transcript_path=str(transcript_path), metadata=metadata
            )

        console.print(f"✅ Successfully stored transcript in database")
        console.print(f"   - Conversation ID: {conversation.id}")
        console.print(f"   - Title: {conversation.title}")
        console.print(f"   - Speakers: {len(speakers)}")
        console.print(
            f"   - Duration: {conversation.duration_seconds / 60:.1f} minutes"
        )

    except Exception as e:
        logger.error(f"❌ Failed to store transcript {transcript_path}: {e}")
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def status():
    """Show database status and statistics."""
    try:
        # Initialize database
        transcript_manager = _get_transcript_manager()

        # Get basic statistics
        conversations = transcript_manager.list_conversations()

        # Calculate statistics
        total_conversations = len(conversations)
        completed_conversations = len(
            [c for c in conversations if c.get("analysis_status") == "completed"]
        )
        failed_conversations = len(
            [c for c in conversations if c.get("analysis_status") == "failed"]
        )
        pending_conversations = len(
            [c for c in conversations if c.get("analysis_status") == "pending"]
        )

        total_duration = sum(c.get("duration_seconds", 0) for c in conversations)
        total_words = sum(c.get("word_count", 0) for c in conversations)
        total_speakers = sum(c.get("speaker_count", 0) for c in conversations)

        # Display status
        console.print(
            Panel(
                f"[bold]Database Status[/bold]\n\n"
                f"📊 Total Conversations: {total_conversations}\n"
                f"✅ Completed: {completed_conversations}\n"
                f"❌ Failed: {failed_conversations}\n"
                f"⏳ Pending: {pending_conversations}\n\n"
                f"📈 Total Duration: {total_duration / 60:.1f} minutes\n"
                f"📝 Total Words: {total_words:,}\n"
                f"🗣️  Total Speakers: {total_speakers}",
                title="📊 Database Statistics",
                border_style="green",
            )
        )

    except Exception as e:
        logger.error(f"❌ Failed to get database status: {e}")
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    import sys

    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)  # Standard SIGINT exit code
    except typer.Exit as e:
        # Handle typer.Exit (including CliExit) gracefully without traceback
        sys.exit(e.exit_code)
