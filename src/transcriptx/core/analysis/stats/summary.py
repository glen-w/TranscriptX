"""Stats summary surface.

Primary report outputs are report.json, report.md, and report.txt.
"""

from typing import Callable, NamedTuple

from transcriptx.utils.text_utils import format_time, is_eligible_named_speaker


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
