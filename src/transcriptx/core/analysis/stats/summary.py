"""Stats analysis module."""

import os
from datetime import datetime
from html import escape as html_escape

from transcriptx.utils.text_utils import format_time, is_eligible_named_speaker

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.artifact_writer import write_text
from transcriptx.core.analysis.tics import extract_tics_and_top_words

logger = get_logger()


def create_comprehensive_summary(
    transcript_dir: str,
    base_name: str,
    speaker_stats: list,
    sentiment_summary: dict,
    module_data: dict,
    *,
    ignored_ids: set[str] | None = None,
    speaker_key_aliases: dict[str, str] | None = None,
) -> str:
    """
    Create a comprehensive summary incorporating data from all modules.

    Args:
        transcript_dir: Directory containing analysis outputs
        base_name: Base name of the transcript
        speaker_stats: List of speaker statistics
        sentiment_summary: Sentiment summary dictionary
        module_data: Dictionary containing data from all modules

    Returns:
        Formatted summary string
    """
    summary_lines = []

    # Header
    summary_lines.append(f"📊 COMPREHENSIVE ANALYSIS SUMMARY: {base_name}")
    summary_lines.append("=" * 60)
    summary_lines.append("")

    def _eligible(display_name: str) -> bool:
        key = (
            speaker_key_aliases.get(display_name, display_name)
            if speaker_key_aliases
            else display_name
        )
        return is_eligible_named_speaker(display_name, key, ignored_ids or set())

    # Basic Statistics
    summary_lines.append("🎯 BASIC STATISTICS")
    summary_lines.append("-" * 20)
    summary_lines.append(
        f"{'Speaker':<22} {'Words':>7} {'Segments':>10} {'Duration':>10} {'Tic Rate':>10} {'Avg Segment':>14}"
    )
    summary_lines.append("-" * 70)
    for (
        duration,
        name,
        word_count,
        segment_count,
        tic_rate,
        avg_segment_len,
    ) in speaker_stats:
        summary_lines.append(
            f"{name:<22} {word_count:>7} {segment_count:>10} {format_time(duration):>10} {tic_rate:>9.2%} {avg_segment_len:>14.2f}"
        )
    summary_lines.append("")

    # Sentiment Analysis
    if sentiment_summary:
        summary_lines.append("😊 SENTIMENT ANALYSIS")
        summary_lines.append("-" * 20)
        summary_lines.append(
            f"{'Speaker':<22} {'Compound':>10} {'Positive':>10} {'Neutral':>10} {'Negative':>10}"
        )
        summary_lines.append("-" * 70)
        for speaker, scores in sentiment_summary.items():
            if not _eligible(speaker):
                continue
            compound = scores.get("compound", 0)
            pos = scores.get("pos", 0)
            neu = scores.get("neu", 0)
            neg = scores.get("neg", 0)
            summary_lines.append(
                f"{speaker:<22} {compound:>10.3f} {pos:>10.3f} {neu:>10.3f} {neg:>10.3f}"
            )
        summary_lines.append("")

    # Dialogue Acts
    if "acts" in module_data and module_data["acts"]:
        summary_lines.append("🗣️ DIALOGUE ACTS")
        summary_lines.append("-" * 15)
        for speaker, acts in module_data["acts"].items():
            if not _eligible(speaker):
                continue
            summary_lines.append(f"{speaker}:")
            for act, count in sorted(acts.items(), key=lambda x: x[1], reverse=True):
                summary_lines.append(f"  • {act}: {count}")
            summary_lines.append("")
    else:
        summary_lines.append(
            "🗣️ DIALOGUE ACTS\n  • No data available for this section.\n"
        )

    # Speaker Interactions
    if "interactions" in module_data and module_data["interactions"]:
        summary_lines.append("🤝 SPEAKER INTERACTIONS")
        summary_lines.append("-" * 22)
        if "speaker_summary" in module_data["interactions"]:
            for speaker_data in module_data["interactions"]["speaker_summary"]:
                speaker = speaker_data.get("speaker", "Unknown")
                if not _eligible(speaker):
                    continue
                interruptions_init = speaker_data.get("interruptions_initiated", 0)
                interruptions_rec = speaker_data.get("interruptions_received", 0)
                responses_init = speaker_data.get("responses_initiated", 0)
                responses_rec = speaker_data.get("responses_received", 0)
                dominance = speaker_data.get("dominance_score", 0)
                summary_lines.append(f"{speaker}:")
                summary_lines.append(
                    f"  • Interruptions: {interruptions_init} initiated, {interruptions_rec} received"
                )
                summary_lines.append(
                    f"  • Responses: {responses_init} initiated, {responses_rec} received"
                )
                summary_lines.append(f"  • Dominance Score: {dominance:.3f}")
                summary_lines.append("")
    else:
        summary_lines.append(
            "🤝 SPEAKER INTERACTIONS\n  • No data available for this section.\n"
        )

    # Emotion Analysis
    if "emotion" in module_data and module_data["emotion"]:
        summary_lines.append("😄 EMOTION ANALYSIS")
        summary_lines.append("-" * 18)
        if "speaker_emotions" in module_data["emotion"]:
            for speaker, emotions in module_data["emotion"]["speaker_emotions"].items():
                if not _eligible(speaker):
                    continue
                summary_lines.append(f"{speaker}:")
                for emotion, score in sorted(
                    emotions.items(), key=lambda x: x[1], reverse=True
                )[:5]:
                    summary_lines.append(f"  • {emotion}: {score:.3f}")
                summary_lines.append("")
    else:
        summary_lines.append(
            "😄 EMOTION ANALYSIS\n  • No data available for this section.\n"
        )

    # Named Entities
    if "ner" in module_data and module_data["ner"]:
        summary_lines.append("🏷️ NAMED ENTITIES")
        summary_lines.append("-" * 16)
        for speaker, entities in module_data["ner"].items():
            if not _eligible(speaker):
                continue
            summary_lines.append(f"{speaker}:")
            for entity, count in sorted(
                entities.items(), key=lambda x: x[1], reverse=True
            )[:5]:
                summary_lines.append(f"  • {entity}: {count}")
            summary_lines.append("")
    else:
        summary_lines.append(
            "🏷️ NAMED ENTITIES\n  • No data available for this section.\n"
        )

    # Entity Sentiment Analysis
    if "entity_sentiment" in module_data and module_data["entity_sentiment"]:
        summary_lines.append("🎯 ENTITY SENTIMENT ANALYSIS")
        summary_lines.append("-" * 26)
        for speaker, entities in module_data["entity_sentiment"].items():
            if not _eligible(speaker):
                continue
            summary_lines.append(f"{speaker}:")
            for entity, sentiment in sorted(
                entities.items(),
                key=lambda x: x[1].get("sentiment_score", 0),
                reverse=True,
            )[:5]:
                sentiment_score = sentiment.get("sentiment_score", 0)
                summary_lines.append(f"  • {entity}: {sentiment_score:.3f}")
            summary_lines.append("")
    else:
        summary_lines.append(
            "🎯 ENTITY SENTIMENT ANALYSIS\n  • No data available for this section.\n"
        )

    # Conversation Loops
    if "conversation_loops" in module_data and module_data["conversation_loops"]:
        summary_lines.append("🔄 CONVERSATION LOOPS")
        summary_lines.append("-" * 20)
        if "loops" in module_data["conversation_loops"]:
            loops = module_data["conversation_loops"]["loops"]
            summary_lines.append(f"Total loops detected: {len(loops)}")
            for i, loop in enumerate(loops[:5], 1):  # Show first 5 loops
                speakers = loop.get("speakers", [])
                topic = loop.get("topic", "Unknown topic")
                summary_lines.append(f"  {i}. {', '.join(speakers)} - {topic}")
            summary_lines.append("")
    else:
        summary_lines.append(
            "🔄 CONVERSATION LOOPS\n  • No data available for this section.\n"
        )

    # Emotional Contagion
    if "contagion" in module_data and module_data["contagion"]:
        summary_lines.append("😊 EMOTIONAL CONTAGION")
        summary_lines.append("-" * 21)
        if "contagion_events" in module_data["contagion"]:
            events = module_data["contagion"]["contagion_events"]
            summary_lines.append(f"Contagion events detected: {len(events)}")
            for i, event in enumerate(events[:5], 1):  # Show first 5 events
                source = event.get("source_speaker", "Unknown")
                target = event.get("target_speaker", "Unknown")
                emotion = event.get("emotion", "Unknown")
                strength = event.get("strength", 0)
                summary_lines.append(
                    f"  {i}. {source} → {target} ({emotion}, strength: {strength:.3f})"
                )
            summary_lines.append("")
    else:
        summary_lines.append(
            "😊 EMOTIONAL CONTAGION\n  • No data available for this section.\n"
        )

    # Key Insights
    summary_lines.append("💡 KEY INSIGHTS")
    summary_lines.append("-" * 13)

    # Most talkative speaker
    if speaker_stats:
        most_talkative = max(speaker_stats, key=lambda x: x[2])  # word count
        summary_lines.append(
            f"• Most talkative speaker: {most_talkative[1]} ({most_talkative[2]} words)"
        )

    # Most positive/negative speaker
    if sentiment_summary:
        most_positive = max(
            sentiment_summary.items(), key=lambda x: x[1].get("compound", 0)
        )
        most_negative = min(
            sentiment_summary.items(), key=lambda x: x[1].get("compound", 0)
        )
        summary_lines.append(
            f"• Most positive speaker: {most_positive[0]} (compound: {most_positive[1].get('compound', 0):.3f})"
        )
        summary_lines.append(
            f"• Most negative speaker: {most_negative[0]} (compound: {most_negative[1].get('compound', 0):.3f})"
        )

    # Most dominant speaker (from interactions)
    if "interactions" in module_data and module_data["interactions"]:
        if "speaker_summary" in module_data["interactions"]:
            speaker_summaries = module_data["interactions"]["speaker_summary"]
            if speaker_summaries:
                most_dominant = max(
                    speaker_summaries, key=lambda x: x.get("dominance_score", 0)
                )
                summary_lines.append(
                    f"• Most dominant speaker: {most_dominant.get('speaker', 'Unknown')} (score: {most_dominant.get('dominance_score', 0):.3f})"
                )

    # Most emotional speaker
    if "emotion" in module_data and module_data["emotion"]:
        if "speaker_emotions" in module_data["emotion"]:
            emotion_scores = {}
            for speaker, emotions in module_data["emotion"]["speaker_emotions"].items():
                if not _eligible(speaker):
                    continue
                emotion_scores[speaker] = sum(emotions.values())

            if emotion_scores:
                most_emotional = max(emotion_scores.items(), key=lambda x: x[1])
                summary_lines.append(
                    f"• Most emotional speaker: {most_emotional[0]} (total emotion score: {most_emotional[1]:.3f})"
                )

    summary_lines.append("")
    summary_lines.append(
        "📁 Detailed outputs available in module-specific directories:"
    )
    summary_lines.append("  • acts/ - Dialogue act analysis")
    summary_lines.append("  • interactions/ - Speaker interaction patterns")
    summary_lines.append("  • emotion/ - Emotion detection")
    summary_lines.append("  • sentiment/ - Sentiment analysis")
    summary_lines.append("  • data/cache/ - Location cache and data storage")
    summary_lines.append("  • entity_sentiment/ - Entity sentiment framing analysis")
    summary_lines.append("  • conversation_loops/ - Conversation loop detection")
    summary_lines.append("  • contagion/ - Emotional contagion analysis")
    summary_lines.append("  • wordclouds/ - Word frequency analysis")
    summary_lines.append("  • tics/ - Verbal tics and filler words")

    return "\n".join(summary_lines)


def generate_summary_stats(
    segments: list,
    base_name: str,
    transcript_dir: str,
    speaker_map: dict,
    *,
    ignored_ids: set[str] | None = None,
    speaker_key_aliases: dict[str, str] | None = None,
):
    """
    Generate comprehensive summary statistics from transcript segments.

    Args:
        segments: List of transcript segments
        base_name: Base name for output files
        transcript_dir: Directory to save outputs
        speaker_map: Speaker ID to name mapping
    """
    # Create output directories
    stats_dir = os.path.join(transcript_dir, "stats")
    os.makedirs(stats_dir, exist_ok=True)

    def _eligible(display_name: str) -> bool:
        key = (
            speaker_key_aliases.get(display_name, display_name)
            if speaker_key_aliases
            else display_name
        )
        return is_eligible_named_speaker(display_name, key, ignored_ids or set())

    # Group text by speaker
    grouped = {}
    for seg in segments:
        raw_id = seg.get("speaker")
        name = speaker_map.get(raw_id, raw_id)
        if not _eligible(str(name)):
            continue
        grouped.setdefault(name, []).append(seg.get("text", ""))

    # Load tics
    tic_list = extract_tics_and_top_words(grouped)
    # Convert to list if it's a tuple
    if isinstance(tic_list, tuple):
        tic_list = list(tic_list)

    # Compute speaker statistics
    speaker_stats, sentiment_summary = compute_speaker_stats(
        grouped, segments, speaker_map, tic_list, ignored_ids=ignored_ids
    )

    # Load module data
    module_data = load_module_data(transcript_dir, base_name)

    # Create comprehensive summary text
    summary_text = create_comprehensive_summary(
        transcript_dir,
        base_name,
        speaker_stats,
        sentiment_summary,
        module_data,
        ignored_ids=ignored_ids,
        speaker_key_aliases=speaker_key_aliases,
    )

    # Save summary text
    txt_file = os.path.join(stats_dir, f"{base_name}_comprehensive_summary.txt")
    write_text(txt_file, summary_text)

    # HTML summary output removed (superseded by browser GUI)


def generate_enhanced_html_summary(
    transcript_dir: str, base_name: str, module_data: dict, speaker_map: dict
):
    """
    Generate an enhanced HTML summary with comprehensive chart explanations and better organization.

    Args:
        transcript_dir: Directory containing analysis results
        base_name: Base name for output files
        module_data: Dictionary containing module analysis data
        speaker_map: Speaker ID to name mapping
    """
    html_file = os.path.join(transcript_dir, f"{base_name}_comprehensive_summary.html")

    try:
        # Get current timestamp
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Find all chart images in transcript_dir and subfolders
        chart_imgs = []
        image_exts = (".png", ".jpg", ".jpeg", ".svg")
        for root, dirs, files in os.walk(transcript_dir):
            for f in files:
                if f.lower().endswith(image_exts):
                    rel = os.path.relpath(
                        os.path.join(root, f), os.path.dirname(html_file)
                    )
                    chart_imgs.append(rel)
        chart_imgs.sort()

        # Find HTML files (maps, etc.)
        html_files = []
        for root, dirs, files in os.walk(transcript_dir):
            for f in files:
                if f.lower().endswith(".html"):
                    rel = os.path.relpath(
                        os.path.join(root, f), os.path.dirname(html_file)
                    )
                    html_files.append(rel)

        # Group HTML files by module
        module_html_files = {}
        for html_file_path in html_files:
            html_name = os.path.basename(html_file_path).lower()
            module = "other"
            if "location" in html_name or "map" in html_name:
                module = "ner"
            elif "contagion" in html_name or "emotional" in html_name:
                module = "contagion"

            if module not in module_html_files:
                module_html_files[module] = []
            module_html_files[module].append(html_file_path)

        # Group images by module with improved logic
        module_images = {}
        for img in chart_imgs:
            img_name = os.path.basename(img).lower()
            module = "other"
            if "sentiment" in img_name:
                module = "sentiment"
            elif "emotion" in img_name and not (
                "map" in img_name or "contagion" in img_name
            ):
                module = "emotion"
            elif "acts" in img_name:
                module = "acts"
            elif "interaction" in img_name:
                module = "interactions"
            elif "ner" in img_name or "location" in img_name:
                module = "ner"
            elif "entity" in img_name:
                module = "entity-sentiment"
            elif "loop" in img_name or "pattern" in img_name:
                module = "conversation-loops"
            elif (
                "contagion" in img_name
                or "emotional_map" in img_name
                or ("map" in img_name and "emotion" in img_name)
            ):
                module = "contagion"
            elif "temporal" in img_name or "stats" in img_name or "summary" in img_name:
                module = "stats"
            elif (
                "radar" in img_name or "dominance" in img_name or "heatmap" in img_name
            ):
                # Move these to their own sections
                if "radar" in img_name:
                    module = "emotion-radars"
                elif "dominance" in img_name:
                    module = "meeting-dominance"
                elif "heatmap" in img_name:
                    module = "interaction-heatmaps"
            elif "topic" in img_name:
                module = "topic-modeling"
            elif "semantic" in img_name or "similarity" in img_name:
                module = "semantic-similarity"
            elif "wordcloud" in img_name or "word_cloud" in img_name:
                module = "wordclouds"
            elif "readability" in img_name or "understandability" in img_name:
                module = "readability"
            elif "tics" in img_name:
                module = "tics"
            if module not in module_images:
                module_images[module] = []
            module_images[module].append(img)

        # Generate the enhanced HTML content
        html_content = create_enhanced_html_content(
            base_name, now, module_images, module_html_files, module_data, speaker_map
        )

        # Write HTML file
        write_text(html_file, html_content)
        print(f"[green]✅ Enhanced HTML summary saved: {html_file}[/green]")

    except Exception as e:
        print(f"[yellow]Warning: Could not export enhanced HTML summary: {e}[/yellow]")


def create_enhanced_html_content(
    base_name: str,
    timestamp: str,
    module_images: dict,
    module_html_files: dict,
    module_data: dict,
    speaker_map: dict,
) -> str:
    """
    Create enhanced HTML content with comprehensive chart explanations.
    """
    # Define comprehensive module information
    modules_info = {
        "sentiment": {
            "name": "Sentiment Analysis",
            "description": "Analysis of overall emotional tone and sentiment trends throughout the conversation",
            "chart_explanations": {
                "timeline": "Shows sentiment changes over time, helping identify emotional shifts and key moments",
                "distribution": "Displays the overall distribution of positive, negative, and neutral sentiments",
                "speaker_comparison": "Compares sentiment patterns between different speakers",
                "scores": "Quantitative sentiment scores for different categories and time periods",
            },
        },
        "emotion": {
            "name": "Emotion Detection",
            "description": "Detection and analysis of specific emotions expressed by speakers",
            "chart_explanations": {
                "timeline": "Tracks emotional changes over time, showing when different emotions peak",
                "distribution": "Shows the frequency of different emotions across the conversation",
                "speaker_emotions": "Individual speaker emotional profiles and patterns",
                "emotion_network": "Visual representation of how emotions connect and influence each other",
            },
        },
        "emotion-radars": {
            "name": "Emotion Radar Charts",
            "description": "Radar charts showing the distribution of emotions for each speaker",
            "chart_explanations": {
                "radar_chart": "Each axis represents an emotion category. Distance from center shows frequency. Larger areas indicate more diverse emotional expression.",
                "comparison": "Side-by-side radar charts allow easy comparison of emotional profiles between speakers",
            },
        },
        "acts": {
            "name": "Dialogue Acts",
            "description": "Classification of speech acts and conversation structure patterns",
            "chart_explanations": {
                "distribution": "Shows the frequency of different types of speech acts (questions, statements, etc.)",
                "timeline": "Tracks dialogue act patterns over time, revealing conversation flow",
                "speaker_acts": "Individual speaker tendencies for different types of speech acts",
                "transition_matrix": "Shows how different speech acts follow each other in conversation",
            },
        },
        "interactions": {
            "name": "Speaker Interactions",
            "description": "Analysis of interruptions, responses, and interaction patterns between speakers",
            "chart_explanations": {
                "network": "Network diagram showing who interacts with whom. Node size indicates activity level, edge thickness shows interaction frequency",
                "timeline": "Chronological view of interactions, showing conversation flow and turn-taking patterns",
                "dominance": "Analysis of which speakers dominate conversations and control flow",
                "response_patterns": "Shows typical response patterns and conversation dynamics",
            },
        },
        "interaction-heatmaps": {
            "name": "Interaction Heatmaps",
            "description": "Heatmaps showing the intensity and frequency of interactions between speakers",
            "chart_explanations": {
                "heatmap": "Color intensity represents interaction frequency. Darker colors indicate more frequent interactions between speaker pairs",
                "temporal_heatmap": "Shows how interaction patterns change over time during the conversation",
            },
        },
        "meeting-dominance": {
            "name": "Meeting Dominance Analysis",
            "description": "Visualization of speaker dominance patterns and influence in the conversation",
            "chart_explanations": {
                "dominance_network": "Node size represents dominance score. Larger nodes indicate more influential speakers. Edge thickness shows dominance relationships",
                "influence_flow": "Arrows show direction of influence between speakers",
                "centrality": "Identifies the most central and influential speakers in the conversation",
            },
        },
        "ner": {
            "name": "Named Entity Recognition",
            "description": "Identification and analysis of people, places, organizations, and other entities mentioned",
            "chart_explanations": {
                "entity_distribution": "Shows frequency of different types of entities (people, places, organizations)",
                "location_map": "Geographic visualization of mentioned locations",
                "entity_network": "Network showing relationships between different entities",
                "temporal_entities": "Timeline of when different entities are mentioned",
            },
        },
        "entity-sentiment": {
            "name": "Entity Sentiment Analysis",
            "description": "Analysis of how specific entities are discussed and the sentiment associated with them",
            "chart_explanations": {
                "sentiment_heatmap": "Shows sentiment associated with different entities. Colors indicate positive (green) or negative (red) sentiment",
                "entity_emotions": "Emotional analysis of how different entities are discussed",
                "sentiment_timeline": "How sentiment toward specific entities changes over time",
            },
        },
        "conversation-loops": {
            "name": "Conversation Loops",
            "description": "Identification of repeated conversation patterns and circular discussions",
            "chart_explanations": {
                "loop_detection": "Identifies circular or repetitive conversation patterns",
                "pattern_analysis": "Shows recurring themes and topics that return throughout the conversation",
                "loop_network": "Network visualization of how conversation loops connect and influence each other",
            },
        },
        "contagion": {
            "name": "Emotional Contagion",
            "description": "Analysis of how emotions spread and influence between speakers during the conversation",
            "chart_explanations": {
                "contagion_network": "Arrows show emotional influence between speakers. Thickness indicates strength of influence",
                "emotion_flow": "Timeline showing how emotions spread from one speaker to another",
                "influence_matrix": "Quantitative analysis of emotional influence patterns",
            },
        },
        "topic-modeling": {
            "name": "Topic Modeling",
            "description": "Identification and analysis of main topics and themes in the conversation",
            "chart_explanations": {
                "topic_distribution": "Shows the prevalence of different topics throughout the conversation",
                "topic_evolution": "Timeline showing how topics emerge, develop, and fade over time",
                "topic_network": "Network showing relationships between different topics",
                "speaker_topics": "Analysis of which speakers contribute to which topics",
                "word_clouds": "Visual representation of key terms associated with each topic",
            },
        },
        "semantic-similarity": {
            "name": "Semantic Similarity Analysis",
            "description": "Analysis of semantic similarity and repetition patterns in the conversation",
            "chart_explanations": {
                "similarity_heatmap": "Shows semantic similarity between different parts of the conversation",
                "repetition_analysis": "Identifies repeated phrases, concepts, or ideas",
                "similarity_network": "Network showing semantic connections between different segments",
            },
        },
        "wordclouds": {
            "name": "Word Clouds",
            "description": "Visual representation of the most frequently used words and phrases",
            "chart_explanations": {
                "global_wordcloud": "Overall most frequent words across the entire conversation",
                "speaker_wordclouds": "Individual word clouds for each speaker, showing their unique vocabulary",
                "topic_wordclouds": "Word clouds for specific topics or themes",
            },
        },
        "readability": {
            "name": "Readability Analysis",
            "description": "Analysis of text complexity and readability metrics",
            "chart_explanations": {
                "readability_scores": "Various readability metrics (Flesch, Gunning Fog, etc.)",
                "complexity_timeline": "How text complexity changes over time",
                "speaker_complexity": "Readability comparison between different speakers",
            },
        },
        "tics": {
            "name": "Speech Tics Analysis",
            "description": "Analysis of speech patterns, filler words, and repetitive phrases",
            "chart_explanations": {
                "tic_frequency": "Frequency of different speech tics and filler words",
                "speaker_tics": "Individual speaker tic patterns and habits",
                "tic_timeline": "How speech tics change over time during the conversation",
            },
        },
        "stats": {
            "name": "Statistics & Summary",
            "description": "Overall metrics, statistics, and comprehensive summary data",
            "chart_explanations": {
                "summary_stats": "Key statistics about the conversation (duration, word count, speaker participation)",
                "temporal_analysis": "Time-based analysis of conversation patterns",
                "participation_metrics": "Quantitative analysis of speaker participation and engagement",
            },
        },
    }

    # Start building HTML content
    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>Comprehensive Analysis Summary - {html_escape(base_name)}</title>",
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">',
        '<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">',
        "<style>",
        """
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .main-container { 
            background: white; 
            border-radius: 15px; 
            box-shadow: 0 20px 40px rgba(0,0,0,0.1); 
            margin: 20px auto; 
            overflow: hidden;
        }
        .header-section {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }
        .header-section h1 {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        .header-section .subtitle {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        .content-section {
            padding: 2rem;
        }
        .module-card {
            border: none;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            margin-bottom: 2rem;
            overflow: hidden;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .module-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }
        .module-header {
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            border-bottom: 1px solid #e2e8f0;
            padding: 1.5rem;
            cursor: pointer;
            transition: background 0.3s ease;
        }
        .module-header:hover {
            background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e1 100%);
        }
        .module-header h3 {
            margin: 0;
            color: #1e293b;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .module-content {
            padding: 1.5rem;
            background: #fafbfc;
        }
        .chart-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 1.5rem;
            margin: 1.5rem 0;
        }
        .chart-item {
            background: white;
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            text-align: center;
        }
        .chart-item img {
            max-width: 100%;
            height: auto;
            border-radius: 6px;
            cursor: pointer;
            transition: transform 0.3s ease;
        }
        .chart-item img:hover {
            transform: scale(1.05);
        }
        .chart-caption {
            margin-top: 0.5rem;
            font-size: 0.9rem;
            color: #64748b;
            font-weight: 500;
        }
        .explanation-box {
            background: #f1f5f9;
            border-left: 4px solid #3b82f6;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 0 6px 6px 0;
        }
        .explanation-box h5 {
            color: #1e40af;
            margin-bottom: 0.5rem;
        }
        .toc {
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        .toc h4 {
            color: #1e293b;
            margin-bottom: 1rem;
        }
        .toc .nav-link {
            color: #475569;
            text-decoration: none;
            padding: 0.5rem 0;
            display: block;
            border-radius: 6px;
            transition: all 0.3s ease;
        }
        .toc .nav-link:hover {
            background: #e2e8f0;
            color: #1e40af;
            padding-left: 0.5rem;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin: 1.5rem 0;
        }
        .stat-card {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: #3b82f6;
        }
        .stat-label {
            color: #64748b;
            font-size: 0.9rem;
            margin-top: 0.5rem;
        }
        .modal-content {
            border-radius: 12px;
            border: none;
        }
        .modal-header {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            border-radius: 12px 12px 0 0;
        }
        .btn-close {
            filter: invert(1);
        }
        .accordion-button:not(.collapsed) {
            background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e1 100%);
            color: #1e40af;
        }
        .accordion-button:focus {
            box-shadow: 0 0 0 0.25rem rgba(59, 130, 246, 0.25);
        }
        """,
        "</style>",
        "</head>",
        "<body>",
        '<div class="container-fluid">',
        '<div class="main-container">',
        # Header
        '<div class="header-section">',
        '<h1><i class="fas fa-chart-line me-3"></i>Comprehensive Analysis Summary</h1>',
        f'<div class="subtitle">Meeting: {html_escape(base_name)}</div>',
        f'<div class="subtitle">Generated: {timestamp}</div>',
        "</div>",
        # Content
        '<div class="content-section">',
        # Table of Contents
        '<div class="toc">',
        '<h4><i class="fas fa-list me-2"></i>Table of Contents</h4>',
        '<div class="row">',
    ]

    # Add TOC links
    for module_id, info in modules_info.items():
        if module_id in module_images and module_images[module_id]:
            html_parts.append('<div class="col-md-6 col-lg-4">')
            html_parts.append(f'<a href="#{module_id}" class="nav-link">')
            html_parts.append(
                f'<i class="fas fa-chevron-right me-2"></i>{info["name"]}'
            )
            html_parts.append("</a></div>")

    html_parts.extend(
        [
            "</div>",
            "</div>",
            # Overview section
            '<div class="row mb-4">',
            '<div class="col-12">',
            '<div class="card module-card">',
            '<div class="module-header">',
            '<h3><i class="fas fa-info-circle me-2"></i>Analysis Overview</h3>',
            "</div>",
            '<div class="module-content">',
            '<p class="lead">This comprehensive analysis examines multiple dimensions of the conversation using advanced natural language processing and machine learning techniques.</p>',
            '<div class="stats-grid">',
            f'<div class="stat-card"><div class="stat-value">{len(speaker_map)}</div><div class="stat-label">Speakers</div></div>',
            f'<div class="stat-card"><div class="stat-value">{len(module_images)}</div><div class="stat-label">Analysis Modules</div></div>',
            f'<div class="stat-card"><div class="stat-value">{sum(len(imgs) for imgs in module_images.values())}</div><div class="stat-label">Visualizations</div></div>',
            "</div>",
            '<div class="explanation-box">',
            '<h5><i class="fas fa-lightbulb me-2"></i>How to Use This Report</h5>',
            "<p>Each section below contains detailed visualizations and explanations. Click on any chart to view it in full size. The analysis covers sentiment, emotions, topics, interactions, and more to provide a complete understanding of the conversation dynamics.</p>",
            "</div>",
            "</div>",
            "</div>",
            "</div>",
            "</div>",
        ]
    )

    # Add module sections
    for module_id, info in modules_info.items():
        if module_id in module_images and module_images[module_id]:
            html_parts.extend(
                [
                    f'<div class="card module-card" id="{module_id}">',
                    '<div class="module-header" data-bs-toggle="collapse" data-bs-target="#'
                    + module_id
                    + '-content">',
                    f'<h3><i class="fas fa-chart-bar me-2"></i>{info["name"]}</h3>',
                    '<i class="fas fa-chevron-down"></i>',
                    "</div>",
                    f'<div class="collapse" id="{module_id}-content">',
                    '<div class="module-content">',
                    f'<p class="lead">{info["description"]}</p>',
                ]
            )

            # Add chart explanations
            if "chart_explanations" in info:
                html_parts.append('<div class="explanation-box">')
                html_parts.append(
                    '<h5><i class="fas fa-info-circle me-2"></i>Understanding the Charts</h5>'
                )
                for chart_type, explanation in info["chart_explanations"].items():
                    html_parts.append(
                        f'<p><strong>{chart_type.replace("_", " ").title()}:</strong> {explanation}</p>'
                    )
                html_parts.append("</div>")

            # Add charts
            html_parts.append('<div class="chart-grid">')
            for img in module_images[module_id]:
                img_name = os.path.basename(img)
                html_parts.extend(
                    [
                        '<div class="chart-item">',
                        f'<img src="{img}" alt="{img_name}" class="img-fluid" data-bs-toggle="modal" data-bs-target="#imageModal" data-img-src="{img}">',
                        f'<div class="chart-caption">{img_name}</div>',
                        "</div>",
                    ]
                )
            html_parts.append("</div>")

            # Add module data if available
            if module_id in module_data and module_data[module_id]:
                summary_text = str(module_data[module_id])
                if (
                    not (summary_text.startswith("{") and summary_text.endswith("}"))
                    and len(summary_text) < 500
                ):
                    html_parts.extend(
                        [
                            '<div class="explanation-box">',
                            '<h5><i class="fas fa-clipboard-list me-2"></i>Summary</h5>',
                            f"<p>{summary_text}</p>",
                            "</div>",
                        ]
                    )

            # Add HTML files if available
            if module_id in module_html_files and module_html_files[module_id]:
                html_parts.append('<div class="explanation-box">')
                html_parts.append(
                    '<h5><i class="fas fa-globe me-2"></i>Interactive Visualizations</h5>'
                )
                for html_file_path in module_html_files[module_id]:
                    html_parts.append(
                        f'<p><a href="{html_file_path}" target="_blank" class="btn btn-outline-primary btn-sm me-2">'
                    )
                    html_parts.append(
                        f'<i class="fas fa-external-link-alt me-1"></i>{os.path.basename(html_file_path)}</a></p>'
                    )
                html_parts.append("</div>")

            html_parts.extend(["</div>", "</div>", "</div>"])

    # Add any remaining images in "Other Visualizations" section
    if "other" in module_images and module_images["other"]:
        html_parts.extend(
            [
                '<div class="card module-card" id="other">',
                '<div class="module-header" data-bs-toggle="collapse" data-bs-target="#other-content">',
                '<h3><i class="fas fa-images me-2"></i>Other Visualizations</h3>',
                '<i class="fas fa-chevron-down"></i>',
                "</div>",
                '<div class="collapse" id="other-content">',
                '<div class="module-content">',
                '<p class="lead">Additional visualizations and charts from the analysis.</p>',
                '<div class="chart-grid">',
            ]
        )

        for img in module_images["other"]:
            img_name = os.path.basename(img)
            html_parts.extend(
                [
                    '<div class="chart-item">',
                    f'<img src="{img}" alt="{img_name}" class="img-fluid" data-bs-toggle="modal" data-bs-target="#imageModal" data-img-src="{img}">',
                    f'<div class="chart-caption">{img_name}</div>',
                    "</div>",
                ]
            )

        html_parts.extend(["</div>", "</div>", "</div>", "</div>"])

    # Add modal for image viewing
    html_parts.extend(
        [
            # Image Modal
            '<div class="modal fade" id="imageModal" tabindex="-1">',
            '<div class="modal-dialog modal-xl">',
            '<div class="modal-content">',
            '<div class="modal-header">',
            '<h5 class="modal-title"><i class="fas fa-image me-2"></i>Chart Viewer</h5>',
            '<button type="button" class="btn-close" data-bs-dismiss="modal"></button>',
            "</div>",
            '<div class="modal-body text-center">',
            '<img id="modalImage" class="img-fluid" style="max-height: 80vh;">',
            "</div>",
            "</div>",
            "</div>",
            "</div>",
            # Footer
            '<div class="text-center py-4" style="background: #f8fafc; border-top: 1px solid #e2e8f0;">',
            f'<p class="text-muted mb-0">Generated by TranscriptX • {timestamp}</p>',
            "</div>",
            "</div>",
            "</div>",
            "</div>",
            # Scripts
            '<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>',
            "<script>",
            """
        // Image modal functionality
        document.getElementById('imageModal').addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const imgSrc = button.getAttribute('data-img-src');
            const modalImage = document.getElementById('modalImage');
            modalImage.src = imgSrc;
        });
        
        // Smooth scrolling for TOC links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
        """,
            "</script>",
            "</body>",
            "</html>",
        ]
    )

    return "\n".join(html_parts)
