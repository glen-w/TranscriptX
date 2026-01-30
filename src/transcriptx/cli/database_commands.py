"""
Database management CLI commands for TranscriptX.

This module provides CLI commands for database management, including:
- Database initialization and setup
- Migration management
- Speaker profiling operations
- Database status and information
- Data import/export utilities

The commands support:
- Interactive database setup
- Migration creation and execution
- Speaker profile management
- Database health checks
- Performance monitoring
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from transcriptx.core.utils.logger import get_logger
from .exit_codes import CliExit, EXIT_USER_CANCEL

logger = get_logger()
console = Console()

app = typer.Typer(
    name="database",
    help="Database management commands for TranscriptX",
    no_args_is_help=True,
)


def _init_database():
    from transcriptx.database.database import init_database

    return init_database()


def _get_database_manager():
    from transcriptx.database.database import get_database_manager

    return get_database_manager()


def _get_session():
    from transcriptx.database.database import get_session

    return get_session()


def _get_migration_manager():
    from transcriptx.database.migrations import get_migration_manager

    return get_migration_manager()


def _run_migrations(*args, **kwargs):
    from transcriptx.database.migrations import run_migrations

    return run_migrations(*args, **kwargs)


def _create_migration(*args, **kwargs):
    from transcriptx.database.migrations import create_migration

    return create_migration(*args, **kwargs)


def _check_migration_status():
    from transcriptx.database.migrations import check_migration_status

    return check_migration_status()


def _get_migration_history():
    from transcriptx.database.migrations import get_migration_history

    return get_migration_history()


def _get_speaker_repo():
    from transcriptx.database.repositories import SpeakerRepository

    session = _get_session()
    return SpeakerRepository(session)


def _get_speaker_stats_service():
    from transcriptx.database.speaker_statistics import SpeakerStatisticsService

    return SpeakerStatisticsService()


def _get_speaker_profiling_service():
    from transcriptx.database.speaker_profiling import SpeakerProfilingService

    return SpeakerProfilingService()


@app.command("reset")
def reset_db(
    force: bool = typer.Option(
        False, "--force", help="Force reset without safety guard"
    ),
):
    """
    Reset the database (dev-only).
    """
    if not typer.confirm("⚠️ This will DELETE all database data. Continue?"):
        raise CliExit.user_cancel("Operation cancelled")
    from .db_reset_command import reset_database

    reset_database(force=force)
    console.print("✅ Database reset completed")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Force reinitialization"),
    reset: bool = typer.Option(
        False, "--reset", "-r", help="Reset database (WARNING: deletes all data)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """
    Initialize the TranscriptX database.

    This command sets up the database backend, creates tables,
    and initializes the migration system.
    """
    try:
        console.print(
            Panel.fit("🔧 Initializing TranscriptX Database", style="bold blue")
        )

        if reset:
            if not typer.confirm(
                "⚠️ This will delete ALL data in the database. Continue?"
            ):
                console.print("❌ Operation cancelled")
                raise CliExit.user_cancel("Operation cancelled")

            console.print("🔄 Resetting database...")
            reset_database(force=force)
            console.print("✅ Database reset completed")

        # Initialize database
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Initializing database...", total=None)

            db_manager = _init_database()
            progress.update(task, description="✅ Database initialized")

        # Initialize migrations
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Setting up migrations...", total=None)

            migration_manager = _get_migration_manager()
            migration_manager.init_migrations()
            progress.update(task, description="✅ Migrations initialized")

        # Run initial migrations
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running migrations...", total=None)

            success = _run_migrations()
            if success:
                progress.update(task, description="✅ Migrations completed")
            else:
                progress.update(task, description="❌ Migration failed")
                raise CliExit.user_cancel("Operation cancelled")

        # Display database info
        if verbose:
            display_database_info()

        console.print("🎉 Database initialization completed successfully!")

    except Exception as e:
        console.print(f"❌ Database initialization failed: {e}")
        logger.error(f"Database initialization failed: {e}")
        raise CliExit.error()


@app.command()
def status():
    """
    Display database status and information.
    """
    try:
        console.print(Panel.fit("📊 Database Status", style="bold blue"))

        # Get database info
        db_manager = _get_database_manager()
        db_info = db_manager.get_database_info()

        # Create info table
        table = Table(title="Database Information")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Database Type", db_info.get("database_type", "Unknown"))
        table.add_row("Database URL", db_info.get("database_url", "Unknown"))
        table.add_row("Initialized", str(db_info.get("initialized", False)))
        table.add_row("Connection Status", db_info.get("connection_status", "Unknown"))

        if db_info.get("database_size"):
            table.add_row("Database Size", db_info.get("database_size", "Unknown"))

        console.print(table)

        # Display table counts
        if db_info.get("table_counts"):
            console.print("\n📋 Table Statistics:")
            counts_table = Table()
            counts_table.add_column("Table", style="cyan")
            counts_table.add_column("Records", style="green")

            for table_name, count in db_info["table_counts"].items():
                counts_table.add_row(table_name, str(count))

            console.print(counts_table)

        # Display migration status
        console.print("\n🔄 Migration Status:")
        migration_status = _check_migration_status()

        migration_table = Table()
        migration_table.add_column("Property", style="cyan")
        migration_table.add_column("Value", style="green")

        migration_table.add_row(
            "Current Revision", migration_status.get("current_revision", "None")
        )
        migration_table.add_row(
            "Head Revision", migration_status.get("head_revision", "None")
        )
        migration_table.add_row(
            "Up to Date", str(migration_status.get("is_up_to_date", False))
        )
        migration_table.add_row(
            "Pending Migrations", str(migration_status.get("pending_count", 0))
        )

        console.print(migration_table)

        if migration_status.get("pending_migrations"):
            console.print(
                f"📝 Pending migrations: {', '.join(migration_status['pending_migrations'])}"
            )

    except Exception as e:
        console.print(f"❌ Failed to get database status: {e}")
        logger.error(f"Database status check failed: {e}")
        raise CliExit.error()


@app.command()
def migrate(
    target: Optional[str] = typer.Argument(None, help="Target migration revision"),
    create: bool = typer.Option(False, "--create", "-c", help="Create new migration"),
    message: Optional[str] = typer.Option(
        None, "--message", "-m", help="Migration message"
    ),
    autogenerate: bool = typer.Option(
        True, "--autogenerate/--no-autogenerate", help="Auto-generate migration"
    ),
):
    """
    Manage database migrations.
    """
    try:
        if create:
            if not message:
                message = typer.prompt("Enter migration message")

            console.print(f"🔧 Creating migration: {message}")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Creating migration...", total=None)

                revision = _create_migration(message, autogenerate)
                if revision:
                    progress.update(
                        task, description=f"✅ Migration created: {revision}"
                    )
                else:
                    progress.update(task, description="❌ Migration creation failed")
                    raise CliExit.user_cancel("Operation cancelled")
        else:
            console.print(f"🔄 Running migrations to target: {target or 'latest'}")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Running migrations...", total=None)

                success = _run_migrations(target)
                if success:
                    progress.update(task, description="✅ Migrations completed")
                else:
                    progress.update(task, description="❌ Migration failed")
                    raise CliExit.user_cancel("Operation cancelled")

    except Exception as e:
        console.print(f"❌ Migration operation failed: {e}")
        logger.error(f"Migration operation failed: {e}")
        raise CliExit.error()


@app.command()
def history():
    """
    Display migration history.
    """
    try:
        console.print(Panel.fit("📜 Migration History", style="bold blue"))

        history = _get_migration_history()

        if not history:
            console.print("No migrations found")
            return

        table = Table(title="Migration History")
        table.add_column("Revision", style="cyan")
        table.add_column("Message", style="green")
        table.add_column("Date", style="yellow")
        table.add_column("Down Revision", style="magenta")

        for migration in history:
            table.add_row(
                migration.get("revision", "Unknown"),
                migration.get("message", "No message"),
                str(migration.get("date", "Unknown")),
                migration.get("down_revision", "None"),
            )

        console.print(table)

    except Exception as e:
        console.print(f"❌ Failed to get migration history: {e}")
        logger.error(f"Migration history failed: {e}")
        raise CliExit.error()


@app.command()
def profile_speaker(
    name: str = typer.Argument(..., help="Speaker name"),
    transcript_file: Path = typer.Option(
        ..., "--transcript", "-t", help="Transcript file path"
    ),
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Speaker email"),
    organization: Optional[str] = typer.Option(
        None, "--organization", "-o", help="Speaker organization"
    ),
    role: Optional[str] = typer.Option(None, "--role", "-r", help="Speaker role"),
    color: Optional[str] = typer.Option(
        None, "--color", "-c", help="Speaker color (hex code)"
    ),
):
    """
    Create or update a speaker profile from transcript data.
    """
    try:
        console.print(Panel.fit(f"👤 Speaker Profiling: {name}", style="bold blue"))

        # Load transcript data
        if not transcript_file.exists():
            console.print(f"❌ Transcript file not found: {transcript_file}")
            raise CliExit.error()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Loading transcript data...", total=None)

            # Load transcript data (simplified for now)
            transcript_data = load_transcript_data(transcript_file)
            progress.update(task, description="✅ Transcript data loaded")

        # Initialize profiling service
        profiling_service = _get_speaker_profiling_service()

        try:
            # Create or get speaker
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Creating/getting speaker...", total=None)

                speaker, is_new = profiling_service.create_or_get_speaker(
                    name=name,
                    email=email,
                    organization=organization,
                    role=role,
                    color=color,
                )

                if is_new:
                    progress.update(task, description="✅ New speaker created")
                else:
                    progress.update(task, description="✅ Existing speaker found")

            # Extract speaker segments
            speaker_segments = extract_speaker_segments(transcript_data, name)

            if not speaker_segments:
                console.print(f"❌ No segments found for speaker: {name}")
                raise CliExit.user_cancel("Operation cancelled")

            # Create or update profile
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Creating/updating speaker profile...", total=None
                )

                # Check if speaker has existing profile
                existing_profile = profiling_service.profile_repo.get_current_profile(
                    speaker.id
                )

                if existing_profile:
                    profile = profiling_service.update_speaker_profile(
                        speaker.id, speaker_segments
                    )
                    progress.update(task, description="✅ Speaker profile updated")
                else:
                    profile = profiling_service.create_speaker_profile(
                        speaker.id, speaker_segments
                    )
                    progress.update(task, description="✅ Speaker profile created")

            # Create behavioral fingerprint
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Creating behavioral fingerprint...", total=None
                )

                fingerprint = profiling_service.create_behavioral_fingerprint(
                    speaker.id, speaker_segments
                )
                progress.update(task, description="✅ Behavioral fingerprint created")

            # Display results
            display_speaker_profile(speaker, profile, fingerprint)

        finally:
            profiling_service.close()

        console.print("🎉 Speaker profiling completed successfully!")

    except Exception as e:
        console.print(f"❌ Speaker profiling failed: {e}")
        logger.error(f"Speaker profiling failed: {e}")
        raise CliExit.error()


@app.command()
def list_speakers():
    """
    List all speakers in the database.
    """
    try:
        console.print(Panel.fit("👥 Speaker List", style="bold blue"))

        from transcriptx.database.repositories import SpeakerRepository
        session = _get_session()
        speaker_repo = SpeakerRepository(session)

        speakers = speaker_repo.find_speakers(active_only=True)

        if not speakers:
            console.print("No speakers found in database")
            return

        table = Table(title="Speakers")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Email", style="yellow")
        table.add_column("Organization", style="magenta")
        table.add_column("Role", style="blue")
        table.add_column("Created", style="white")

        for speaker in speakers:
            table.add_row(
                str(speaker.id),
                speaker.name,
                speaker.email or "",
                speaker.organization or "",
                speaker.role or "",
                speaker.created_at.strftime("%Y-%m-%d %H:%M"),
            )

        console.print(table)

    except Exception as e:
        console.print(f"❌ Failed to list speakers: {e}")
        logger.error(f"List speakers failed: {e}")
        raise CliExit.error()


def display_database_info():
    """Display detailed database information."""
    db_manager = _get_database_manager()
    db_info = db_manager.get_database_info()

    console.print("\n📊 Database Details:")
    console.print(f"  Type: {db_info.get('database_type', 'Unknown')}")
    console.print(f"  URL: {db_info.get('database_url', 'Unknown')}")
    console.print(f"  Size: {db_info.get('database_size', 'Unknown')}")
    console.print(f"  Status: {db_info.get('connection_status', 'Unknown')}")


def load_transcript_data(transcript_file: Path) -> dict:
    """Load transcript data from file using I/O service."""
    try:
        from transcriptx.io.transcript_service import get_transcript_service

        service = get_transcript_service()

        if transcript_file.suffix == ".json":
            # Use service for caching
            return service.load_transcript(str(transcript_file))
        else:
            # Simple text parsing for non-JSON files
            with open(transcript_file, "r") as f:
                return {"segments": [{"text": f.read(), "speaker": "Unknown"}]}
    except Exception as e:
        logger.error(f"Failed to load transcript data: {e}")
        raise


def extract_speaker_segments(transcript_data: dict, speaker_name: str) -> list:
    """Extract segments for a specific speaker."""
    segments = []

    if "segments" in transcript_data:
        for segment in transcript_data["segments"]:
            if segment.get("speaker") == speaker_name:
                segments.append(segment)

    return segments


def display_speaker_profile(speaker, profile, fingerprint):
    """Display speaker profile information."""
    console.print(f"\n👤 Speaker Profile: {speaker.name}")
    console.print(f"  ID: {speaker.id}")
    console.print(f"  Email: {speaker.email or 'Not specified'}")
    console.print(f"  Organization: {speaker.organization or 'Not specified'}")
    console.print(f"  Role: {speaker.role or 'Not specified'}")
    console.print(f"  Profile Version: {profile.profile_version}")
    console.print(f"  Fingerprint Version: {fingerprint.fingerprint_version}")
    console.print(f"  Confidence Score: {fingerprint.confidence_score:.3f}")


@app.command()
def speakers_list():
    """List all speakers with their statistics."""
    try:
        _init_database()
        speaker_repo = _get_speaker_repo()
        stats_service = _get_speaker_stats_service()

        speakers = speaker_repo.find_speakers(active_only=True)
        all_stats = stats_service.get_all_speaker_statistics()

        # Create stats lookup
        stats_lookup = {s["speaker_id"]: s for s in all_stats}

        if not speakers:
            console.print("[yellow]No speakers found in database[/yellow]")
            return

        table = Table(title="Speakers", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Display Name", style="yellow")
        table.add_column("Conversations", justify="right")
        table.add_column("Speaking Time (min)", justify="right")
        table.add_column("Word Count", justify="right")
        table.add_column("Avg Rate (wpm)", justify="right")

        for speaker in speakers:
            stats = stats_lookup.get(speaker.id, {})
            speaking_time_min = (stats.get("total_speaking_time") or 0) / 60
            word_count = stats.get("total_word_count") or 0
            avg_rate = stats.get("average_speaking_rate") or 0
            conv_count = stats.get("conversation_count") or 0

            table.add_row(
                str(speaker.id),
                speaker.name,
                speaker.display_name or speaker.name,
                str(conv_count),
                f"{speaking_time_min:.1f}",
                str(word_count),
                f"{avg_rate:.1f}",
            )

        console.print(table)

    except Exception as e:
        logger.error(f"❌ Failed to list speakers: {e}")
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def speakers_show(speaker_id: int = typer.Argument(..., help="Speaker ID to show")):
    """Show detailed information about a speaker."""
    try:
        _init_database()
        speaker_repo = _get_speaker_repo()
        stats_service = _get_speaker_stats_service()

        speaker = speaker_repo.get_speaker_by_id(speaker_id)
        if not speaker:
            console.print(f"[red]Speaker with ID {speaker_id} not found[/red]")
            return

        # Get statistics
        stats = stats_service.get_speaker_statistics(speaker_id)

        # Get report
        report = stats_service.generate_speaker_report(speaker_id)

        # Display speaker information
        console.print(f"\n[bold cyan]Speaker: {speaker.name}[/bold cyan]")
        console.print(f"  ID: {speaker.id}")
        console.print(f"  Display Name: {speaker.display_name or speaker.name}")
        console.print(f"  Email: {speaker.email or 'Not specified'}")
        console.print(f"  Organization: {speaker.organization or 'Not specified'}")
        console.print(f"  Role: {speaker.role or 'Not specified'}")
        console.print(f"  Canonical ID: {speaker.canonical_id or 'Not set'}")
        console.print(f"  Confidence Score: {speaker.confidence_score or 0.0:.2f}")
        console.print(f"  Verified: {'Yes' if speaker.is_verified else 'No'}")
        console.print(f"  Active: {'Yes' if speaker.is_active else 'No'}")

        if stats:
            console.print(f"\n[bold cyan]Statistics:[/bold cyan]")
            console.print(
                f"  Total Speaking Time: {(stats.total_speaking_time or 0) / 60:.1f} minutes"
            )
            console.print(f"  Total Word Count: {stats.total_word_count or 0}")
            console.print(f"  Total Segments: {stats.total_segment_count or 0}")
            console.print(
                f"  Average Speaking Rate: {stats.average_speaking_rate or 0:.1f} words/min"
            )
            if stats.average_sentiment_score is not None:
                console.print(
                    f"  Average Sentiment: {stats.average_sentiment_score:.2f}"
                )
            if stats.dominant_emotion:
                console.print(f"  Dominant Emotion: {stats.dominant_emotion}")

        if report.get("participation"):
            participation = report["participation"]
            console.print(f"\n[bold cyan]Participation:[/bold cyan]")
            console.print(
                f"  Conversations: {participation.get('conversation_count', 0)}"
            )
            console.print(f"  Sessions: {participation.get('session_count', 0)}")

        stats_service.close()

    except Exception as e:
        logger.error(f"❌ Failed to show speaker: {e}")
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def speakers_merge(
    source_id: int = typer.Argument(
        ..., help="Source speaker ID (will be merged into target)"
    ),
    target_id: int = typer.Argument(..., help="Target speaker ID (will keep this one)"),
):
    """Merge two speakers into one."""
    try:
        _init_database()
        from transcriptx.database.repositories import SpeakerRepository

        session = _get_session()
        speaker_repo = SpeakerRepository(session)

        source_speaker = speaker_repo.get_speaker_by_id(source_id)
        target_speaker = speaker_repo.get_speaker_by_id(target_id)

        if not source_speaker:
            console.print(f"[red]Source speaker {source_id} not found[/red]")
            return

        if not target_speaker:
            console.print(f"[red]Target speaker {target_id} not found[/red]")
            return

        if source_id == target_id:
            console.print(f"[red]Cannot merge speaker with itself[/red]")
            return

        # Confirm merge
        console.print(f"\n[yellow]This will merge:[/yellow]")
        console.print(f"  Source: {source_speaker.name} (ID: {source_id})")
        console.print(f"  Target: {target_speaker.name} (ID: {target_id})")
        console.print(
            f"\n[yellow]All data from source will be moved to target.[/yellow]"
        )

        confirm = typer.confirm("Are you sure you want to proceed?")
        if not confirm:
            console.print("[yellow]Merge cancelled[/yellow]")
            return

        # Merge speakers
        # Update all sessions to point to target
        from transcriptx.database.models import Session as DBSession

        sessions = (
            session.query(DBSession).filter(DBSession.speaker_id == source_id).all()
        )
        for s in sessions:
            s.speaker_id = target_id

        # Update all stats to point to target
        from transcriptx.database.models import SpeakerStats

        stats = (
            session.query(SpeakerStats)
            .filter(SpeakerStats.speaker_id == source_id)
            .all()
        )
        for stat in stats:
            stat.speaker_id = target_id

        # Deactivate source speaker
        source_speaker.is_active = False

        session.commit()

        console.print(
            f"[green]✅ Successfully merged speaker {source_id} into {target_id}[/green]"
        )

    except Exception as e:
        session.rollback()
        logger.error(f"❌ Failed to merge speakers: {e}")
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def speakers_stats():
    """Show aggregate speaker statistics."""
    try:
        _init_database()
        stats_service = _get_speaker_stats_service()

        all_stats = stats_service.get_all_speaker_statistics()

        if not all_stats:
            console.print("[yellow]No speaker statistics available[/yellow]")
            return

        # Calculate aggregates
        total_speakers = len(all_stats)
        total_speaking_time = sum(s.get("total_speaking_time") or 0 for s in all_stats)
        total_words = sum(s.get("total_word_count") or 0 for s in all_stats)
        total_conversations = sum(s.get("conversation_count") or 0 for s in all_stats)

        avg_speaking_time = (
            total_speaking_time / total_speakers if total_speakers > 0 else 0
        )
        avg_words = total_words / total_speakers if total_speakers > 0 else 0

        console.print(f"\n[bold cyan]Aggregate Speaker Statistics[/bold cyan]")
        console.print(f"  Total Speakers: {total_speakers}")
        console.print(f"  Total Speaking Time: {total_speaking_time / 60:.1f} minutes")
        console.print(f"  Total Word Count: {total_words:,}")
        console.print(f"  Total Conversations: {total_conversations}")
        console.print(
            f"  Average Speaking Time per Speaker: {avg_speaking_time / 60:.1f} minutes"
        )
        console.print(f"  Average Word Count per Speaker: {avg_words:,.0f}")

        # Top speakers by speaking time
        top_speakers = sorted(
            all_stats, key=lambda x: x.get("total_speaking_time") or 0, reverse=True
        )[:5]

        if top_speakers:
            console.print(f"\n[bold cyan]Top 5 Speakers by Speaking Time:[/bold cyan]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Name", style="green")
            table.add_column("Speaking Time (min)", justify="right")
            table.add_column("Word Count", justify="right")
            table.add_column("Conversations", justify="right")

            for speaker in top_speakers:
                table.add_row(
                    speaker.get("speaker_name", "Unknown"),
                    f"{(speaker.get('total_speaking_time') or 0) / 60:.1f}",
                    str(speaker.get("total_word_count") or 0),
                    str(speaker.get("conversation_count") or 0),
                )

            console.print(table)

        stats_service.close()

    except Exception as e:
        logger.error(f"❌ Failed to get speaker statistics: {e}")
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    import sys

    try:
        app()
    except KeyboardInterrupt:
        sys.exit(EXIT_USER_CANCEL)
    except typer.Exit as e:
        # Handle typer.Exit (including CliExit) gracefully without traceback
        sys.exit(e.exit_code)
