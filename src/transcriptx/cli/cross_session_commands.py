"""
Cross-session speaker tracking CLI commands for TranscriptX.

This module provides CLI commands for advanced cross-session speaker tracking,
including speaker matching, pattern evolution tracking, and behavioral analysis.

Key Features:
- Speaker matching across sessions
- Pattern evolution tracking
- Behavioral anomaly detection
- Speaker clustering and grouping
- Network analysis and visualization
- Confidence scoring and verification
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from transcriptx.core.utils.logger import get_logger
from .exit_codes import CliExit

logger = get_logger()
console = Console()

app = typer.Typer(
    name="cross-session",
    help="Cross-session speaker tracking commands for TranscriptX",
    no_args_is_help=True,
)


def _get_tracking_service():
    from transcriptx.database.cross_session_tracking import CrossSessionTrackingService

    return CrossSessionTrackingService()


def _get_db_session():
    from transcriptx.database.database import get_session

    return get_session()


def _get_speaker_cluster_model():
    from transcriptx.database.models import SpeakerCluster

    return SpeakerCluster


@app.command()
def match_speakers(
    speaker_name: str = typer.Option(..., "--speaker-name", "-n", help="Name of the speaker to match"),
    transcript_file: Path = typer.Option(
        ..., "--transcript", "-t", help="Transcript file path"
    ),
    confidence_threshold: float = typer.Option(
        0.7, "--threshold", "-c", help="Minimum confidence threshold"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """
    Find potential matches for a speaker across all sessions.

    This command analyzes a speaker's behavioral patterns and finds
    potential matches across all existing sessions in the database.
    """
    try:
        console.print(Panel.fit("🔍 Cross-Session Speaker Matching", style="bold blue"))

        # Load transcript data
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Loading transcript data...", total=None)

            transcript_data = load_transcript_data(transcript_file)
            speaker_segments = extract_speaker_segments(transcript_data, speaker_name)

            if not speaker_segments:
                console.print(f"❌ No segments found for speaker '{speaker_name}'")
                raise CliExit.error()

            progress.update(task, description="✅ Transcript data loaded")

        # Initialize tracking service
        tracking_service = _get_tracking_service()

        # Find matches
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Finding speaker matches...", total=None)

            matches = tracking_service.find_speaker_matches(
                speaker_name, speaker_segments, confidence_threshold
            )

            progress.update(task, description="✅ Speaker matches found")

        # Display results
        if matches:
            console.print(
                f"\n🎯 Found {len(matches)} potential matches for '{speaker_name}':"
            )

            table = Table(title="Speaker Matches")
            table.add_column("Speaker ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Email", style="yellow")
            table.add_column("Confidence", style="magenta")
            table.add_column("Verified", style="blue")

            for speaker, confidence in matches:
                table.add_row(
                    str(speaker.id),
                    speaker.name,
                    speaker.email or "N/A",
                    f"{confidence:.2%}",
                    "✅" if speaker.is_verified else "❌",
                )

            console.print(table)

            # Show detailed information for top match
            if matches:
                top_match, top_confidence = matches[0]
                console.print(f"\n🏆 Top Match: {top_match.name} (ID: {top_match.id})")
                console.print(f"   Confidence: {top_confidence:.2%}")
                console.print(f"   Email: {top_match.email or 'N/A'}")
                console.print(f"   Organization: {top_match.organization or 'N/A'}")

                if top_confidence >= 0.9:
                    console.print("   🎉 High confidence match!")
                elif top_confidence >= 0.7:
                    console.print("   ✅ Good confidence match")
                else:
                    console.print("   ⚠️ Low confidence match")
        else:
            console.print(
                f"❌ No matches found for '{speaker_name}' above threshold {confidence_threshold:.1%}"
            )

    except Exception as e:
        console.print(f"❌ Speaker matching failed: {e}")
        logger.error(f"Speaker matching failed: {e}")
        raise CliExit.error()


@app.command()
def track_evolution(
    speaker_id: int = typer.Option(..., "--speaker-id", help="Speaker ID to track"),
    transcript_file: Path = typer.Option(
        ..., "--transcript", "-t", help="Transcript file path"
    ),
    session_id: int = typer.Option(..., "--session", "-s", help="Session ID"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """
    Track behavioral pattern evolution for a speaker.

    This command analyzes how a speaker's behavioral patterns have
    evolved over time by comparing current session data with historical patterns.
    """
    try:
        console.print(
            Panel.fit("📈 Speaker Pattern Evolution Tracking", style="bold blue")
        )

        # Load transcript data
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Loading transcript data...", total=None)

            transcript_data = load_transcript_data(transcript_file)
            speaker_segments = extract_speaker_segments_by_id(
                transcript_data, speaker_id
            )

            if not speaker_segments:
                console.print(f"❌ No segments found for speaker ID {speaker_id}")
                raise CliExit.error()

            progress.update(task, description="✅ Transcript data loaded")

        # Initialize tracking service
        tracking_service = _get_tracking_service()

        # Track evolution
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Tracking pattern evolution...", total=None)

            evolutions = tracking_service.track_speaker_evolution(
                speaker_id, speaker_segments, session_id
            )

            progress.update(task, description="✅ Pattern evolution tracked")

        # Display results
        if evolutions:
            console.print(f"\n🔄 Detected {len(evolutions)} pattern evolutions:")

            table = Table(title="Pattern Evolutions")
            table.add_column("Pattern Type", style="cyan")
            table.add_column("Change Magnitude", style="green")
            table.add_column("Confidence", style="yellow")
            table.add_column("Significant", style="magenta")
            table.add_column("Reason", style="blue")

            for evolution in evolutions:
                table.add_row(
                    evolution.pattern_type,
                    f"{evolution.change_magnitude:.2f}",
                    f"{evolution.change_confidence:.2%}",
                    "✅" if evolution.is_significant else "❌",
                    evolution.change_reason or "N/A",
                )

            console.print(table)

            # Show detailed information
            significant_evolutions = [e for e in evolutions if e.is_significant]
            if significant_evolutions:
                console.print(
                    f"\n🎯 {len(significant_evolutions)} significant changes detected!"
                )
                for evolution in significant_evolutions:
                    console.print(
                        f"   • {evolution.pattern_type}: {evolution.change_reason}"
                    )
        else:
            console.print("✅ No significant pattern changes detected")

    except Exception as e:
        console.print(f"❌ Evolution tracking failed: {e}")
        logger.error(f"Evolution tracking failed: {e}")
        raise CliExit.error()


@app.command()
def detect_anomalies(
    speaker_id: int = typer.Option(..., "--speaker-id", help="Speaker ID to analyze"),
    transcript_file: Path = typer.Option(
        ..., "--transcript", "-t", help="Transcript file path"
    ),
    session_id: int = typer.Option(..., "--session", "-s", help="Session ID"),
    severity_threshold: float = typer.Option(
        0.5, "--severity", "-v", help="Minimum severity threshold"
    ),
):
    """
    Detect behavioral anomalies for a speaker.

    This command analyzes a speaker's session data and detects
    unusual behavioral patterns compared to their historical patterns.
    """
    try:
        console.print(Panel.fit("🚨 Behavioral Anomaly Detection", style="bold blue"))

        # Load transcript data
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Loading transcript data...", total=None)

            transcript_data = load_transcript_data(transcript_file)
            speaker_segments = extract_speaker_segments_by_id(
                transcript_data, speaker_id
            )

            if not speaker_segments:
                console.print(f"❌ No segments found for speaker ID {speaker_id}")
                raise CliExit.error()

            progress.update(task, description="✅ Transcript data loaded")

        # Initialize tracking service
        tracking_service = _get_tracking_service()

        # Detect anomalies
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Detecting behavioral anomalies...", total=None)

            anomalies = tracking_service.detect_behavioral_anomalies(
                speaker_id, session_id, speaker_segments
            )

            progress.update(task, description="✅ Anomalies detected")

        # Filter by severity threshold
        filtered_anomalies = [a for a in anomalies if a.severity >= severity_threshold]

        # Display results
        if filtered_anomalies:
            console.print(
                f"\n🚨 Detected {len(filtered_anomalies)} behavioral anomalies:"
            )

            table = Table(title="Behavioral Anomalies")
            table.add_column("Type", style="cyan")
            table.add_column("Severity", style="red")
            table.add_column("Description", style="green")
            table.add_column("Resolved", style="yellow")

            for anomaly in filtered_anomalies:
                severity_color = (
                    "red"
                    if anomaly.severity > 0.8
                    else "yellow" if anomaly.severity > 0.5 else "green"
                )
                table.add_row(
                    anomaly.anomaly_type,
                    f"{anomaly.severity:.2%}",
                    anomaly.description,
                    "✅" if anomaly.is_resolved else "❌",
                )

            console.print(table)

            # Show high severity anomalies
            high_severity = [a for a in filtered_anomalies if a.severity > 0.8]
            if high_severity:
                console.print(
                    f"\n⚠️ {len(high_severity)} high severity anomalies detected!"
                )
                for anomaly in high_severity:
                    console.print(f"   • {anomaly.anomaly_type}: {anomaly.description}")
        else:
            console.print("✅ No behavioral anomalies detected")

    except Exception as e:
        console.print(f"❌ Anomaly detection failed: {e}")
        logger.error(f"Anomaly detection failed: {e}")
        raise CliExit.error()


@app.command()
def create_cluster(
    name: str = typer.Option(..., "--name", "-n", help="Cluster name"),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Cluster description"
    ),
    cluster_type: str = typer.Option(
        "behavioral",
        "--type",
        "-t",
        help="Cluster type (behavioral, organizational, manual)",
    ),
):
    """
    Create a new speaker cluster for grouping similar speakers.

    This command creates a cluster that can be used to group
    speakers based on behavioral similarities or other criteria.
    """
    try:
        console.print(Panel.fit("👥 Speaker Cluster Creation", style="bold blue"))

        # Initialize tracking service
        tracking_service = _get_tracking_service()

        # Create cluster
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Creating speaker cluster...", total=None)

            cluster = tracking_service.create_speaker_cluster(
                name, description, cluster_type
            )

            progress.update(task, description="✅ Speaker cluster created")

        # Display results
        console.print(f"\n✅ Created speaker cluster:")
        console.print(f"   Name: {cluster.name}")
        console.print(f"   Type: {cluster.cluster_type}")
        console.print(f"   Description: {cluster.description or 'N/A'}")
        console.print(f"   ID: {cluster.id}")

    except Exception as e:
        console.print(f"❌ Cluster creation failed: {e}")
        logger.error(f"Cluster creation failed: {e}")
        raise CliExit.error()


@app.command()
def add_to_cluster(
    speaker_id: int = typer.Option(..., "--speaker-id", "-s", help="Speaker ID to add"),
    cluster_id: int = typer.Option(..., "--cluster-id", help="Cluster ID to add to"),
    confidence_score: float = typer.Option(
        0.8, "--confidence", "-c", help="Confidence score"
    ),
    membership_type: str = typer.Option(
        "automatic",
        "--type",
        "-t",
        help="Membership type (automatic, manual, suggested)",
    ),
):
    """
    Add a speaker to a cluster.

    This command adds a speaker to an existing cluster with
    specified confidence score and membership type.
    """
    try:
        console.print(Panel.fit("➕ Add Speaker to Cluster", style="bold blue"))

        # Initialize tracking service
        tracking_service = _get_tracking_service()

        # Add speaker to cluster
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Adding speaker to cluster...", total=None)

            membership = tracking_service.add_speaker_to_cluster(
                speaker_id, cluster_id, confidence_score, membership_type
            )

            progress.update(task, description="✅ Speaker added to cluster")

        # Display results
        console.print(f"\n✅ Added speaker {speaker_id} to cluster {cluster_id}:")
        console.print(f"   Confidence: {membership.confidence_score:.2%}")
        console.print(f"   Membership Type: {membership.membership_type}")
        console.print(f"   Joined: {membership.joined_at}")

    except Exception as e:
        console.print(f"❌ Failed to add speaker to cluster: {e}")
        logger.error(f"Failed to add speaker to cluster: {e}")
        raise CliExit.error()


@app.command()
def show_network(
    speaker_id: int = typer.Option(..., "--speaker-id", "-s", help="Speaker ID to analyze"),
    max_depth: int = typer.Option(2, "--depth", "-d", help="Maximum network depth"),
):
    """
    Show the interaction network for a speaker.

    This command displays the network of speakers connected to
    the specified speaker through various types of links.
    """
    try:
        console.print(Panel.fit("🌐 Speaker Network Analysis", style="bold blue"))

        # Initialize tracking service
        tracking_service = _get_tracking_service()

        # Get network
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing speaker network...", total=None)

            network = tracking_service.get_speaker_network(speaker_id, max_depth)

            progress.update(task, description="✅ Network analysis complete")

        # Display results
        console.print(f"\n🌐 Network for Speaker ID {speaker_id}:")

        # Show direct links
        if network["direct_links"]:
            console.print(f"\n🔗 Direct Links ({len(network['direct_links'])}):")
            table = Table()
            table.add_column("Linked Speaker ID", style="cyan")
            table.add_column("Confidence", style="green")
            table.add_column("Link Type", style="yellow")

            for link in network["direct_links"]:
                table.add_row(
                    str(link["linked_speaker_id"]),
                    f"{link['confidence']:.2%}",
                    link["link_type"],
                )

            console.print(table)
        else:
            console.print("❌ No direct links found")

        # Show session participations
        if network["session_participations"]:
            console.print(
                f"\n📊 Session Participations ({len(network['session_participations'])}):"
            )
            table = Table()
            table.add_column("Session ID", style="cyan")
            table.add_column("Participation Score", style="green")
            table.add_column("Behavioral Consistency", style="yellow")

            for participation in network["session_participations"]:
                table.add_row(
                    str(participation["session_id"]),
                    f"{participation['participation_score']:.2%}",
                    f"{participation['behavioral_consistency']:.2%}",
                )

            console.print(table)
        else:
            console.print("❌ No session participations found")

        # Show network metrics
        metrics = network["network_metrics"]
        console.print(f"\n📈 Network Metrics:")
        console.print(f"   Total Connections: {metrics['total_connections']}")
        console.print(
            f"   High Confidence Connections: {metrics['high_confidence_connections']}"
        )
        console.print(f"   Average Confidence: {metrics['average_confidence']:.2%}")

    except Exception as e:
        console.print(f"❌ Network analysis failed: {e}")
        logger.error(f"Network analysis failed: {e}")
        raise CliExit.error()


@app.command()
def list_clusters():
    """
    List all speaker clusters.

    This command displays all speaker clusters in the database
    with their member counts and metadata.
    """
    try:
        console.print(Panel.fit("👥 Speaker Clusters", style="bold blue"))

        SpeakerCluster = _get_speaker_cluster_model()
        with _get_db_session() as session:
            clusters = session.query(SpeakerCluster).all()

            if clusters:
                table = Table(title="Speaker Clusters")
                table.add_column("ID", style="cyan")
                table.add_column("Name", style="green")
                table.add_column("Type", style="yellow")
                table.add_column("Members", style="magenta")
                table.add_column("Coherence", style="blue")
                table.add_column("Created", style="white")

                for cluster in clusters:
                    table.add_row(
                        str(cluster.id),
                        cluster.name,
                        cluster.cluster_type,
                        str(cluster.member_count),
                        (
                            f"{cluster.cluster_coherence:.2%}"
                            if cluster.cluster_coherence
                            else "N/A"
                        ),
                        cluster.created_at.strftime("%Y-%m-%d"),
                    )

                console.print(table)
            else:
                console.print("❌ No speaker clusters found")

    except Exception as e:
        console.print(f"❌ Failed to list clusters: {e}")
        logger.error(f"Failed to list clusters: {e}")
        raise CliExit.error()


def load_transcript_data(transcript_file: Path) -> dict:
    """Load transcript data from file using I/O service."""
    try:
        from transcriptx.io.transcript_service import get_transcript_service

        service = get_transcript_service()
        # Use service for caching
        return service.load_transcript(str(transcript_file))
    except Exception as e:
        raise Exception(f"Failed to load transcript file: {e}")


def extract_speaker_segments(transcript_data: dict, speaker_name: str) -> list:
    """Extract segments for a specific speaker by name."""
    segments = []

    if isinstance(transcript_data, list):
        for segment in transcript_data:
            if segment.get("speaker") == speaker_name:
                segments.append(segment)
    elif isinstance(transcript_data, dict):
        # Handle different transcript formats
        if "segments" in transcript_data:
            for segment in transcript_data["segments"]:
                if segment.get("speaker") == speaker_name:
                    segments.append(segment)

    return segments


def extract_speaker_segments_by_id(transcript_data: dict, speaker_id: int) -> list:
    """Extract segments for a specific speaker by ID."""
    segments = []

    if isinstance(transcript_data, list):
        for segment in transcript_data:
            if segment.get("speaker_id") == speaker_id:
                segments.append(segment)
    elif isinstance(transcript_data, dict):
        # Handle different transcript formats
        if "segments" in transcript_data:
            for segment in transcript_data["segments"]:
                if segment.get("speaker_id") == speaker_id:
                    segments.append(segment)

    return segments
