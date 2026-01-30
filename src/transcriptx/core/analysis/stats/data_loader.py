"""Stats analysis module."""

import json
import os


from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def load_module_data(transcript_dir: str, base_name: str) -> dict:
    """
    Load data from all analysis modules to create comprehensive summary.

    This function attempts to load JSON data files from each analysis module's
    output directory. If a module's data is missing or corrupted, it gracefully
    handles the error and continues with available data.

    Args:
        transcript_dir: Directory containing analysis outputs
        base_name: Base name of the transcript (used for file naming)

    Returns:
        Dictionary containing data from all available modules, with empty dicts
        for missing modules
    """
    module_data = {}

    # Load dialogue acts data
    module_data["acts"] = _load_first_json(
        [
            os.path.join(
                transcript_dir, "acts", "data", "global", f"{base_name}_acts_summary.json"
            ),
            os.path.join(
                transcript_dir, "acts", "data", f"{base_name}_acts_summary.json"
            ),
        ]
    )

    # Load speaker interactions data
    module_data["interactions"] = _load_first_json(
        [
            os.path.join(
                transcript_dir,
                "interactions",
                "data",
                "global",
                f"{base_name}_speaker_summary.json",
            )
        ]
    )

    # Load emotion analysis data
    module_data["emotion"] = _load_first_json(
        [
            os.path.join(
                transcript_dir,
                "emotion",
                "data",
                "global",
                f"{base_name}_emotion_summary.json",
            )
        ]
    )

    # Load sentiment analysis data
    module_data["sentiment"] = _load_first_json(
        [
            os.path.join(
                transcript_dir,
                "sentiment",
                "data",
                "global",
                f"{base_name}_sentiment_summary.json",
            )
        ]
    )

    # Load NER data
    module_data["ner"] = _load_first_json(
        [os.path.join(transcript_dir, "ner", f"{base_name}_ner-entities.json")]
    )

    # Load word clouds data
    module_data["wordclouds"] = _load_first_json(
        [
            os.path.join(
                transcript_dir,
                "wordclouds",
                "data",
                "global",
                f"{base_name}_wordcloud_summary.json",
            )
        ]
    )

    # Load entity sentiment data
    module_data["entity_sentiment"] = _load_first_json(
        [
            os.path.join(
                transcript_dir,
                "entity_sentiment",
                "data",
                "global",
                f"{base_name}_summary.json",
            ),
            os.path.join(
                transcript_dir,
                "entity_sentiment",
                "data",
                f"{base_name}_entity_sentiment_summary.json",
            ),
        ]
    )

    # Load conversation loops data
    module_data["conversation_loops"] = _load_first_json(
        [
            os.path.join(
                transcript_dir,
                "conversation_loops",
                "data",
                f"{base_name}_conversation_loops_summary.json",
            )
        ]
    )

    # Load contagion data
    module_data["contagion"] = _load_first_json(
        [
            os.path.join(
                transcript_dir, "contagion", "data", f"{base_name}_contagion_summary.json"
            )
        ]
    )

    module_data["understandability"] = _load_first_json(
        [
            os.path.join(
                transcript_dir,
                "understandability",
                "data",
                "global",
                f"{base_name}_understandability.json",
            )
        ]
    )

    return module_data


def _load_first_json(paths: list[str]) -> dict:
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path) as handle:
                    data = json.load(handle)
                return data if isinstance(data, dict) else {}
            except (OSError, json.JSONDecodeError):
                return {}
    return {}
