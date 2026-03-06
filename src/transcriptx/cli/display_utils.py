from rich.console import Console


def show_banner() -> None:
    console = Console()
    console.print("========================================", style="bold blue")
    console.print("  🎤  TranscriptX - Transcript Analyzer  🎤", style="bold cyan")
    console.print("========================================", style="bold blue")


def show_current_config(config):
    print("\n[bold cyan]👀 Current Configuration[/bold cyan]")
    print("\n[bold]Analysis Settings:[/bold]")
    print(f"  • Sentiment window size: {config.analysis.sentiment_window_size}")
    print(f"  • Sentiment min confidence: {config.analysis.sentiment_min_confidence}")
    print(f"  • Emotion model: {config.analysis.emotion_model_name}")
    print(f"  • Emotion min confidence: {config.analysis.emotion_min_confidence}")
    print(f"  • NER labels: {', '.join(config.analysis.ner_labels)}")
    print(f"  • NER min confidence: {config.analysis.ner_min_confidence}")
    print(f"  • Word cloud max words: {config.analysis.wordcloud_max_words}")
    print(f"  • Word cloud min font size: {config.analysis.wordcloud_min_font_size}")
    print(f"  • Readability metrics: {', '.join(config.analysis.readability_metrics)}")
    print(
        f"  • Interaction overlap threshold: {config.analysis.interaction_overlap_threshold} seconds"
    )
    print(f"  • Interaction min gap: {config.analysis.interaction_min_gap} seconds")
    print(
        f"  • Interaction min segment length: {config.analysis.interaction_min_segment_length} seconds"
    )
    print(
        f"  • Interaction response threshold: {config.analysis.interaction_response_threshold} seconds"
    )
    print(
        f"  • Interaction include responses: {config.analysis.interaction_include_responses}"
    )
    print(
        f"  • Interaction include overlaps: {config.analysis.interaction_include_overlaps}"
    )
    print(f"  • Output formats: {', '.join(config.analysis.output_formats)}")
    print("\n[bold]Output Settings:[/bold]")
    print(f"  • Output directory: {config.output.base_output_dir}")
    print(f"  • Create subdirectories: {config.output.create_subdirectories}")
    print(f"  • Overwrite existing: {config.output.overwrite_existing}")
    print("\n[bold]Logging Settings:[/bold]")
    print(f"  • Log level: {config.logging.level}")
    print(f"  • File logging: {config.logging.file_logging}")
    print(f"  • Log file: {config.logging.log_file}")
    print(f"  • Max log size: {config.logging.max_log_size / (1024 * 1024):.1f} MB")
    print(f"  • Backup count: {config.logging.backup_count}")
