"""Configuration display utilities."""

from rich import print

from transcriptx.utils.text_utils import strip_emojis


def show_current_config(config):
    """Show current configuration."""
    print("\n[bold cyan]👀 Current Configuration[/bold cyan]")

    print("\n[bold]Analysis Settings:[/bold]")
    msg = f"  • Sentiment window size: {config.analysis.sentiment_window_size}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Sentiment min confidence: {config.analysis.sentiment_min_confidence}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Emotion model: {config.analysis.emotion_model_name}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Emotion min confidence: {config.analysis.emotion_min_confidence}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • NER labels: {', '.join(config.analysis.ner_labels)}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • NER min confidence: {config.analysis.ner_min_confidence}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Word cloud max words: {config.analysis.wordcloud_max_words}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Word cloud min font size: {config.analysis.wordcloud_min_font_size}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Readability metrics: {', '.join(config.analysis.readability_metrics)}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Interaction min interactions: {config.analysis.interaction_min_interactions}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Interaction time window: {config.analysis.interaction_time_window}s"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Output formats: {', '.join(config.analysis.output_formats)}"
    print(strip_emojis(msg) if not config.use_emojis else msg)

    print("\n[bold]Transcription Settings:[/bold]")
    msg = f"  • Model: {config.transcription.model_name}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Compute type: {config.transcription.compute_type}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Language: {config.transcription.language or 'Auto-detect'}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Batch size: {config.transcription.batch_size}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Diarization: {config.transcription.diarize}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Min speakers: {config.transcription.min_speakers}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Max speakers: {config.transcription.max_speakers if config.transcription.max_speakers is not None else 'no limit'}"
    print(strip_emojis(msg) if not config.use_emojis else msg)

    print("\n[bold]Output Settings:[/bold]")
    msg = f"  • Output directory: {config.output.base_output_dir}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Create subdirectories: {config.output.create_subdirectories}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Overwrite existing: {config.output.overwrite_existing}"
    print(strip_emojis(msg) if not config.use_emojis else msg)

    print("\n[bold]Group Analysis Settings:[/bold]")
    msg = f"  • Enabled: {config.group_analysis.enabled}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Group output directory: {config.group_analysis.output_dir}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Persist groups: {config.group_analysis.persist_groups}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Stats aggregation: {config.group_analysis.enable_stats_aggregation}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Scaffold by_session: {config.group_analysis.scaffold_by_session}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Scaffold by_speaker: {config.group_analysis.scaffold_by_speaker}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Scaffold comparisons: {config.group_analysis.scaffold_comparisons}"
    print(strip_emojis(msg) if not config.use_emojis else msg)

    print("\n[bold]Logging Settings:[/bold]")
    msg = f"  • Log level: {config.logging.level}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • File logging: {config.logging.file_logging}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Log file: {config.logging.log_file}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Max log size: {config.logging.max_log_size / (1024*1024):.1f} MB"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Backup count: {config.logging.backup_count}"
    print(strip_emojis(msg) if not config.use_emojis else msg)

    print("\n[bold]Audio Preprocessing Settings:[/bold]")
    msg = f"  • Global mode: {config.audio_preprocessing.preprocessing_mode}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Convert to mono: {config.audio_preprocessing.convert_to_mono}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Downsample: {config.audio_preprocessing.downsample}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Target sample rate: {config.audio_preprocessing.target_sample_rate} Hz"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = (
        f"  • Skip if compliant: {config.audio_preprocessing.skip_if_already_compliant}"
    )
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Normalize mode: {config.audio_preprocessing.normalize_mode}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Target LUFS: {config.audio_preprocessing.target_lufs}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Limiter enabled: {config.audio_preprocessing.limiter_enabled}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Denoise mode: {config.audio_preprocessing.denoise_mode}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Denoise strength: {config.audio_preprocessing.denoise_strength}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • High-pass mode: {config.audio_preprocessing.highpass_mode}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • High-pass cutoff: {config.audio_preprocessing.highpass_cutoff} Hz"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Low-pass mode: {config.audio_preprocessing.lowpass_mode}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Low-pass cutoff: {config.audio_preprocessing.lowpass_cutoff} Hz"
    print(strip_emojis(msg) if not config.use_emojis else msg)
    msg = f"  • Band-pass mode: {config.audio_preprocessing.bandpass_mode}"
    print(strip_emojis(msg) if not config.use_emojis else msg)
