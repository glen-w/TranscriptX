"""Legacy HTML compatibility helpers for stats summary.

This module supports the deprecated/manual HTML export path only.
Primary report outputs are report.json, report.md, and report.txt.
"""

LEGACY_HTML_MODULES_INFO = {
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


def classify_html_module(html_name: str) -> str:
    if "location" in html_name or "map" in html_name:
        return "ner"
    if "contagion" in html_name or "emotional" in html_name:
        return "contagion"
    return "other"


def classify_image_module(img_name: str) -> str:
    if "sentiment" in img_name:
        return "sentiment"
    if "emotion" in img_name and not ("map" in img_name or "contagion" in img_name):
        return "emotion"
    if "acts" in img_name:
        return "acts"
    if "interaction" in img_name:
        return "interactions"
    if "ner" in img_name or "location" in img_name:
        return "ner"
    if "entity" in img_name:
        return "entity-sentiment"
    if "loop" in img_name or "pattern" in img_name:
        return "conversation-loops"
    if (
        "contagion" in img_name
        or "emotional_map" in img_name
        or ("map" in img_name and "emotion" in img_name)
    ):
        return "contagion"
    if "temporal" in img_name or "stats" in img_name or "summary" in img_name:
        return "stats"
    if "radar" in img_name:
        return "emotion-radars"
    if "dominance" in img_name:
        return "meeting-dominance"
    if "heatmap" in img_name:
        return "interaction-heatmaps"
    if "topic" in img_name:
        return "topic-modeling"
    if "semantic" in img_name or "similarity" in img_name:
        return "semantic-similarity"
    if "wordcloud" in img_name or "word_cloud" in img_name:
        return "wordclouds"
    if "readability" in img_name or "understandability" in img_name:
        return "readability"
    if "tics" in img_name:
        return "tics"
    return "other"
