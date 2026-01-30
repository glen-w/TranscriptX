"""Analysis configuration editor."""

from typing import Any, Optional

import questionary

from transcriptx.cli.settings import (  # type: ignore[import-untyped]
    SettingItem,
    create_bool_editor,
    create_choice_editor,
    create_float_editor,
    create_int_editor,
    create_list_editor,
    create_str_editor,
    settings_menu_loop,
)
from ._dirty_tracker import is_dirty, mark_dirty

# Known emotion model IDs for choice list; arbitrary IDs still load from config
EMOTION_MODEL_CHOICES = [
    "bhadresh-savani/distilbert-base-uncased-emotion",
    "SamLowe/roberta-base-go_emotions",
    "j-hartmann/emotion-english-distilroberta-base",
]

CUSTOM_EMOTION_MODEL_LABEL = "Custom…"

# Known sentiment model IDs for choice list; arbitrary IDs still load from config
SENTIMENT_MODEL_CHOICES = [
    "cardiffnlp/twitter-roberta-base-sentiment-latest",
    "cardiffnlp/twitter-xlm-roberta-base-sentiment",
    "nlptown/bert-base-multilingual-uncased-sentiment",
    "ProsusAI/finbert",
]

CUSTOM_SENTIMENT_MODEL_LABEL = "Custom…"


def _sentiment_model_editor(item: SettingItem) -> Optional[Any]:
    """Let user pick a known sentiment model or enter custom HF model id."""
    current_value = item.getter() or ""
    choices = list(SENTIMENT_MODEL_CHOICES) + [CUSTOM_SENTIMENT_MODEL_LABEL]
    default = (
        current_value
        if current_value in SENTIMENT_MODEL_CHOICES
        else CUSTOM_SENTIMENT_MODEL_LABEL
    )
    selection_choices = [questionary.Choice(title=c, value=c) for c in choices]
    try:
        selected = questionary.select(
            "Select sentiment model",
            choices=selection_choices,
            default=default,
        ).ask()
    except KeyboardInterrupt:
        return None
    if selected is None:
        return None
    if selected == CUSTOM_SENTIMENT_MODEL_LABEL:
        custom = questionary.text(
            "Enter Hugging Face model id",
            default=current_value if current_value not in SENTIMENT_MODEL_CHOICES else "",
        ).ask()
        if custom is None:
            return None
        return custom.strip() or current_value
    return selected


def _emotion_model_editor(item: SettingItem) -> Optional[Any]:
    """Let user pick a known emotion model or enter custom HF model id."""
    current_value = item.getter() or ""
    choices = list(EMOTION_MODEL_CHOICES) + [CUSTOM_EMOTION_MODEL_LABEL]
    default = (
        current_value
        if current_value in EMOTION_MODEL_CHOICES
        else CUSTOM_EMOTION_MODEL_LABEL
    )
    selection_choices = [questionary.Choice(title=c, value=c) for c in choices]
    try:
        selected = questionary.select(
            "Select emotion model",
            choices=selection_choices,
            default=default,
        ).ask()
    except KeyboardInterrupt:
        return None
    if selected is None:
        return None
    if selected == CUSTOM_EMOTION_MODEL_LABEL:
        custom = questionary.text(
            "Enter Hugging Face model id",
            default=current_value if current_value not in EMOTION_MODEL_CHOICES else "",
        ).ask()
        if custom is None:
            return None
        return custom.strip() or current_value
    return selected


from .quality_filtering import edit_quality_filtering_config
from .voice import edit_voice_config
from .highlights import edit_highlights_config
from .summary import edit_summary_config


def edit_analysis_config(config: Any) -> None:
    """Edit analysis configuration."""
    items = [
        SettingItem(
            order=1,
            key="analysis.sentiment_window_size",
            label="Sentiment window size",
            getter=lambda: config.analysis.sentiment_window_size,
            setter=lambda value: setattr(config.analysis, "sentiment_window_size", value),
            editor=create_int_editor(min_val=1, hint="Positive integer window size."),
        ),
        SettingItem(
            order=2,
            key="analysis.sentiment_min_confidence",
            label="Sentiment min confidence",
            getter=lambda: config.analysis.sentiment_min_confidence,
            setter=lambda value: setattr(
                config.analysis, "sentiment_min_confidence", value
            ),
            editor=create_float_editor(
                min_val=0.0, max_val=1.0, hint="Range: 0.0 to 1.0"
            ),
        ),
        SettingItem(
            order=3,
            key="analysis.sentiment_backend",
            label="Sentiment backend",
            getter=lambda: getattr(config.analysis, "sentiment_backend", "vader"),
            setter=lambda value: setattr(config.analysis, "sentiment_backend", value),
            editor=create_choice_editor(
                ["vader", "transformers"],
                hint="vader = NLTK VADER; transformers = Hugging Face model.",
            ),
        ),
        SettingItem(
            order=4,
            key="analysis.sentiment_model_name",
            label="Sentiment model",
            getter=lambda: getattr(
                config.analysis,
                "sentiment_model_name",
                "cardiffnlp/twitter-roberta-base-sentiment-latest",
            ),
            setter=lambda value: setattr(
                config.analysis, "sentiment_model_name", value
            ),
            editor=_sentiment_model_editor,
        ),
        SettingItem(
            order=5,
            key="analysis.emotion_min_confidence",
            label="Emotion min confidence",
            getter=lambda: config.analysis.emotion_min_confidence,
            setter=lambda value: setattr(config.analysis, "emotion_min_confidence", value),
            editor=create_float_editor(
                min_val=0.0, max_val=1.0, hint="Range: 0.0 to 1.0"
            ),
        ),
        SettingItem(
            order=6,
            key="analysis.emotion_model_name",
            label="Emotion model",
            getter=lambda: config.analysis.emotion_model_name,
            setter=lambda value: setattr(config.analysis, "emotion_model_name", value),
            editor=_emotion_model_editor,
        ),
        SettingItem(
            order=7,
            key="analysis.emotion_output_mode",
            label="Emotion output mode",
            getter=lambda: getattr(config.analysis, "emotion_output_mode", "top1"),
            setter=lambda value: setattr(
                config.analysis, "emotion_output_mode", value
            ),
            editor=create_choice_editor(
                ["top1", "multilabel"],
                hint="top1 = single label; multilabel = all above threshold.",
            ),
        ),
        SettingItem(
            order=8,
            key="analysis.emotion_score_threshold",
            label="Emotion score threshold",
            getter=lambda: getattr(config.analysis, "emotion_score_threshold", 0.30),
            setter=lambda value: setattr(
                config.analysis, "emotion_score_threshold", value
            ),
            editor=create_float_editor(
                min_val=0.0, max_val=1.0, hint="For multilabel: keep labels above this."
            ),
        ),
        SettingItem(
            order=9,
            key="analysis.ner_labels",
            label="NER labels",
            getter=lambda: config.analysis.ner_labels,
            setter=lambda value: setattr(config.analysis, "ner_labels", value),
            editor=create_list_editor(
                hint=(
                    "Available: PERSON, ORG, GPE, LOC, DATE, TIME, MONEY, FAC, "
                    "PRODUCT, EVENT, WORK_OF_ART, LAW, LANGUAGE"
                )
            ),
        ),
        SettingItem(
            order=10,
            key="analysis.ner_min_confidence",
            label="NER min confidence",
            getter=lambda: config.analysis.ner_min_confidence,
            setter=lambda value: setattr(config.analysis, "ner_min_confidence", value),
            editor=create_float_editor(
                min_val=0.0, max_val=1.0, hint="Range: 0.0 to 1.0"
            ),
        ),
        SettingItem(
            order=11,
            key="analysis.ner_include_geocoding",
            label="NER geocoding",
            getter=lambda: config.analysis.ner_include_geocoding,
            setter=lambda value: setattr(config.analysis, "ner_include_geocoding", value),
            editor=create_bool_editor(hint="Include geocoding for location entities."),
        ),
        SettingItem(
            order=12,
            key="analysis.wordcloud_max_words",
            label="Word cloud max words",
            getter=lambda: config.analysis.wordcloud_max_words,
            setter=lambda value: setattr(config.analysis, "wordcloud_max_words", value),
            editor=create_int_editor(min_val=1, hint="Positive integer."),
        ),
        SettingItem(
            order=13,
            key="analysis.wordcloud_min_font_size",
            label="Word cloud min font size",
            getter=lambda: config.analysis.wordcloud_min_font_size,
            setter=lambda value: setattr(
                config.analysis, "wordcloud_min_font_size", value
            ),
            editor=create_int_editor(min_val=1, hint="Positive integer."),
        ),
        SettingItem(
            order=14,
            key="analysis.wordcloud_stopwords",
            label="Word cloud stopwords",
            getter=lambda: config.analysis.wordcloud_stopwords,
            setter=lambda value: setattr(
                config.analysis, "wordcloud_stopwords", value
            ),
            editor=create_list_editor(hint="Comma-separated list of stopwords."),
        ),
        SettingItem(
            order=15,
            key="analysis.readability_metrics",
            label="Readability metrics",
            getter=lambda: config.analysis.readability_metrics,
            setter=lambda value: setattr(config.analysis, "readability_metrics", value),
            editor=create_list_editor(
                hint=(
                    "Examples: flesch_reading_ease, flesch_kincaid_grade, gunning_fog"
                )
            ),
        ),
        SettingItem(
            order=16,
            key="analysis.output_formats",
            label="Output formats",
            getter=lambda: config.analysis.output_formats,
            setter=lambda value: setattr(config.analysis, "output_formats", value),
            editor=create_list_editor(
                hint="Comma-separated list (e.g., json, csv, png)."
            ),
        ),
        SettingItem(
            order=17,
            key="analysis.use_emojis",
            label="Use emojis",
            getter=lambda: getattr(config, "use_emojis", True),
            setter=lambda value: setattr(config, "use_emojis", value),
            editor=create_bool_editor(hint="Enable emojis in menus and messages."),
        ),
        # Semantic / repetition limits (performance and coverage)
        SettingItem(
            order=18,
            key="analysis.max_segments_per_speaker",
            label="Max segments per speaker (repetition)",
            getter=lambda: config.analysis.max_segments_per_speaker,
            setter=lambda value: setattr(
                config.analysis, "max_segments_per_speaker", value
            ),
            editor=create_int_editor(
                min_val=1,
                hint="Max segments per speaker for within-speaker repetition detection (default 200).",
            ),
        ),
        SettingItem(
            order=19,
            key="analysis.max_segments_for_cross_speaker",
            label="Max segments for cross-speaker analysis",
            getter=lambda: config.analysis.max_segments_for_cross_speaker,
            setter=lambda value: setattr(
                config.analysis, "max_segments_for_cross_speaker", value
            ),
            editor=create_int_editor(
                min_val=1,
                hint="Max segments for cross-speaker repetition detection (default 500).",
            ),
        ),
        SettingItem(
            order=20,
            key="analysis.max_segments_for_semantic",
            label="Max segments for semantic analysis",
            getter=lambda: config.analysis.max_segments_for_semantic,
            setter=lambda value: setattr(
                config.analysis, "max_segments_for_semantic", value
            ),
            editor=create_int_editor(
                min_val=1,
                hint="Maximum segments to process for semantic similarity (default 1000).",
            ),
        ),
        SettingItem(
            order=21,
            key="analysis.use_quality_filtering",
            label="Use quality filtering for segments",
            getter=lambda: config.analysis.use_quality_filtering,
            setter=lambda value: setattr(
                config.analysis, "use_quality_filtering", value
            ),
            editor=create_bool_editor(
                hint="Filter segments by quality before limiting; if false, simple truncation.",
            ),
        ),
        SettingItem(
            order=22,
            key="analysis.semantic_similarity_threshold",
            label="Semantic similarity threshold (within-speaker)",
            getter=lambda: config.analysis.semantic_similarity_threshold,
            setter=lambda value: setattr(
                config.analysis, "semantic_similarity_threshold", value
            ),
            editor=create_float_editor(
                min_val=0.0,
                max_val=1.0,
                hint="Threshold for within-speaker repetition (default 0.7).",
            ),
        ),
        SettingItem(
            order=23,
            key="analysis.cross_speaker_similarity_threshold",
            label="Cross-speaker similarity threshold",
            getter=lambda: config.analysis.cross_speaker_similarity_threshold,
            setter=lambda value: setattr(
                config.analysis, "cross_speaker_similarity_threshold", value
            ),
            editor=create_float_editor(
                min_val=0.0,
                max_val=1.0,
                hint="Threshold for cross-speaker similarity (default 0.6).",
            ),
        ),
        SettingItem(
            order=24,
            key="analysis.ner_use_light_model",
            label="NER use light model",
            getter=lambda: config.analysis.ner_use_light_model,
            setter=lambda value: setattr(
                config.analysis, "ner_use_light_model", value
            ),
            editor=create_bool_editor(
                hint="Use lighter NER model for faster processing.",
            ),
        ),
        SettingItem(
            order=25,
            key="analysis.ner_max_segments",
            label="NER max segments",
            getter=lambda: config.analysis.ner_max_segments,
            setter=lambda value: setattr(config.analysis, "ner_max_segments", value),
            editor=create_int_editor(
                min_val=1,
                hint="Maximum segments to run NER on (default 5000).",
            ),
        ),
        SettingItem(
            order=26,
            key="analysis.interaction_min_interactions",
            label="Interaction min interactions",
            getter=lambda: config.analysis.interaction_min_interactions,
            setter=lambda value: setattr(
                config.analysis, "interaction_min_interactions", value
            ),
            editor=create_int_editor(
                min_val=1,
                hint="Minimum interactions to count (default 2).",
            ),
        ),
        SettingItem(
            order=27,
            key="analysis.interaction_time_window",
            label="Interaction time window (seconds)",
            getter=lambda: config.analysis.interaction_time_window,
            setter=lambda value: setattr(
                config.analysis, "interaction_time_window", value
            ),
            editor=create_float_editor(
                min_val=0.1,
                hint="Time window in seconds for interaction analysis (default 30.0).",
            ),
        ),
        SettingItem(
            order=28,
            key="analysis.quality_filtering_profiles",
            label="Quality filtering profiles",
            getter=lambda: "Manage",
            setter=lambda _: None,
            editor=lambda _: (edit_quality_filtering_config(config), None)[1],
        ),
        SettingItem(
            order=29,
            key="analysis.voice",
            label="Voice settings",
            getter=lambda: "Manage",
            setter=lambda _: None,
            editor=lambda _: (edit_voice_config(config), None)[1],
        ),
        SettingItem(
            order=30,
            key="analysis.highlights",
            label="Highlights settings",
            getter=lambda: "Manage",
            setter=lambda _: None,
            editor=lambda _: (edit_highlights_config(config), None)[1],
        ),
        SettingItem(
            order=31,
            key="analysis.summary",
            label="Summary settings",
            getter=lambda: "Manage",
            setter=lambda _: None,
            editor=lambda _: (edit_summary_config(config), None)[1],
        ),
    ]

    settings_menu_loop(
        title="📊 Analysis Settings",
        items=items,
        on_back=lambda: None,
        dirty_tracker=is_dirty,
        mark_dirty=mark_dirty,
    )
