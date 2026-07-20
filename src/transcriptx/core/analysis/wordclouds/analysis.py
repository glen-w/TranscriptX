# transcriptx/core/wordclouds.py

"""
Word Cloud Generation Module for TranscriptX.

This module provides comprehensive word cloud generation capabilities for transcript analysis,
including speaker-specific word clouds, topic-based clouds, and sentiment-weighted visualizations.

Implementation is split across ``output_bridge``, ``terms_io``, ``plotting``, ``frequencies``,
and ``group_run``; this module remains the compatibility facade and orchestration entry point.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

import transcriptx.core.analysis.wordclouds.output_bridge as _wc_output_bridge
from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.output.output_service import create_output_service
from transcriptx.core.utils.lazy_imports import lazy_pyplot
from transcriptx.core.utils.nlp_utils import (
    ALL_STOPWORDS,
    nlp,
    tokenize_and_filter,
    load_tics,
)
from transcriptx.core.utils.config import get_config  # noqa: F401
from transcriptx.core.utils.notifications import notify_user
from transcriptx.core.utils.output_standards import create_standard_output_structure
from transcriptx.core.utils.speaker_extraction import (
    get_speaker_display_name,
    group_segments_by_speaker,
)
from transcriptx.io import load_segments
from transcriptx.utils.text_utils import is_eligible_named_speaker

from transcriptx.core.analysis.wordclouds.frequencies import (
    generate_bigram_tfidf_wordclouds,
    generate_bigram_wordclouds,
    generate_pos_wordclouds,
    generate_tfidf_wordclouds,
    generate_tic_wordclouds,
    save_freq_json_csv,
)
from transcriptx.core.analysis.wordclouds.group_run import (  # noqa: F401
    _emit_pooled_global_tfidf_wordcloud,
    run_group_wordclouds,
)
from transcriptx.core.analysis.wordclouds.output_bridge import (
    _get_ignored_ids,
    _relative_to_transcript,
    _should_generate_views,  # noqa: F401
    save_global_chart,
)
from transcriptx.core.analysis.wordclouds.plotting import (
    _get_wordcloud_class,
    _save_wordcloud_view,
    _wordcloud_figure,
    generate_wordcloud,
)
from transcriptx.core.analysis.wordclouds.terms_io import (
    _build_terms_payload,
    _build_wordcloud_explorer_html,  # noqa: F401
    _save_terms_json,
)

plt = lazy_pyplot()


def __getattr__(name: str) -> Any:
    if name == "_ACTIVE_OUTPUT_SERVICE":
        return _wc_output_bridge._ACTIVE_OUTPUT_SERVICE
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class WordcloudsAnalysis(AnalysisModule):
    """
    Word cloud generation analysis module.

    This module generates various types of word clouds for transcript analysis,
    including basic, bigram, TF-IDF, tic-based, and POS-tagged word clouds.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the wordclouds analysis module."""
        super().__init__(config)
        self.module_name = "wordclouds"
        self._eligibility_result: Dict[str, Any] | None = None

    def run_from_context(self, context):
        self._eligibility_result = (
            context.get_analysis_result("insight_eligibility") or {}
        )
        try:
            return super().run_from_context(context)
        finally:
            self._eligibility_result = None

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        tic_list: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform wordcloud analysis on transcript segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            tic_list: Optional list of tics to filter (from tics module)

        Returns:
            Dictionary containing wordcloud analysis results
        """
        grouped: Dict[str, List[str]]
        eligibility = self._eligibility_result or {}
        filtered_segments = (
            eligibility.get("filtered_segments")
            if isinstance(eligibility, dict)
            else None
        )
        if isinstance(filtered_segments, list) and filtered_segments:
            grouped = defaultdict(list)
            for seg in filtered_segments:
                if not isinstance(seg, dict):
                    continue
                speaker = str(seg.get("speaker") or "").strip()
                content_text = str(seg.get("content_text") or "").strip()
                if speaker and content_text:
                    grouped[speaker].append(content_text)
            grouped = dict(grouped)
            if tic_list is None:
                tic_list = list(eligibility.get("tic_mask") or [])
        else:
            # Fallback path when eligibility artifacts are unavailable.
            grouped = group_texts_by_speaker(segments)

        # Extract tics if not provided
        if tic_list is None:
            from transcriptx.core.analysis.tics import extract_tics_and_top_words
            from transcriptx.core.utils.nlp_utils import build_tic_mask

            per_speaker_tics, _ = extract_tics_and_top_words(grouped)
            detected: set[str] = set()
            for counts in (per_speaker_tics or {}).values():
                if isinstance(counts, dict):
                    detected.update(str(term).lower() for term in counts.keys())
                elif isinstance(counts, (list, set, tuple)):
                    detected.update(str(term).lower() for term in counts)
            tic_list = sorted(build_tic_mask(detected))

        return {
            "grouped_texts": dict(grouped),
            "tic_list": tic_list,
            "eligibility_fallback": not (
                isinstance(filtered_segments, list) and len(filtered_segments) > 0
            ),
        }

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save results using OutputService (new interface).

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        tic_list = results.get("tic_list", [])
        output_structure = output_service.get_output_structure()

        # Use existing run_all_wordclouds function which handles all wordcloud types
        # This is a bridge approach - full refactoring would extract each wordcloud type
        # For now, we'll delegate to the existing function
        transcript_path = output_service.transcript_path
        run_all_wordclouds(
            transcript_path,
            tic_list,
            transcript_dir=output_structure.transcript_dir,
            grouped_texts=results.get("grouped_texts"),
        )


def group_texts_by_speaker(segments: list) -> dict:
    """
    Group text segments by speaker using segment-based identification.

    Uses stable per-speaker ids from segments when available to distinguish speakers with the same name.

    Args:
        segments: List of transcript segments

    Returns:
        Dictionary mapping speaker display name to list of text strings
    """
    # Group segments by speaker using segment fields
    grouped_segments = group_segments_by_speaker(segments)

    # Extract texts grouped by display name
    grouped = defaultdict(list)
    fallback_grouped = defaultdict(list)
    ignored_ids = _get_ignored_ids()
    for grouping_key, segs in grouped_segments.items():
        display_name = get_speaker_display_name(grouping_key, segs, segments)
        if display_name:
            if ignored_ids and (
                str(grouping_key) in ignored_ids or str(display_name) in ignored_ids
            ):
                continue
            texts = [seg.get("text", "") for seg in segs if seg.get("text")]
            if texts:
                fallback_grouped[display_name].extend(texts)
            if not is_eligible_named_speaker(
                display_name, str(grouping_key), ignored_ids
            ):
                continue
            if texts:
                grouped[display_name].extend(texts)

    if not grouped and not fallback_grouped:
        for seg in segments:
            display_name = str(seg.get("speaker") or "").strip()
            if not display_name:
                continue
            if ignored_ids and (
                display_name in ignored_ids
                or str(seg.get("speaker_db_id")) in ignored_ids
            ):
                continue
            text = seg.get("text", "")
            if text:
                fallback_grouped[display_name].append(text)

    if not grouped and fallback_grouped:
        return fallback_grouped

    return grouped


def run_all_wordclouds(
    transcript_path: str,
    tic_list: list[str],
    transcript_dir: str | None = None,
    grouped_texts: Dict[str, List[str]] | None = None,
) -> None:
    from transcriptx.core.utils._path_core import get_base_name, get_transcript_dir
    from transcriptx.core.utils.logger import get_logger

    logger = get_logger()

    base_name = get_base_name(transcript_path)
    # Use provided transcript_dir if available, otherwise use standardized path
    if transcript_dir is None:
        transcript_dir = get_transcript_dir(transcript_path)

    # Use output standards for directory structure
    output_structure = create_standard_output_structure(transcript_dir, "wordclouds")
    _wc_output_bridge._ACTIVE_OUTPUT_SERVICE = create_output_service(
        transcript_path,
        "wordclouds",
        output_dir=transcript_dir,
        run_id=Path(transcript_dir).name,
    )

    if grouped_texts is not None:
        grouped = dict(grouped_texts)
        logger.info(
            f"[WORDCLOUDS] Using precomputed speaker grouping from pipeline: "
            f"{len(grouped)} speakers: {list(grouped.keys())}"
        )
    else:
        try:
            segments = load_segments(str(transcript_path))
            logger.info(
                f"[WORDCLOUDS] Loaded {len(segments)} segments from {transcript_path}"
            )
        except Exception as e:
            logger.error(f"[WORDCLOUDS] Failed to load segments: {e}")
            notify_user(
                f"⚠️ Failed to load transcript segments for wordclouds: {e}",
                technical=True,
                section="wordclouds",
            )
            return

        grouped = group_texts_by_speaker(segments)
        logger.info(
            f"[WORDCLOUDS] Grouped text into {len(grouped)} speakers: {list(grouped.keys())}"
        )

    if not grouped:
        logger.warning(
            "[WORDCLOUDS] No speakers found after grouping. No wordclouds will be generated."
        )
        notify_user(
            "⚠️ No speakers found for wordcloud generation. Check speaker mapping.",
            technical=True,
            section="wordclouds",
        )
        return

    # Basic
    try:
        for speaker, texts in grouped.items():
            joined = " ".join(texts)
            if not joined.strip():
                logger.warning(
                    f"[WORDCLOUDS] Skipping empty text for speaker {speaker}"
                )
                continue
            freq = generate_wordcloud(
                joined,
                output_structure,
                base_name,
                speaker,
                "wordcloud",
                chart_type="basic",
                title=f"{speaker}",
            )
            if freq:
                save_freq_json_csv(
                    freq, output_structure, f"{base_name}-basic", speaker
                )
    except Exception as e:
        logger.error(
            f"[WORDCLOUDS] Error generating basic wordclouds: {e}", exc_info=True
        )
        notify_user(
            f"⚠️ Error generating basic wordclouds: {e}",
            technical=True,
            section="wordclouds",
        )

    # Global basic
    try:
        all_text = " ".join(" ".join(texts) for texts in grouped.values())
        if all_text.strip():
            global_freq = generate_wordcloud(
                all_text,
                output_structure,
                base_name,
                "wordcloud-ALL",
                "wordcloud",
                chart_type="basic",
                title="All Speakers",
            )
            if global_freq:
                save_freq_json_csv(
                    global_freq, output_structure, f"{base_name}-basic", "ALL"
                )
        else:
            logger.warning("[WORDCLOUDS] No text content for global wordcloud")
    except Exception as e:
        logger.error(
            f"[WORDCLOUDS] Error generating global basic wordcloud: {e}", exc_info=True
        )
        notify_user(
            f"⚠️ Error generating global basic wordcloud: {e}",
            technical=True,
            section="wordclouds",
        )

    # TF-IDF
    try:
        generate_tfidf_wordclouds(grouped, output_structure, base_name)
    except Exception as e:
        logger.error(
            f"[WORDCLOUDS] Error generating TF-IDF wordclouds: {e}", exc_info=True
        )

    # Basic bigrams
    try:
        generate_bigram_wordclouds(grouped, output_structure, base_name)
    except Exception as e:
        logger.error(
            f"[WORDCLOUDS] Error generating bigram wordclouds: {e}", exc_info=True
        )

    # Global bigrams
    try:
        all_words = []
        for texts in grouped.values():
            all_words.extend(tokenize_and_filter(" ".join(texts)))

        if len(all_words) < 2:
            logger.warning("[WORDCLOUDS] Not enough words for bigram generation")
        else:
            bigrams = [
                f"{all_words[i]} {all_words[i + 1]}" for i in range(len(all_words) - 1)
            ]
            global_freq = Counter(bigrams)

            if global_freq:
                wc = _get_wordcloud_class()(
                    width=800, height=400, background_color="white"
                ).generate_from_frequencies(global_freq)
                fig, ax = _wordcloud_figure(wc)
                chart_path = None
                try:
                    ax.set_title("All Speakers – Bigrams Only")
                    fig.tight_layout()
                    chart_path = save_global_chart(
                        fig,
                        output_structure,
                        base_name,
                        "wordcloud-bigrams-ALL",
                        dpi=300,
                        chart_type="bigrams",
                        frequencies=global_freq,
                    )
                finally:
                    plt.close(fig)
                save_freq_json_csv(
                    global_freq, output_structure, f"{base_name}-bigrams", "ALL"
                )

                payload = _build_terms_payload(
                    dict(global_freq),
                    variant="bigrams",
                    variant_key="bigrams_count",
                    speaker=None,
                    ngram=2,
                    metric="count",
                )
                terms_path = _save_terms_json(
                    payload, filename="wordcloud-bigrams-ALL", speaker=None
                )
                _save_wordcloud_view(
                    payload,
                    title="All Speakers – Bigrams Only",
                    filename="wordcloud-bigrams-ALL",
                    speaker=None,
                    source_terms_path=(
                        _relative_to_transcript(terms_path) if terms_path else None
                    ),
                    thumbnail_path=(
                        _relative_to_transcript(chart_path) if chart_path else None
                    ),
                )
    except Exception as e:
        logger.error(
            f"[WORDCLOUDS] Error generating global bigram wordcloud: {e}", exc_info=True
        )

    # TF-IDF bigrams
    try:
        generate_bigram_tfidf_wordclouds(grouped, output_structure, base_name)
    except Exception as e:
        logger.error(
            f"[WORDCLOUDS] Error generating TF-IDF bigram wordclouds: {e}",
            exc_info=True,
        )

    # Verbal tics
    try:
        generate_tic_wordclouds(grouped, output_structure, base_name)
    except Exception as e:
        logger.error(
            f"[WORDCLOUDS] Error generating tic wordclouds: {e}", exc_info=True
        )

    # === Per-speaker POS word clouds ===
    for pos_filter, allowed_tags in {
        "noun": {"NOUN", "PROPN"},
        "verb": {"VERB"},
        "adj": {"ADJ"},
    }.items():
        try:
            generate_pos_wordclouds(grouped, output_structure, base_name, pos_filter)
        except Exception as e:
            logger.error(
                f"[WORDCLOUDS] Error generating {pos_filter} POS wordclouds: {e}",
                exc_info=True,
            )

    # === Global POS word clouds ===
    for pos_filter, allowed_tags in {
        "noun": {"NOUN", "PROPN"},
        "verb": {"VERB"},
        "adj": {"ADJ"},
    }.items():
        try:
            all_text = " ".join(" ".join(texts) for texts in grouped.values())
            doc = nlp(all_text.lower())
            tokens = [
                token.text
                for token in doc
                if token.pos_ in allowed_tags and token.text not in ALL_STOPWORDS
            ]
            global_freq = Counter(tokens)

            if global_freq:
                wc = _get_wordcloud_class()(
                    width=800, height=400, background_color="white"
                ).generate_from_frequencies(global_freq)
                fig, ax = _wordcloud_figure(wc)
                chart_path = None
                try:
                    ax.set_title(f"All Speakers – {pos_filter.title()}s")
                    fig.tight_layout()
                    chart_path = save_global_chart(
                        fig,
                        output_structure,
                        base_name,
                        f"wordcloud-{pos_filter}-ALL",
                        dpi=300,
                        chart_type=f"pos_{pos_filter}",
                        frequencies=global_freq,
                    )
                finally:
                    plt.close(fig)
                save_freq_json_csv(
                    global_freq, output_structure, f"{base_name}-{pos_filter}", "ALL"
                )

                payload = _build_terms_payload(
                    dict(global_freq),
                    variant=f"pos_{pos_filter}",
                    variant_key=f"pos_{pos_filter}_unigram",
                    speaker=None,
                    ngram=1,
                    metric="count",
                )
                terms_path = _save_terms_json(
                    payload, filename=f"wordcloud-{pos_filter}-ALL", speaker=None
                )
                _save_wordcloud_view(
                    payload,
                    title=f"All Speakers – {pos_filter.title()}s",
                    filename=f"wordcloud-{pos_filter}-ALL",
                    speaker=None,
                    source_terms_path=(
                        _relative_to_transcript(terms_path) if terms_path else None
                    ),
                    thumbnail_path=(
                        _relative_to_transcript(chart_path) if chart_path else None
                    ),
                )
        except Exception as e:
            logger.error(
                f"[WORDCLOUDS] Error generating global {pos_filter} POS wordcloud: {e}",
                exc_info=True,
            )

    logger.info(f"[WORDCLOUDS] Completed wordcloud generation for {base_name}")


def generate_wordclouds(
    segments: list[dict[str, Any]],
    base_name: str,
    transcript_dir: str,
) -> None:
    """
    Generate word clouds for transcript segments.

    Args:
        segments: List of transcript segments
        base_name: Base name for output files
        transcript_dir: Output directory
    """
    # Directories will be created lazily when files are saved
    # No need to create them upfront
    _wc_output_bridge._ACTIVE_OUTPUT_SERVICE = create_output_service(
        str(Path(transcript_dir) / f"{base_name}.json"),
        "wordclouds",
        output_dir=transcript_dir,
        run_id=Path(transcript_dir).name,
    )

    # Group texts by speaker using segment-based identification
    group_texts_by_speaker(segments)

    # Load tics
    tic_list = load_tics()

    # Create temporary transcript file for compatibility
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"segments": segments}, f)
        temp_path = f.name

    try:
        # Pass the correct transcript_dir to avoid recalculating from temp file path
        run_all_wordclouds(temp_path, tic_list, transcript_dir=transcript_dir)
    finally:
        os.unlink(temp_path)
