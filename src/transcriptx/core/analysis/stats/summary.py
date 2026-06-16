"""Stats summary surface.

The legacy HTML export path in this module is compatibility-only.
Primary report outputs are report.json, report.md, and report.txt.
"""

import os
import warnings
from datetime import datetime
from html import escape as html_escape
from typing import Callable, NamedTuple

from transcriptx.utils.text_utils import format_time, is_eligible_named_speaker

from transcriptx.core.analysis.stats.summary_legacy_html import (
    LEGACY_HTML_MODULES_INFO,
    classify_html_module,
    classify_image_module,
)
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.artifact_writer import write_text

logger = get_logger()


class SummarySectionSpec(NamedTuple):
    renderer: Callable[[], list[str]]


def _make_speaker_eligibility(
    ignored_ids: set[str] | None,
    speaker_key_aliases: dict[str, str] | None,
):
    def _eligible(display_name: str) -> bool:
        key = (
            speaker_key_aliases.get(display_name, display_name)
            if speaker_key_aliases
            else display_name
        )
        return is_eligible_named_speaker(display_name, key, ignored_ids or set())

    return _eligible


def _render_basic_statistics_section(speaker_stats: list) -> list[str]:
    lines = [
        "🎯 BASIC STATISTICS",
        "-" * 20,
        f"{'Speaker':<22} {'Words':>7} {'Segments':>10} {'Duration':>10} {'Tic Rate':>10} {'Avg Segment':>14}",
        "-" * 70,
    ]
    for (
        duration,
        name,
        word_count,
        segment_count,
        tic_rate,
        avg_segment_len,
    ) in speaker_stats:
        lines.append(
            f"{name:<22} {word_count:>7} {segment_count:>10} {format_time(duration):>10} {tic_rate:>9.2%} {avg_segment_len:>14.2f}"
        )
    lines.append("")
    return lines


def _render_sentiment_section(sentiment_summary: dict, eligible) -> list[str]:
    if not sentiment_summary:
        return []
    lines = [
        "😊 SENTIMENT ANALYSIS",
        "-" * 20,
        f"{'Speaker':<22} {'Compound':>10} {'Positive':>10} {'Neutral':>10} {'Negative':>10}",
        "-" * 70,
    ]
    for speaker, scores in sentiment_summary.items():
        if not eligible(speaker):
            continue
        compound = scores.get("compound", 0)
        pos = scores.get("pos", 0)
        neu = scores.get("neu", 0)
        neg = scores.get("neg", 0)
        lines.append(
            f"{speaker:<22} {compound:>10.3f} {pos:>10.3f} {neu:>10.3f} {neg:>10.3f}"
        )
    lines.append("")
    return lines


def _render_dialogue_acts_section(module_data: dict, eligible) -> list[str]:
    if "acts" not in module_data or not module_data["acts"]:
        return ["🗣️ DIALOGUE ACTS\n  • No data available for this section.\n"]
    lines = ["🗣️ DIALOGUE ACTS", "-" * 15]
    for speaker, acts in module_data["acts"].items():
        if not eligible(speaker):
            continue
        lines.append(f"{speaker}:")
        for act, count in sorted(acts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  • {act}: {count}")
        lines.append("")
    return lines


def _render_interactions_section(module_data: dict, eligible) -> list[str]:
    if "interactions" not in module_data or not module_data["interactions"]:
        return ["🤝 SPEAKER INTERACTIONS\n  • No data available for this section.\n"]
    lines = ["🤝 SPEAKER INTERACTIONS", "-" * 22]
    if "speaker_summary" in module_data["interactions"]:
        for speaker_data in module_data["interactions"]["speaker_summary"]:
            speaker = speaker_data.get("speaker", "Unknown")
            if not eligible(speaker):
                continue
            interruptions_init = speaker_data.get("interruptions_initiated", 0)
            interruptions_rec = speaker_data.get("interruptions_received", 0)
            responses_init = speaker_data.get("responses_initiated", 0)
            responses_rec = speaker_data.get("responses_received", 0)
            dominance = speaker_data.get("dominance_score", 0)
            lines.append(f"{speaker}:")
            lines.append(
                f"  • Interruptions: {interruptions_init} initiated, {interruptions_rec} received"
            )
            lines.append(
                f"  • Responses: {responses_init} initiated, {responses_rec} received"
            )
            lines.append(f"  • Dominance Score: {dominance:.3f}")
            lines.append("")
    return lines


def _render_emotion_section(module_data: dict, eligible) -> list[str]:
    if "emotion" not in module_data or not module_data["emotion"]:
        return ["😄 EMOTION ANALYSIS\n  • No data available for this section.\n"]
    lines = ["😄 EMOTION ANALYSIS", "-" * 18]
    if "speaker_emotions" in module_data["emotion"]:
        for speaker, emotions in module_data["emotion"]["speaker_emotions"].items():
            if not eligible(speaker):
                continue
            lines.append(f"{speaker}:")
            for emotion, score in sorted(
                emotions.items(), key=lambda x: x[1], reverse=True
            )[:5]:
                lines.append(f"  • {emotion}: {score:.3f}")
            lines.append("")
    return lines


def _render_ner_section(module_data: dict, eligible) -> list[str]:
    if "ner" not in module_data or not module_data["ner"]:
        return ["🏷️ NAMED ENTITIES\n  • No data available for this section.\n"]
    lines = ["🏷️ NAMED ENTITIES", "-" * 16]
    for speaker, entities in module_data["ner"].items():
        if not eligible(speaker):
            continue
        lines.append(f"{speaker}:")
        for entity, count in sorted(entities.items(), key=lambda x: x[1], reverse=True)[
            :5
        ]:
            lines.append(f"  • {entity}: {count}")
        lines.append("")
    return lines


def _render_entity_sentiment_section(module_data: dict, eligible) -> list[str]:
    if "entity_sentiment" not in module_data or not module_data["entity_sentiment"]:
        return [
            "🎯 ENTITY SENTIMENT ANALYSIS\n  • No data available for this section.\n"
        ]
    lines = ["🎯 ENTITY SENTIMENT ANALYSIS", "-" * 26]
    for speaker, entities in module_data["entity_sentiment"].items():
        if not eligible(speaker):
            continue
        lines.append(f"{speaker}:")
        for entity, sentiment in sorted(
            entities.items(), key=lambda x: x[1].get("sentiment_score", 0), reverse=True
        )[:5]:
            sentiment_score = sentiment.get("sentiment_score", 0)
            lines.append(f"  • {entity}: {sentiment_score:.3f}")
        lines.append("")
    return lines


def _render_conversation_loops_section(module_data: dict) -> list[str]:
    if "conversation_loops" not in module_data or not module_data["conversation_loops"]:
        return ["🔄 CONVERSATION LOOPS\n  • No data available for this section.\n"]
    lines = ["🔄 CONVERSATION LOOPS", "-" * 20]
    if "loops" in module_data["conversation_loops"]:
        loops = module_data["conversation_loops"]["loops"]
        lines.append(f"Total loops detected: {len(loops)}")
        for i, loop in enumerate(loops[:5], 1):
            speakers = loop.get("speakers", [])
            topic = loop.get("topic", "Unknown topic")
            lines.append(f"  {i}. {', '.join(speakers)} - {topic}")
        lines.append("")
    return lines


def _render_contagion_section(module_data: dict) -> list[str]:
    if "contagion" not in module_data or not module_data["contagion"]:
        return ["😊 EMOTIONAL CONTAGION\n  • No data available for this section.\n"]
    lines = ["😊 EMOTIONAL CONTAGION", "-" * 21]
    if "contagion_events" in module_data["contagion"]:
        events = module_data["contagion"]["contagion_events"]
        lines.append(f"Contagion events detected: {len(events)}")
        for i, event in enumerate(events[:5], 1):
            source = event.get("source_speaker", "Unknown")
            target = event.get("target_speaker", "Unknown")
            emotion = event.get("emotion", "Unknown")
            strength = event.get("strength", 0)
            lines.append(
                f"  {i}. {source} → {target} ({emotion}, strength: {strength:.3f})"
            )
        lines.append("")
    return lines


def _render_key_insights_section(
    speaker_stats, sentiment_summary, module_data, eligible
):
    lines = ["💡 KEY INSIGHTS", "-" * 13]
    if speaker_stats:
        most_talkative = max(speaker_stats, key=lambda x: x[2])
        lines.append(
            f"• Most talkative speaker: {most_talkative[1]} ({most_talkative[2]} words)"
        )
    if sentiment_summary:
        filtered = [(k, v) for k, v in sentiment_summary.items() if eligible(k)]
        if filtered:
            most_positive = max(filtered, key=lambda x: x[1].get("compound", 0))
            most_negative = min(filtered, key=lambda x: x[1].get("compound", 0))
            lines.append(
                f"• Most positive speaker: {most_positive[0]} (compound: {most_positive[1].get('compound', 0):.3f})"
            )
            lines.append(
                f"• Most negative speaker: {most_negative[0]} (compound: {most_negative[1].get('compound', 0):.3f})"
            )
    if "interactions" in module_data and module_data["interactions"]:
        if "speaker_summary" in module_data["interactions"]:
            speaker_summaries = module_data["interactions"]["speaker_summary"]
            if speaker_summaries:
                most_dominant = max(
                    speaker_summaries, key=lambda x: x.get("dominance_score", 0)
                )
                lines.append(
                    f"• Most dominant speaker: {most_dominant.get('speaker', 'Unknown')} (score: {most_dominant.get('dominance_score', 0):.3f})"
                )
    if "emotion" in module_data and module_data["emotion"]:
        if "speaker_emotions" in module_data["emotion"]:
            emotion_scores = {}
            for speaker, emotions in module_data["emotion"]["speaker_emotions"].items():
                if not eligible(speaker):
                    continue
                emotion_scores[speaker] = sum(emotions.values())
            if emotion_scores:
                most_emotional = max(emotion_scores.items(), key=lambda x: x[1])
                lines.append(
                    f"• Most emotional speaker: {most_emotional[0]} (total emotion score: {most_emotional[1]:.3f})"
                )
    lines.extend(
        [
            "",
            "📁 Detailed outputs available in module-specific directories:",
            "  • acts/ - Dialogue act analysis",
            "  • interactions/ - Speaker interaction patterns",
            "  • emotion/ - Emotion detection",
            "  • sentiment/ - Sentiment analysis",
            "  • data/cache/ - Location cache and data storage",
            "  • entity_sentiment/ - Entity sentiment framing analysis",
            "  • conversation_loops/ - Conversation loop detection",
            "  • contagion/ - Emotional contagion analysis",
            "  • wordclouds/ - Word frequency analysis",
            "  • tics/ - Verbal tics and filler words",
        ]
    )
    return lines


def _build_summary_section_specs(
    speaker_stats: list, sentiment_summary: dict, module_data: dict, eligible
) -> tuple[SummarySectionSpec, ...]:
    return (
        SummarySectionSpec(
            renderer=lambda: _render_basic_statistics_section(speaker_stats)
        ),
        SummarySectionSpec(
            renderer=lambda: _render_sentiment_section(sentiment_summary, eligible)
        ),
        SummarySectionSpec(
            renderer=lambda: _render_dialogue_acts_section(module_data, eligible)
        ),
        SummarySectionSpec(
            renderer=lambda: _render_interactions_section(module_data, eligible)
        ),
        SummarySectionSpec(
            renderer=lambda: _render_emotion_section(module_data, eligible)
        ),
        SummarySectionSpec(renderer=lambda: _render_ner_section(module_data, eligible)),
        SummarySectionSpec(
            renderer=lambda: _render_entity_sentiment_section(module_data, eligible)
        ),
        SummarySectionSpec(
            renderer=lambda: _render_conversation_loops_section(module_data)
        ),
        SummarySectionSpec(renderer=lambda: _render_contagion_section(module_data)),
        SummarySectionSpec(
            renderer=lambda: _render_key_insights_section(
                speaker_stats, sentiment_summary, module_data, eligible
            )
        ),
    )


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
    eligible = _make_speaker_eligibility(ignored_ids, speaker_key_aliases)
    summary_lines = [
        f"📊 COMPREHENSIVE ANALYSIS SUMMARY: {base_name}",
        "=" * 60,
        "",
    ]
    section_specs = _build_summary_section_specs(
        speaker_stats, sentiment_summary, module_data, eligible
    )
    for section in section_specs:
        summary_lines.extend(section.renderer())

    return "\n".join(summary_lines)


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
    warnings.warn(
        "generate_enhanced_html_summary() is deprecated and retained for temporary "
        "manual/export compatibility only. Prefer report.json/report.md/report.txt.",
        DeprecationWarning,
        stacklevel=2,
    )
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
            module = classify_html_module(html_name)

            if module not in module_html_files:
                module_html_files[module] = []
            module_html_files[module].append(html_file_path)

        # Group images by module with improved logic
        module_images = {}
        for img in chart_imgs:
            img_name = os.path.basename(img).lower()
            module = classify_image_module(img_name)
            if module not in module_images:
                module_images[module] = []
            module_images[module].append(img)

        # Generate the enhanced HTML content
        html_content = create_enhanced_html_content(
            base_name, now, module_images, module_html_files, module_data, speaker_map
        )

        # Write HTML file
        write_text(html_file, html_content)
        logger.info("Enhanced HTML summary saved: %s", html_file)

    except Exception as e:
        logger.warning("Could not export enhanced HTML summary: %s", e)


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
    modules_info = LEGACY_HTML_MODULES_INFO

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
                        f"<p><strong>{chart_type.replace('_', ' ').title()}:</strong> {explanation}</p>"
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
