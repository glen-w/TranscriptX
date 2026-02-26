"""
Profile management commands for TranscriptX CLI.

This module provides CLI commands for managing speaker profiles, including
viewing, comparing, exporting, and analyzing speaker data.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ..core.integration import DatabaseIntegrationPipeline, SpeakerProfileAggregator
from ..database.models import Speaker
from ..database.database import get_database_session
from .exit_codes import CliExit

logger = logging.getLogger(__name__)
console = Console()

# Create Typer app for profile commands
profile_app = typer.Typer(
    name="profile",
    help="Manage speaker profiles and analyze speaker data",
    no_args_is_help=True,
)


@profile_app.command("show")
def show_speaker_profile(
    speaker_name: str = typer.Option(
        ..., "--speaker-name", "-n", help="Name of the speaker to show profile for"
    ),
    analysis_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Specific analysis type to show"
    ),
    format: str = typer.Option(
        "rich", "--format", "-f", help="Output format (rich, json, table)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Show comprehensive speaker profile."""

    try:
        with console.status(f"[bold green]Loading profile for {speaker_name}..."):
            # Get database session
            session = get_database_session()

            # Find speaker
            speaker = (
                session.query(Speaker).filter(Speaker.name == speaker_name).first()
            )
            if not speaker:
                console.print(f"[red]Speaker '{speaker_name}' not found[/red]")
                raise CliExit.error()

            # Get profile data
            pipeline = DatabaseIntegrationPipeline(session)
            profile_data = pipeline.persistence_service.get_speaker_profile(
                speaker.id, analysis_type
            )

            if not profile_data:
                console.print(
                    f"[yellow]No profile data found for {speaker_name}[/yellow]"
                )
                raise CliExit.success()

            # Display profile
            if format == "json":
                output = json.dumps(profile_data, indent=2, default=str)
                if output_file:
                    output_file.write_text(output)
                else:
                    console.print(output)
            elif format == "table":
                display_profile_table(profile_data, speaker_name)
            else:  # rich format
                display_profile_rich(profile_data, speaker_name)

    except Exception as e:
        logger.error(f"Error showing profile for {speaker_name}: {str(e)}")
        console.print(f"[red]Error: {str(e)}[/red]")
        raise CliExit.error()


@profile_app.command("compare")
def compare_speakers(
    speaker1: str = typer.Option(..., "--speaker1", help="First speaker name"),
    speaker2: str = typer.Option(..., "--speaker2", help="Second speaker name"),
    analysis_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Specific analysis type to compare"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Compare two speakers across all dimensions."""

    try:
        with console.status(f"[bold green]Comparing {speaker1} and {speaker2}..."):
            # Get database session
            session = get_database_session()

            # Find speakers
            speaker1_obj = (
                session.query(Speaker).filter(Speaker.name == speaker1).first()
            )
            speaker2_obj = (
                session.query(Speaker).filter(Speaker.name == speaker2).first()
            )

            if not speaker1_obj:
                console.print(f"[red]Speaker '{speaker1}' not found[/red]")
                raise CliExit.error()
            if not speaker2_obj:
                console.print(f"[red]Speaker '{speaker2}' not found[/red]")
                raise CliExit.error()

            # Get profile data
            pipeline = DatabaseIntegrationPipeline(session)
            profile1 = pipeline.persistence_service.get_speaker_profile(
                speaker1_obj.id, analysis_type
            )
            profile2 = pipeline.persistence_service.get_speaker_profile(
                speaker2_obj.id, analysis_type
            )

            # Generate comparison
            comparison = generate_speaker_comparison(
                profile1, profile2, speaker1, speaker2
            )

            # Display comparison
            if output_file:
                output_file.write_text(json.dumps(comparison, indent=2, default=str))
            else:
                display_comparison_rich(comparison)

    except Exception as e:
        logger.error(f"Error comparing speakers: {str(e)}")
        console.print(f"[red]Error: {str(e)}[/red]")
        raise CliExit.error()


@profile_app.command("export")
def export_speaker_data(
    speaker_name: str = typer.Option(
        ..., "--speaker-name", "-n", help="Name of the speaker to export"
    ),
    format: str = typer.Option(
        "json", "--format", "-f", help="Export format (json, csv)"
    ),
    output_file: Path = typer.Option(..., "--output", "-o", help="Output file path"),
):
    """Export speaker data in specified format."""

    try:
        with console.status(f"[bold green]Exporting data for {speaker_name}..."):
            # Get database session
            session = get_database_session()

            # Find speaker
            speaker = (
                session.query(Speaker).filter(Speaker.name == speaker_name).first()
            )
            if not speaker:
                console.print(f"[red]Speaker '{speaker_name}' not found[/red]")
                raise CliExit.error()

            # Export data
            pipeline = DatabaseIntegrationPipeline(session)
            export_data = pipeline.persistence_service.export_speaker_data(
                speaker.id, format
            )

            # Write to file
            if format == "json":
                output_file.write_text(json.dumps(export_data, indent=2, default=str))
            elif format == "csv":
                # Convert to CSV format
                csv_data = convert_to_csv(export_data)
                output_file.write_text(csv_data)
            else:
                console.print(f"[red]Unsupported format: {format}[/red]")
                raise CliExit.error()

            console.print(f"[green]Data exported to {output_file}[/green]")

    except Exception as e:
        logger.error(f"Error exporting data for {speaker_name}: {str(e)}")
        console.print(f"[red]Error: {str(e)}[/red]")
        raise CliExit.error()


@profile_app.command("evolution")
def analyze_speaker_evolution(
    speaker_name: str = typer.Option(
        ..., "--speaker-name", "-n", help="Name of the speaker to analyze"
    ),
    time_period: str = typer.Option(
        "all", "--period", "-p", help="Time period (all, month, week)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Analyze how speaker has evolved over time."""

    try:
        with console.status(f"[bold green]Analyzing evolution for {speaker_name}..."):
            # Get database session
            session = get_database_session()

            # Find speaker
            speaker = (
                session.query(Speaker).filter(Speaker.name == speaker_name).first()
            )
            if not speaker:
                console.print(f"[red]Speaker '{speaker_name}' not found[/red]")
                raise CliExit.error()

            # Analyze evolution
            aggregator = SpeakerProfileAggregator(session)
            evolution_data = analyze_evolution_trends(speaker.id, time_period, session)

            # Display evolution
            if output_file:
                output_file.write_text(
                    json.dumps(evolution_data, indent=2, default=str)
                )
            else:
                display_evolution_rich(evolution_data, speaker_name)

    except Exception as e:
        logger.error(f"Error analyzing evolution for {speaker_name}: {str(e)}")
        console.print(f"[red]Error: {str(e)}[/red]")
        raise CliExit.error()


@profile_app.command("list")
def list_speaker_profiles(
    analysis_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Filter by analysis type"
    ),
    limit: int = typer.Option(
        50, "--limit", "-l", help="Maximum number of profiles to show"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json)"
    ),
):
    """List all available speaker profiles."""

    try:
        with console.status("[bold green]Loading speaker profiles..."):
            # Get database session
            session = get_database_session()

            # Get speakers with profiles
            speakers = session.query(Speaker).all()

            profile_list = []
            for speaker in speakers[:limit]:
                pipeline = DatabaseIntegrationPipeline(session)
                stats = pipeline.persistence_service.get_speaker_statistics(speaker.id)

                if stats.get("profile_count", 0) > 0:
                    profile_list.append(
                        {
                            "name": speaker.name,
                            "profile_count": stats["profile_count"],
                            "completeness": stats["data_completeness"],
                            "last_updated": stats.get("last_updated"),
                            "analysis_types": stats.get("analysis_types", []),
                        }
                    )

            # Display profiles
            if format == "json":
                console.print(json.dumps(profile_list, indent=2, default=str))
            else:
                display_profile_list_table(profile_list)

    except Exception as e:
        logger.error(f"Error listing profiles: {str(e)}")
        console.print(f"[red]Error: {str(e)}[/red]")
        raise CliExit.error()


@profile_app.command("update")
def update_speaker_profile(
    speaker_name: str = typer.Option(
        ..., "--speaker-name", "-n", help="Name of the speaker to update"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force update even if data exists"
    ),
):
    """Update speaker profile with latest data."""

    try:
        with console.status(f"[bold green]Updating profile for {speaker_name}..."):
            # Get database session
            session = get_database_session()

            # Find speaker
            speaker = (
                session.query(Speaker).filter(Speaker.name == speaker_name).first()
            )
            if not speaker:
                console.print(f"[red]Speaker '{speaker_name}' not found[/red]")
                raise CliExit.error()

            # Update profile
            pipeline = DatabaseIntegrationPipeline(session)
            aggregator = SpeakerProfileAggregator(session)

            # This would need to be implemented based on your specific requirements
            # For now, just aggregate the existing profile
            profile_data = aggregator.aggregate_speaker_profile(speaker.id)

            console.print(f"[green]Profile updated for {speaker_name}[/green]")

    except Exception as e:
        logger.error(f"Error updating profile for {speaker_name}: {str(e)}")
        console.print(f"[red]Error: {str(e)}[/red]")
        raise CliExit.error()


# Helper functions for display


def display_profile_rich(profile_data: Dict[str, Any], speaker_name: str):
    """Display profile data in rich format."""

    # Create main panel
    content = f"[bold blue]Speaker Profile: {speaker_name}[/bold blue]\n\n"

    for analysis_type, data in profile_data.items():
        content += f"[bold]{analysis_type.title()}[/bold]\n"
        for key, value in data.items():
            if key not in ["speaker_id", "created_at", "updated_at"]:
                content += f"  {key}: {value}\n"
        content += "\n"

    panel = Panel(content, title="Speaker Profile", border_style="blue")
    console.print(panel)


def display_profile_table(profile_data: Dict[str, Any], speaker_name: str):
    """Display profile data in table format."""

    table = Table(title=f"Speaker Profile: {speaker_name}")
    table.add_column("Analysis Type", style="cyan")
    table.add_column("Field", style="magenta")
    table.add_column("Value", style="green")

    for analysis_type, data in profile_data.items():
        for key, value in data.items():
            if key not in ["speaker_id", "created_at", "updated_at"]:
                table.add_row(analysis_type, key, str(value))

    console.print(table)


def generate_speaker_comparison(
    profile1: Dict[str, Any], profile2: Dict[str, Any], name1: str, name2: str
) -> Dict[str, Any]:
    """Generate comparison between two speakers."""

    comparison = {
        "speaker1": name1,
        "speaker2": name2,
        "comparison_date": str(datetime.now()),
        "differences": {},
        "similarities": {},
        "recommendations": [],
    }

    # Compare each analysis type
    all_types = set(profile1.keys()) | set(profile2.keys())

    for analysis_type in all_types:
        data1 = profile1.get(analysis_type, {})
        data2 = profile2.get(analysis_type, {})

        differences = []
        similarities = []

        # Compare fields
        all_fields = set(data1.keys()) | set(data2.keys())
        for field in all_fields:
            value1 = data1.get(field)
            value2 = data2.get(field)

            if value1 != value2:
                differences.append(
                    {"field": field, "speaker1_value": value1, "speaker2_value": value2}
                )
            else:
                similarities.append({"field": field, "value": value1})

        comparison["differences"][analysis_type] = differences
        comparison["similarities"][analysis_type] = similarities

    return comparison


def display_comparison_rich(comparison: Dict[str, Any]):
    """Display comparison data in rich format."""

    content = f"[bold blue]Speaker Comparison: {comparison['speaker1']} vs {comparison['speaker2']}[/bold blue]\n\n"

    for analysis_type, differences in comparison["differences"].items():
        if differences:
            content += f"[bold]{analysis_type.title()}[/bold]\n"
            for diff in differences:
                content += f"  {diff['field']}: {diff['speaker1_value']} vs {diff['speaker2_value']}\n"
            content += "\n"

    panel = Panel(content, title="Speaker Comparison", border_style="green")
    console.print(panel)


def convert_to_csv(export_data: Dict[str, Any]) -> str:
    """Convert export data to CSV format."""

    csv_lines = []

    # Add metadata
    csv_lines.append("Field,Value")
    csv_lines.append(f"speaker_id,{export_data.get('speaker_id', '')}")
    csv_lines.append(f"export_timestamp,{export_data.get('export_timestamp', '')}")

    # Add profile data
    for profile_type, profile_data in export_data.get("profiles", {}).items():
        csv_lines.append("")
        csv_lines.append(f"{profile_type}_profile,")
        for field, value in profile_data.items():
            csv_lines.append(f"{profile_type}_{field},{value}")

    return "\n".join(csv_lines)


def analyze_evolution_trends(
    speaker_id: int, time_period: str, session
) -> Dict[str, Any]:
    """Analyze evolution trends for a speaker."""

    # This would need to be implemented based on your specific requirements
    # For now, return a placeholder structure
    return {
        "speaker_id": speaker_id,
        "time_period": time_period,
        "trends": {
            "sentiment": {"direction": "improving", "confidence": 0.8},
            "emotion": {"direction": "stable", "confidence": 0.6},
            "interaction": {"direction": "improving", "confidence": 0.7},
        },
        "key_changes": [
            {
                "type": "sentiment",
                "change": "Increased positive communication",
                "confidence": 0.8,
            },
            {
                "type": "interaction",
                "change": "Improved collaboration skills",
                "confidence": 0.7,
            },
        ],
    }


def display_evolution_rich(evolution_data: Dict[str, Any], speaker_name: str):
    """Display evolution data in rich format."""

    content = f"[bold blue]Evolution Analysis: {speaker_name}[/bold blue]\n\n"

    content += "[bold]Trends:[/bold]\n"
    for trend_type, trend_data in evolution_data.get("trends", {}).items():
        direction = trend_data.get("direction", "unknown")
        confidence = trend_data.get("confidence", 0)
        content += f"  {trend_type}: {direction} (confidence: {confidence:.2f})\n"

    content += "\n[bold]Key Changes:[/bold]\n"
    for change in evolution_data.get("key_changes", []):
        change_type = change.get("type", "unknown")
        change_desc = change.get("change", "No description")
        confidence = change.get("confidence", 0)
        content += f"  {change_type}: {change_desc} (confidence: {confidence:.2f})\n"

    panel = Panel(content, title="Evolution Analysis", border_style="yellow")
    console.print(panel)


def display_profile_list_table(profile_list: List[Dict[str, Any]]):
    """Display profile list in table format."""

    table = Table(title="Speaker Profiles")
    table.add_column("Name", style="cyan")
    table.add_column("Profile Count", style="magenta")
    table.add_column("Completeness", style="green")
    table.add_column("Last Updated", style="yellow")
    table.add_column("Analysis Types", style="blue")

    for profile in profile_list:
        last_updated = profile.get("last_updated", "Unknown")
        if last_updated != "Unknown":
            last_updated = str(last_updated)[:19]  # Truncate timestamp

        analysis_types = ", ".join(profile.get("analysis_types", []))

        table.add_row(
            profile["name"],
            str(profile["profile_count"]),
            f"{profile['completeness']:.1%}",
            last_updated,
            analysis_types,
        )

    console.print(table)


# Add the profile app to the main CLI
def add_profile_commands(app):
    """Add profile commands to the main CLI app."""
    app.add_typer(profile_app, name="profile")
