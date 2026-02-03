# transcriptx/core/wordclouds.py

"""
Word Cloud Generation Module for TranscriptX.

This module provides comprehensive word cloud generation capabilities for transcript analysis,
including speaker-specific word clouds, topic-based clouds, and sentiment-weighted visualizations.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from scipy.sparse import spmatrix

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.wordclouds.models import WordcloudTerm, WordcloudTerms
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.nlp_utils import (
    ALL_STOPWORDS,
    extract_tics_from_text,
    nlp,
    tokenize_and_filter,
)
from transcriptx.core.utils.output_standards import create_standard_output_structure
from transcriptx.core.output.output_service import create_output_service
from transcriptx.core.utils.artifact_writer import write_json, write_csv
from transcriptx.core.utils.speaker_extraction import (
    group_segments_by_speaker,
    get_speaker_display_name,
)
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.utils.notifications import notify_user
from transcriptx.io import load_segments
from transcriptx.core.utils.lazy_imports import lazy_pyplot, get_wordcloud
from transcriptx.core.viz.charts import is_plotly_available

plt = lazy_pyplot()

_ACTIVE_OUTPUT_SERVICE = None


@contextmanager
def use_output_service(service):
    global _ACTIVE_OUTPUT_SERVICE
    previous = _ACTIVE_OUTPUT_SERVICE
    _ACTIVE_OUTPUT_SERVICE = service
    try:
        yield
    finally:
        _ACTIVE_OUTPUT_SERVICE = previous


def _save_chart_global(fig, filename, dpi=300, chart_type=None):
    if not _ACTIVE_OUTPUT_SERVICE:
        return None
    result = _ACTIVE_OUTPUT_SERVICE.save_chart(
        chart_id=filename,
        scope="global",
        static_fig=fig,
        dpi=dpi,
        chart_type=chart_type,
    )
    return result.get("static")


def _save_chart_speaker(fig, speaker, filename, dpi=300, chart_type=None):
    if not _ACTIVE_OUTPUT_SERVICE:
        return None
    result = _ACTIVE_OUTPUT_SERVICE.save_chart(
        chart_id=filename,
        scope="speaker",
        speaker=speaker,
        static_fig=fig,
        dpi=dpi,
        chart_type=chart_type,
    )
    return result.get("static")


def save_global_chart(fig, output_structure, base_name, filename, dpi=300, chart_type=None):
    return _save_chart_global(fig, filename, dpi=dpi, chart_type=chart_type)


def save_speaker_chart(
    fig, output_structure, base_name, speaker, filename, dpi=300, chart_type=None
):
    return _save_chart_speaker(fig, speaker, filename, dpi=dpi, chart_type=chart_type)


def _get_dynamic_views_mode() -> str:
    config = get_config()
    return getattr(config.output, "dynamic_views", "auto")


def _should_generate_views() -> bool:
    mode = _get_dynamic_views_mode()
    if mode == "off":
        return False
    if mode == "on" and not is_plotly_available():
        notify_user(
            "Plotly is required when dynamic_views='on'. Install transcriptx[plotly].",
            technical=True,
            section="wordclouds",
        )
        return False
    return True


def _relative_to_transcript(path: str | Path) -> str:
    if not _ACTIVE_OUTPUT_SERVICE:
        return str(path)
    path_obj = Path(path)
    try:
        return path_obj.relative_to(Path(_ACTIVE_OUTPUT_SERVICE.transcript_dir)).as_posix()
    except ValueError:
        return path_obj.as_posix()


def _build_terms_payload(
    freq: dict[str, Any],
    *,
    variant: str,
    variant_key: str,
    speaker: str | None,
    ngram: int,
    metric: str,
    min_count: int | None = None,
    min_bigram_count: int | None = None,
) -> dict[str, Any]:
    sorted_items = sorted(freq.items(), key=lambda item: item[1], reverse=True)
    terms = [
        WordcloudTerm(term=term, value=float(value), rank=idx + 1)
        for idx, (term, value) in enumerate(sorted_items)
    ]
    run_id = _ACTIVE_OUTPUT_SERVICE.run_id if _ACTIVE_OUTPUT_SERVICE else None
    transcript_key = _ACTIVE_OUTPUT_SERVICE.base_name if _ACTIVE_OUTPUT_SERVICE else None
    payload = WordcloudTerms(
        source="wordclouds",
        variant=variant,
        variant_key=variant_key,
        speaker=speaker,
        ngram=ngram,
        metric=metric,
        terms=terms,
        min_count=min_count,
        min_bigram_count=min_bigram_count,
        run_id=run_id,
        transcript_key=transcript_key,
    )
    return payload.to_dict()


def _save_terms_json(
    payload: dict[str, Any],
    *,
    filename: str,
    speaker: str | None,
) -> str | None:
    if not _ACTIVE_OUTPUT_SERVICE:
        return None
    if speaker:
        safe_speaker = str(speaker).replace(" ", "_").replace("/", "_")
        name = f"{safe_speaker}_{filename}.terms"
        return _ACTIVE_OUTPUT_SERVICE.save_data(
            payload,
            name,
            format_type="json",
            subdirectory="speakers",
            speaker=speaker,
        )
    name = f"{filename}.terms"
    return _ACTIVE_OUTPUT_SERVICE.save_data(payload, name, format_type="json")


def _build_wordcloud_explorer_html(
    title: str, payload: dict[str, Any], use_plotly: bool
) -> str:
    terms_json = json.dumps(payload)
    plotly_script = (
        '<script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>'
        if use_plotly
        else ""
    )
    table_mode_marker = "table-mode" if not use_plotly else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  {plotly_script}
  <style>
    body {{ font-family: Arial, sans-serif; margin: 16px; }}
    .controls {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }}
    .controls label {{ font-size: 12px; color: #333; }}
    #chart {{ width: 100%; height: 480px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 8px; font-size: 12px; }}
    th {{ background: #f5f5f5; text-align: left; }}
    .actions {{ display: flex; gap: 8px; }}
  </style>
</head>
<body class="{table_mode_marker}">
  <h2>{title}</h2>
  <div class="controls">
    <label>Search<br><input id="search" type="text" placeholder="filter terms"></label>
    <label>Top N<br><input id="topN" type="number" value="50" min="1" max="500"></label>
    <label>Min Value<br><input id="minValue" type="number" value="0" step="0.01"></label>
    <label>Sort<br>
      <select id="sortMode">
        <option value="value">Value</option>
        <option value="term">Term</option>
        <option value="rank">Rank</option>
      </select>
    </label>
    <div class="actions">
      <button id="copyTerms">Copy filtered terms</button>
      <button id="downloadCsv">Download CSV</button>
    </div>
  </div>
  <div id="chart"></div>
  <div id="table"></div>
  <script>
    window.WORDCLOUD_TERMS = {terms_json};
  </script>
  <script>
    const terms = window.WORDCLOUD_TERMS.terms || [];
    const searchInput = document.getElementById('search');
    const topNInput = document.getElementById('topN');
    const minValueInput = document.getElementById('minValue');
    const sortModeInput = document.getElementById('sortMode');
    const tableContainer = document.getElementById('table');

    function filteredTerms() {{
      const search = searchInput.value.toLowerCase();
      const minValue = parseFloat(minValueInput.value || '0');
      const topN = parseInt(topNInput.value || '50', 10);
      let items = terms.filter(t => t.term.toLowerCase().includes(search) && t.value >= minValue);
      const sortMode = sortModeInput.value;
      if (sortMode === 'term') {{
        items = items.sort((a, b) => a.term.localeCompare(b.term));
      }} else if (sortMode === 'rank') {{
        items = items.sort((a, b) => a.rank - b.rank);
      }} else {{
        items = items.sort((a, b) => b.value - a.value);
      }}
      return items.slice(0, topN);
    }}

    function renderTable(items) {{
      const rows = items.map(t => `<tr><td>${{t.rank}}</td><td>${{t.term}}</td><td>${{t.value}}</td></tr>`).join('');
      tableContainer.innerHTML = `
        <table>
          <thead><tr><th>Rank</th><th>Term</th><th>Value</th></tr></thead>
          <tbody>${{rows}}</tbody>
        </table>`;
    }}

    function renderPlotly(items) {{
      if (!window.Plotly) {{
        renderTable(items);
        return;
      }}
      const x = items.map(t => t.value).reverse();
      const y = items.map(t => t.term).reverse();
      const data = [{{
        type: 'bar',
        orientation: 'h',
        x: x,
        y: y
      }}];
      const layout = {{
        margin: {{ l: 200, r: 20, t: 30, b: 40 }},
        height: 480,
        xaxis: {{ title: 'Value' }},
        yaxis: {{ title: 'Term' }}
      }};
      window.Plotly.newPlot('chart', data, layout, {{displayModeBar: false}});
    }}

    function render() {{
      const items = filteredTerms();
      renderTable(items);
      renderPlotly(items);
    }}

    function toCsv(items) {{
      const rows = ['term,value'].concat(items.map(t => `${{t.term}},${{t.value}}`));
      return rows.join('\\n');
    }}

    document.getElementById('copyTerms').addEventListener('click', () => {{
      const items = filteredTerms();
      const csv = toCsv(items);
      navigator.clipboard.writeText(csv);
    }});

    document.getElementById('downloadCsv').addEventListener('click', () => {{
      const items = filteredTerms();
      const csv = toCsv(items);
      const blob = new Blob([csv], {{ type: 'text/csv' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'wordcloud_terms.csv';
      a.click();
      URL.revokeObjectURL(url);
    }});

    searchInput.addEventListener('input', render);
    topNInput.addEventListener('input', render);
    minValueInput.addEventListener('input', render);
    sortModeInput.addEventListener('change', render);
    render();
  </script>
</body>
</html>"""


def _save_wordcloud_view(
    payload: dict[str, Any],
    *,
    title: str,
    filename: str,
    speaker: str | None,
    source_terms_path: str | None,
    thumbnail_path: str | None,
) -> None:
    if not _ACTIVE_OUTPUT_SERVICE or not _should_generate_views():
        return
    mode = _get_dynamic_views_mode()
    use_plotly = mode != "off" and (mode == "on" or is_plotly_available())
    html = _build_wordcloud_explorer_html(title, payload, use_plotly=use_plotly)
    depends_on = [path for path in [source_terms_path, thumbnail_path] if path]
    viz_suffix = None
    if speaker:
        viz_suffix = str(speaker).replace(" ", "_").replace("/", "_")
    viz_id = f"wordclouds.{filename}.view"
    if viz_suffix:
        viz_id = f"{viz_id}.{viz_suffix}"
    _ACTIVE_OUTPUT_SERVICE.save_view_html(
        name=f"{filename}_explorer",
        html_content=html,
        module="wordclouds",
        scope="speaker" if speaker else "global",
        speaker=speaker,
        view_kind="wordcloud_explorer",
        viz_id=viz_id,
        depends_on=depends_on,
        metadata={
            "variant": payload.get("variant"),
            "variant_key": payload.get("variant_key"),
            "ngram": payload.get("ngram"),
            "metric": payload.get("metric"),
            "source_terms_path": source_terms_path,
            "thumbnail_path": thumbnail_path,
        },
    )


def _get_wordcloud_class():
    return get_wordcloud().WordCloud


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

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str] = None,
        tic_list: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform wordcloud analysis on transcript segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility, not used)
            tic_list: Optional list of tics to filter (from tics module)

        Returns:
            Dictionary containing wordcloud analysis results
        """
        import warnings

        if speaker_map is not None:
            warnings.warn(
                "speaker_map parameter is deprecated. Speaker identification now uses "
                "speaker_db_id from segments directly.",
                DeprecationWarning,
                stacklevel=2,
            )

        # Group texts by speaker using database-driven approach
        grouped = group_texts_by_speaker(segments)

        # Extract tics if not provided
        if tic_list is None:
            from transcriptx.core.analysis.tics import extract_tics_and_top_words

            _, _ = extract_tics_and_top_words(grouped)
            # Note: tic_list extraction would need to be done here
            tic_list = []

        return {
            "grouped_texts": dict(grouped),
            "tic_list": tic_list,
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
        grouped_texts = results["grouped_texts"]
        tic_list = results.get("tic_list", [])
        base_name = output_service.base_name
        output_structure = output_service.get_output_structure()

        # Use existing run_all_wordclouds function which handles all wordcloud types
        # This is a bridge approach - full refactoring would extract each wordcloud type
        # For now, we'll delegate to the existing function
        transcript_path = output_service.transcript_path
        run_all_wordclouds(
            transcript_path, tic_list, transcript_dir=output_structure.transcript_dir
        )


def group_texts_by_speaker(segments: list) -> dict:
    """
    Group text segments by speaker using database-driven speaker identification.

    Uses speaker_db_id when available to properly distinguish speakers with the same name.

    Args:
        segments: List of transcript segments

    Returns:
        Dictionary mapping speaker display name to list of text strings
    """
    from transcriptx.utils.text_utils import is_named_speaker

    # Group segments by speaker using database-driven approach
    grouped_segments = group_segments_by_speaker(segments)

    # Extract texts grouped by display name
    grouped = defaultdict(list)
    for grouping_key, segs in grouped_segments.items():
        display_name = get_speaker_display_name(grouping_key, segs, segments)
        if display_name:
            texts = [seg.get("text", "") for seg in segs if seg.get("text")]
            if texts:
                grouped[display_name].extend(texts)

    return grouped


def generate_wordcloud(
    text: str,
    output_structure,
    base_name: str,
    speaker: str,
    filename: str,
    chart_type: str = "basic",
    title: str = "Word Cloud",
) -> dict[str, int]:
    words = tokenize_and_filter(text)
    bigrams = [(words[i], words[i + 1]) for i in range(len(words) - 1)]
    bigram_phrases = [" ".join(pair) for pair in bigrams]
    all_tokens = words + bigram_phrases
    freq = Counter(all_tokens)

    if not freq:
        notify_user(
            f"⚠️ Skipping word cloud '{title}': no tokens to display.",
            technical=True,
            section="wordclouds",
        )
        return {}

    wc = _get_wordcloud_class()(
        width=800, height=400, background_color="white"
    ).generate_from_frequencies(freq)
    fig = plt.figure(figsize=(10, 5))
    chart_path = None
    view_speaker = None if speaker == "wordcloud-ALL" else speaker
    try:
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")
        plt.title(title)
        plt.tight_layout()

        if speaker == "wordcloud-ALL":
            chart_path = save_global_chart(
                fig,
                output_structure,
                base_name,
                filename,
                dpi=300,
                chart_type=chart_type,
            )
        else:
            chart_path = save_speaker_chart(
                fig,
                output_structure,
                base_name,
                speaker,
                filename,
                dpi=300,
                chart_type=chart_type,
            )
    finally:
        # Always close the figure (even if saving fails) to avoid accumulating
        # many open figures in batch runs.
        plt.close(fig)

    payload = _build_terms_payload(
        dict(freq),
        variant="basic",
        variant_key="basic_unigram",
        speaker=view_speaker,
        ngram=1,
        metric="count",
    )
    terms_path = _save_terms_json(payload, filename=filename, speaker=view_speaker)
    _save_wordcloud_view(
        payload,
        title=title,
        filename=filename,
        speaker=view_speaker,
        source_terms_path=_relative_to_transcript(terms_path) if terms_path else None,
        thumbnail_path=_relative_to_transcript(chart_path) if chart_path else None,
    )
    notify_user(
        f"✅ Word cloud saved for {speaker}", technical=False, section="wordclouds"
    )

    return freq


def save_freq_json_csv(
    freq: dict[str, int], output_structure, prefix: str, speaker: str
) -> None:
    if speaker != "ALL":
        config = get_config()
        exclude = getattr(
            getattr(config, "analysis", None),
            "exclude_unidentified_from_speaker_charts",
            False,
        )
        if exclude and not is_named_speaker(speaker):
            return
    safe = speaker.replace(" ", "_").replace("/", "_")

    if speaker == "ALL":
        json_path = output_structure.global_data_dir / f"{prefix}-{safe}.json"
        csv_path = output_structure.global_data_dir / f"{prefix}-{safe}.csv"
    else:
        json_path = output_structure.speaker_data_dir / f"{prefix}-{safe}.json"
        csv_path = output_structure.speaker_data_dir / f"{prefix}-{safe}.csv"

    # Ensure directories exist before saving
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    write_json(json_path, freq, indent=2, ensure_ascii=False)
    rows = [[token, count] for token, count in freq.items()]
    write_csv(csv_path, rows, header=["Token", "Frequency"])


def generate_bigram_wordclouds(
    grouped: dict[str, list[str]], output_structure, base_name: str
) -> None:
    for speaker, texts in grouped.items():
        words = tokenize_and_filter(" ".join(texts))
        bigrams = [f"{words[i]}_{words[i+1]}" for i in range(len(words) - 1)]
        freq = Counter(bigrams)

        if not freq:
            notify_user(
                f"⚠️ No bigrams found for speaker: {speaker}",
                technical=True,
                section="wordclouds",
            )
            continue

        wc = _get_wordcloud_class()(
            width=800, height=400, background_color="white"
        ).generate_from_frequencies(freq)
        fig = plt.figure(figsize=(10, 5))
        chart_path = None
        try:
            plt.imshow(wc, interpolation="bilinear")
            plt.axis("off")
            plt.title(f"{speaker} – Bigrams Only")
            plt.tight_layout()
            chart_path = save_speaker_chart(
                fig,
                output_structure,
                base_name,
                speaker,
                "wordcloud-bigrams",
                dpi=300,
                chart_type="bigrams",
            )
        finally:
            plt.close(fig)

        payload = _build_terms_payload(
            dict(freq),
            variant="bigrams",
            variant_key="bigrams_count",
            speaker=speaker,
            ngram=2,
            metric="count",
        )
        terms_path = _save_terms_json(payload, filename="wordcloud-bigrams", speaker=speaker)
        _save_wordcloud_view(
            payload,
            title=f"{speaker} – Bigrams Only",
            filename="wordcloud-bigrams",
            speaker=speaker,
            source_terms_path=_relative_to_transcript(terms_path) if terms_path else None,
            thumbnail_path=_relative_to_transcript(chart_path) if chart_path else None,
        )
        save_freq_json_csv(freq, output_structure, f"{base_name}-bigrams", speaker)


def generate_tfidf_wordclouds(
    grouped: dict[str, list[str]], output_structure, base_name: str
) -> None:
    config = get_config()
    exclude = getattr(
        getattr(config, "analysis", None),
        "exclude_unidentified_from_speaker_charts",
        False,
    )
    speakers = [s for s in grouped if is_named_speaker(s)] if exclude else list(grouped.keys())
    documents = [" ".join(grouped[s]) for s in speakers]
    filtered_docs = [" ".join(tokenize_and_filter(doc)) for doc in documents]

    # Check if we have any non-empty documents after filtering
    non_empty_docs = [doc for doc in filtered_docs if doc.strip()]
    if not non_empty_docs:
        notify_user(
            "⚠️ No valid content found for TF-IDF word clouds after filtering. Skipping.",
            technical=True,
            section="wordclouds",
        )
        return

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        vector_config = get_config().analysis.vectorization
        vec = TfidfVectorizer(
            ngram_range=vector_config.wordcloud_ngram_range,
            max_features=vector_config.wordcloud_max_features,
        )
        matrix = vec.fit_transform(non_empty_docs)
    except ValueError as e:
        if "empty vocabulary" in str(e):
            notify_user(
                "⚠️ Empty vocabulary for TF-IDF word clouds. All content was filtered out. Skipping.",
                technical=True,
                section="wordclouds",
            )
            return
        else:
            raise e
    features = vec.get_feature_names_out()

    for idx, speaker in enumerate(speakers):
        # Handle sparse matrix properly
        row = matrix[idx]
        if isinstance(row, spmatrix):
            scores = row.toarray().flatten()
        else:
            scores = np.array(row).flatten()

        freq = {features[i]: scores[i] for i in range(len(scores)) if scores[i] > 0}
        if not freq:
            continue
        wc = _get_wordcloud_class()(
            width=800, height=400, background_color="white"
        ).generate_from_frequencies(freq)
        fig = plt.figure(figsize=(10, 5))
        chart_path = None
        try:
            plt.imshow(wc, interpolation="bilinear")
            plt.axis("off")
            plt.title(f"{speaker} – TF-IDF Keywords")
            plt.tight_layout()
            chart_path = save_speaker_chart(
                fig,
                output_structure,
                base_name,
                speaker,
                "tfidf",
                dpi=300,
                chart_type="tfidf",
            )
        finally:
            plt.close(fig)
        save_freq_json_csv(freq, output_structure, f"{base_name}-tfidf", speaker)

        payload = _build_terms_payload(
            dict(freq),
            variant="tfidf",
            variant_key="tfidf_unigram",
            speaker=speaker,
            ngram=1,
            metric="tfidf",
        )
        terms_path = _save_terms_json(payload, filename="tfidf", speaker=speaker)
        _save_wordcloud_view(
            payload,
            title=f"{speaker} – TF-IDF Keywords",
            filename="tfidf",
            speaker=speaker,
            source_terms_path=_relative_to_transcript(terms_path) if terms_path else None,
            thumbnail_path=_relative_to_transcript(chart_path) if chart_path else None,
        )

    # Global
    full = " ".join(non_empty_docs)
    global_matrix = vec.fit_transform([full])
    global_row = global_matrix[0]
    if isinstance(global_row, spmatrix):
        global_scores = global_row.toarray().flatten()
    else:
        global_scores = np.array(global_row).flatten()

    global_freq = {
        features[i]: global_scores[i]
        for i in range(len(features))
        if global_scores[i] > 0
    }
    wc = _get_wordcloud_class()(
        width=800, height=400, background_color="white"
    ).generate_from_frequencies(global_freq)
    fig = plt.figure(figsize=(10, 5))
    chart_path = None
    try:
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")
        plt.title("All Speakers – TF-IDF")
        plt.tight_layout()
        chart_path = save_global_chart(
            fig,
            output_structure,
            base_name,
            "tfidf-ALL",
            dpi=300,
            chart_type="tfidf",
        )
    finally:
        plt.close(fig)
    save_freq_json_csv(global_freq, output_structure, f"{base_name}-tfidf", "ALL")

    payload = _build_terms_payload(
        dict(global_freq),
        variant="tfidf",
        variant_key="tfidf_unigram",
        speaker=None,
        ngram=1,
        metric="tfidf",
    )
    terms_path = _save_terms_json(payload, filename="tfidf-ALL", speaker=None)
    _save_wordcloud_view(
        payload,
        title="All Speakers – TF-IDF",
        filename="tfidf-ALL",
        speaker=None,
        source_terms_path=_relative_to_transcript(terms_path) if terms_path else None,
        thumbnail_path=_relative_to_transcript(chart_path) if chart_path else None,
    )


def generate_bigram_tfidf_wordclouds(
    grouped: dict[str, list[str]], output_structure, base_name: str
) -> None:
    speakers = list(grouped.keys())
    documents = [" ".join(grouped[s]) for s in speakers]
    filtered_docs = [" ".join(tokenize_and_filter(doc)) for doc in documents]

    # Check if we have any non-empty documents after filtering
    non_empty_docs = [doc for doc in filtered_docs if doc.strip()]
    if not non_empty_docs:
        notify_user(
            "⚠️ No valid content found for bigram TF-IDF word clouds after filtering. Skipping.",
            technical=True,
            section="wordclouds",
        )
        return

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        vector_config = get_config().analysis.vectorization
        vec = TfidfVectorizer(
            ngram_range=vector_config.wordcloud_ngram_range,
            max_features=vector_config.wordcloud_max_features,
        )
        matrix = vec.fit_transform(non_empty_docs)
    except ValueError as e:
        if "empty vocabulary" in str(e):
            notify_user(
                "⚠️ Empty vocabulary for bigram TF-IDF word clouds. All content was filtered out. Skipping.",
                technical=True,
                section="wordclouds",
            )
            return
        else:
            raise e
    features = vec.get_feature_names_out()

    for idx, speaker in enumerate(speakers):
        # Handle sparse matrix properly
        row = matrix[idx]
        if isinstance(row, spmatrix):
            scores = row.toarray().flatten()
        else:
            scores = np.array(row).flatten()

        freq = {features[i]: scores[i] for i in range(len(scores)) if scores[i] > 0}
        if not freq:
            continue
        wc = _get_wordcloud_class()(
            width=800, height=400, background_color="white"
        ).generate_from_frequencies(freq)
        fig = plt.figure(figsize=(10, 5))
        chart_path = None
        try:
            plt.imshow(wc, interpolation="bilinear")
            plt.axis("off")
            plt.title(f"{speaker} – TF-IDF Bigrams")
            plt.tight_layout()
            chart_path = save_speaker_chart(
                fig,
                output_structure,
                base_name,
                speaker,
                "tfidf-bigrams",
                dpi=300,
                chart_type="tfidf_bigrams",
            )
        finally:
            plt.close(fig)
        save_freq_json_csv(
            freq, output_structure, f"{base_name}-tfidf-bigrams", speaker
        )

        payload = _build_terms_payload(
            dict(freq),
            variant="tfidf_bigrams",
            variant_key="tfidf_bigrams",
            speaker=speaker,
            ngram=2,
            metric="tfidf",
        )
        terms_path = _save_terms_json(payload, filename="tfidf-bigrams", speaker=speaker)
        _save_wordcloud_view(
            payload,
            title=f"{speaker} – TF-IDF Bigrams",
            filename="tfidf-bigrams",
            speaker=speaker,
            source_terms_path=_relative_to_transcript(terms_path) if terms_path else None,
            thumbnail_path=_relative_to_transcript(chart_path) if chart_path else None,
        )

    # Global
    full = " ".join(filtered_docs)
    global_matrix = vec.fit_transform([full])
    global_row = global_matrix[0]
    if isinstance(global_row, spmatrix):
        global_scores = global_row.toarray().flatten()
    else:
        global_scores = np.array(global_row).flatten()

    global_freq = {
        features[i]: global_scores[i]
        for i in range(len(features))
        if global_scores[i] > 0
    }
    wc = _get_wordcloud_class()(
        width=800, height=400, background_color="white"
    ).generate_from_frequencies(global_freq)
    fig = plt.figure(figsize=(10, 5))
    chart_path = None
    try:
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")
        plt.title("All Speakers – TF-IDF Bigrams")
        plt.tight_layout()
        chart_path = save_global_chart(
            fig,
            output_structure,
            base_name,
            "tfidf-bigrams-ALL",
            dpi=300,
            chart_type="tfidf_bigrams",
        )
    finally:
        plt.close(fig)
    save_freq_json_csv(
        global_freq, output_structure, f"{base_name}-tfidf-bigrams", "ALL"
    )

    payload = _build_terms_payload(
        dict(global_freq),
        variant="tfidf_bigrams",
        variant_key="tfidf_bigrams",
        speaker=None,
        ngram=2,
        metric="tfidf",
    )
    terms_path = _save_terms_json(payload, filename="tfidf-bigrams-ALL", speaker=None)
    _save_wordcloud_view(
        payload,
        title="All Speakers – TF-IDF Bigrams",
        filename="tfidf-bigrams-ALL",
        speaker=None,
        source_terms_path=_relative_to_transcript(terms_path) if terms_path else None,
        thumbnail_path=_relative_to_transcript(chart_path) if chart_path else None,
    )


def generate_tic_wordclouds(
    grouped: dict[str, list[str]], output_structure, base_name: str
) -> None:
    config = get_config()
    exclude = getattr(
        getattr(config, "analysis", None),
        "exclude_unidentified_from_speaker_charts",
        False,
    )
    for speaker, texts in grouped.items():
        if exclude and not is_named_speaker(speaker):
            continue
        tics = extract_tics_from_text(" ".join(texts))
        freq = Counter(tics)
        if not freq:
            continue
        wc = _get_wordcloud_class()(
            width=800, height=400, background_color="white"
        ).generate_from_frequencies(freq)
        fig = plt.figure(figsize=(10, 5))
        chart_path = None
        try:
            plt.imshow(wc, interpolation="bilinear")
            plt.axis("off")
            plt.title(f"{speaker} – Verbal Tics")
            plt.tight_layout()
            chart_path = save_speaker_chart(
                fig,
                output_structure,
                base_name,
                speaker,
                "wordcloud-tics",
                dpi=300,
                chart_type="tics",
            )
        finally:
            plt.close(fig)
        save_freq_json_csv(freq, output_structure, f"{base_name}-tics", speaker)

        payload = _build_terms_payload(
            dict(freq),
            variant="tics",
            variant_key="tics_unigram",
            speaker=speaker,
            ngram=1,
            metric="count",
        )
        terms_path = _save_terms_json(payload, filename="wordcloud-tics", speaker=speaker)
        _save_wordcloud_view(
            payload,
            title=f"{speaker} – Verbal Tics",
            filename="wordcloud-tics",
            speaker=speaker,
            source_terms_path=_relative_to_transcript(terms_path) if terms_path else None,
            thumbnail_path=_relative_to_transcript(chart_path) if chart_path else None,
        )


def generate_pos_wordclouds(
    grouped: dict[str, list[str]], output_structure, base_name: str, pos_filter: str
) -> None:
    pos_tags = {
        "noun": {"NOUN", "PROPN"},
        "verb": {"VERB"},
        "adj": {"ADJ"},
    }.get(pos_filter.lower(), set())

    for speaker, texts in grouped.items():
        text = " ".join(texts)
        doc = nlp(text.lower())
        tokens = [
            t.text for t in doc if t.pos_ in pos_tags and t.text not in ALL_STOPWORDS
        ]
        freq = Counter(tokens)
        if not freq:
            continue
        wc = _get_wordcloud_class()(
            width=800, height=400, background_color="white"
        ).generate_from_frequencies(freq)
        fig = plt.figure(figsize=(10, 5))
        chart_path = None
        try:
            plt.imshow(wc, interpolation="bilinear")
            plt.axis("off")
            plt.title(f"{speaker} – {pos_filter.title()}s")
            plt.tight_layout()
            chart_path = save_speaker_chart(
                fig,
                output_structure,
                base_name,
                speaker,
                f"wordcloud-{pos_filter}",
                dpi=300,
                chart_type=f"pos_{pos_filter}",
            )
        finally:
            plt.close(fig)
        save_freq_json_csv(freq, output_structure, f"{base_name}-{pos_filter}", speaker)

        payload = _build_terms_payload(
            dict(freq),
            variant=f"pos_{pos_filter}",
            variant_key=f"pos_{pos_filter}_unigram",
            speaker=speaker,
            ngram=1,
            metric="count",
        )
        terms_path = _save_terms_json(
            payload, filename=f"wordcloud-{pos_filter}", speaker=speaker
        )
        _save_wordcloud_view(
            payload,
            title=f"{speaker} – {pos_filter.title()}s",
            filename=f"wordcloud-{pos_filter}",
            speaker=speaker,
            source_terms_path=_relative_to_transcript(terms_path) if terms_path else None,
            thumbnail_path=_relative_to_transcript(chart_path) if chart_path else None,
        )


def run_group_wordclouds(
    grouped: Dict[str, List[str]],
    group_base_dir: str | Path,
    base_name: str,
    run_id: str,
    tic_list: list[str] | None = None,
) -> None:
    from transcriptx.core.utils.logger import get_logger

    logger = get_logger()
    if not grouped:
        logger.warning("[WORDCLOUDS] No grouped text for group wordclouds.")
        return

    output_structure = create_standard_output_structure(str(group_base_dir), "wordclouds")
    virtual_path = str(Path(group_base_dir) / f"{base_name}.virtual")
    output_service = create_output_service(
        virtual_path,
        "wordclouds",
        output_dir=str(group_base_dir),
        run_id=run_id,
    )

    def _normalize_chunk(text: str) -> str:
        return " ".join(text.split())

    grouped_joined: Dict[str, str] = {}
    for speaker, chunks in grouped.items():
        cleaned = [_normalize_chunk(chunk) for chunk in chunks if chunk and chunk.strip()]
        if not cleaned:
            continue
        grouped_joined[speaker] = "\n".join(cleaned)

    if not grouped_joined:
        logger.warning("[WORDCLOUDS] No non-empty text for group wordclouds.")
        return

    with use_output_service(output_service):
        for speaker, joined in grouped_joined.items():
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
                save_freq_json_csv(freq, output_structure, f"{base_name}-basic", speaker)

        all_text = "\n".join(grouped_joined.values())
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


def run_all_wordclouds(
    transcript_path: str, tic_list: list[str], transcript_dir: str | None = None
) -> None:
    from transcriptx.core.utils.path_utils import get_base_name, get_transcript_dir
    from transcriptx.core.utils.logger import get_logger

    logger = get_logger()

    base_name = get_base_name(transcript_path)
    # Use provided transcript_dir if available, otherwise use standardized path
    if transcript_dir is None:
        transcript_dir = get_transcript_dir(transcript_path)

    # Use output standards for directory structure
    output_structure = create_standard_output_structure(transcript_dir, "wordclouds")
    global _ACTIVE_OUTPUT_SERVICE
    _ACTIVE_OUTPUT_SERVICE = create_output_service(
        transcript_path,
        "wordclouds",
        output_dir=transcript_dir,
        run_id=Path(transcript_dir).name,
    )

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

    # Group texts by speaker using database-driven approach
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
                f"{all_words[i]}_{all_words[i+1]}" for i in range(len(all_words) - 1)
            ]
            global_freq = Counter(bigrams)

            if global_freq:
                wc = _get_wordcloud_class()(
                    width=800, height=400, background_color="white"
                ).generate_from_frequencies(global_freq)
                fig = plt.figure(figsize=(10, 5))
                chart_path = None
                try:
                    plt.imshow(wc, interpolation="bilinear")
                    plt.axis("off")
                    plt.title("All Speakers – Bigrams Only")
                    plt.tight_layout()
                    chart_path = save_global_chart(
                        fig,
                        output_structure,
                        base_name,
                        "wordcloud-bigrams-ALL",
                        dpi=300,
                        chart_type="bigrams",
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
                    source_terms_path=_relative_to_transcript(terms_path)
                    if terms_path
                    else None,
                    thumbnail_path=_relative_to_transcript(chart_path)
                    if chart_path
                    else None,
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
                fig = plt.figure(figsize=(10, 5))
                chart_path = None
                try:
                    plt.imshow(wc, interpolation="bilinear")
                    plt.axis("off")
                    plt.title(f"All Speakers – {pos_filter.title()}s")
                    plt.tight_layout()
                    chart_path = save_global_chart(
                        fig,
                        output_structure,
                        base_name,
                        f"wordcloud-{pos_filter}-ALL",
                        dpi=300,
                        chart_type=f"pos_{pos_filter}",
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
                    source_terms_path=_relative_to_transcript(terms_path)
                    if terms_path
                    else None,
                    thumbnail_path=_relative_to_transcript(chart_path)
                    if chart_path
                    else None,
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
    speaker_map: dict[str, str] = None,
) -> None:
    """
    Generate word clouds for transcript segments.

    Args:
        segments: List of transcript segments
        base_name: Base name for output files
        transcript_dir: Output directory
        speaker_map: Speaker mapping dictionary (deprecated, kept for backward compatibility, not used)
    """
    import warnings

    if speaker_map is not None:
        warnings.warn(
            "speaker_map parameter is deprecated. Speaker identification now uses "
            "speaker_db_id from segments directly.",
            DeprecationWarning,
            stacklevel=2,
        )

    from transcriptx.core.utils.nlp_utils import load_tics

    # Directories will be created lazily when files are saved
    # No need to create them upfront
    global _ACTIVE_OUTPUT_SERVICE
    _ACTIVE_OUTPUT_SERVICE = create_output_service(
        str(Path(transcript_dir) / f"{base_name}.json"),
        "wordclouds",
        output_dir=transcript_dir,
        run_id=Path(transcript_dir).name,
    )

    # Group texts by speaker using database-driven approach
    grouped = group_texts_by_speaker(segments)

    # Load tics
    tic_list = load_tics()

    # Create temporary transcript file for compatibility
    import json
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"segments": segments}, f)
        temp_path = f.name

    try:
        # Pass the correct transcript_dir to avoid recalculating from temp file path
        run_all_wordclouds(temp_path, tic_list, transcript_dir=transcript_dir)
    finally:
        os.unlink(temp_path)
