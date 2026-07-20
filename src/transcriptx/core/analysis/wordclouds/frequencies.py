"""Token frequencies, TF-IDF, bigram/tic/POS wordcloud generators."""

from __future__ import annotations

from collections import Counter

import numpy as np
from scipy.sparse import spmatrix

from transcriptx.core.analysis.wordclouds.output_bridge import (
    _include_speaker_wordcloud,
    _relative_to_transcript,
    save_global_chart,
    save_speaker_chart,
)
from transcriptx.core.analysis.wordclouds.plotting import (
    _get_wordcloud_class,
    _save_wordcloud_view,
    _wordcloud_figure,
)
from transcriptx.core.analysis.wordclouds.terms_io import (
    _build_terms_payload,
    _save_terms_json,
)
from transcriptx.core.utils.artifact_writer import write_csv, write_json
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.lazy_imports import lazy_pyplot
from transcriptx.core.utils.nlp_utils import (
    ALL_STOPWORDS,
    extract_tics_from_text,
    nlp,
    tokenize_and_filter,
)
from transcriptx.core.utils.notifications import notify_user

plt = lazy_pyplot()


def save_freq_json_csv(
    freq: dict[str, int], output_structure, prefix: str, speaker: str
) -> None:
    if speaker != "ALL" and not _include_speaker_wordcloud(speaker):
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
        if not _include_speaker_wordcloud(speaker):
            continue
        words = tokenize_and_filter(" ".join(texts))
        # Use readable phrase labels in outputs and UI.
        bigrams = [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]
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
        fig, ax = _wordcloud_figure(wc)
        chart_path = None
        try:
            ax.set_title(f"{speaker} – Bigrams Only")
            fig.tight_layout()
            chart_path = save_speaker_chart(
                fig,
                output_structure,
                base_name,
                speaker,
                "wordcloud-bigrams",
                dpi=300,
                chart_type="bigrams",
                title=f"{speaker} – Bigrams Only",
                viz_id="wordcloud.wordcloud.speaker.bigrams",
                frequencies=freq,
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
        terms_path = _save_terms_json(
            payload, filename="wordcloud-bigrams", speaker=speaker
        )
        _save_wordcloud_view(
            payload,
            title=f"{speaker} – Bigrams Only",
            filename="wordcloud-bigrams",
            speaker=speaker,
            source_terms_path=(
                _relative_to_transcript(terms_path) if terms_path else None
            ),
            thumbnail_path=_relative_to_transcript(chart_path) if chart_path else None,
        )
        save_freq_json_csv(freq, output_structure, f"{base_name}-bigrams", speaker)


def generate_tfidf_wordclouds(
    grouped: dict[str, list[str]], output_structure, base_name: str
) -> None:
    speakers = [s for s in grouped if _include_speaker_wordcloud(s)]
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
        fig, ax = _wordcloud_figure(wc)
        chart_path = None
        try:
            ax.set_title(f"{speaker} – TF-IDF Keywords")
            fig.tight_layout()
            chart_path = save_speaker_chart(
                fig,
                output_structure,
                base_name,
                speaker,
                "tfidf",
                dpi=300,
                chart_type="tfidf",
                title=f"{speaker} – TF-IDF Keywords",
                viz_id="wordcloud.wordcloud.speaker.tfidf",
                frequencies=freq,
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
            source_terms_path=(
                _relative_to_transcript(terms_path) if terms_path else None
            ),
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
    fig, ax = _wordcloud_figure(wc)
    chart_path = None
    try:
        ax.set_title("All Speakers – TF-IDF")
        fig.tight_layout()
        chart_path = save_global_chart(
            fig,
            output_structure,
            base_name,
            "tfidf-ALL",
            dpi=300,
            chart_type="tfidf",
            title="All Speakers – TF-IDF",
            viz_id="wordcloud.wordcloud.global.tfidf",
            frequencies=global_freq,
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
    speakers = [s for s in grouped if _include_speaker_wordcloud(s)]
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
        fig, ax = _wordcloud_figure(wc)
        chart_path = None
        try:
            ax.set_title(f"{speaker} – TF-IDF Bigrams")
            fig.tight_layout()
            chart_path = save_speaker_chart(
                fig,
                output_structure,
                base_name,
                speaker,
                "tfidf-bigrams",
                dpi=300,
                chart_type="tfidf_bigrams",
                title=f"{speaker} – TF-IDF Bigrams",
                viz_id="wordcloud.wordcloud.speaker.tfidf_bigrams",
                frequencies=freq,
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
        terms_path = _save_terms_json(
            payload, filename="tfidf-bigrams", speaker=speaker
        )
        _save_wordcloud_view(
            payload,
            title=f"{speaker} – TF-IDF Bigrams",
            filename="tfidf-bigrams",
            speaker=speaker,
            source_terms_path=(
                _relative_to_transcript(terms_path) if terms_path else None
            ),
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
    fig, ax = _wordcloud_figure(wc)
    chart_path = None
    try:
        ax.set_title("All Speakers – TF-IDF Bigrams")
        fig.tight_layout()
        chart_path = save_global_chart(
            fig,
            output_structure,
            base_name,
            "tfidf-bigrams-ALL",
            dpi=300,
            chart_type="tfidf_bigrams",
            title="All Speakers – TF-IDF Bigrams",
            viz_id="wordcloud.wordcloud.global.tfidf_bigrams",
            frequencies=global_freq,
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
    for speaker, texts in grouped.items():
        if not _include_speaker_wordcloud(speaker):
            continue
        tics = extract_tics_from_text(" ".join(texts))
        freq = Counter(tics)
        if not freq:
            continue
        wc = _get_wordcloud_class()(
            width=800, height=400, background_color="white"
        ).generate_from_frequencies(freq)
        fig, ax = _wordcloud_figure(wc)
        chart_path = None
        try:
            ax.set_title(f"{speaker} – Verbal Tics")
            fig.tight_layout()
            chart_path = save_speaker_chart(
                fig,
                output_structure,
                base_name,
                speaker,
                "wordcloud-tics",
                dpi=300,
                chart_type="tics",
                title=f"{speaker} – Verbal Tics",
                viz_id="wordcloud.wordcloud.speaker.tics",
                frequencies=freq,
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
        terms_path = _save_terms_json(
            payload, filename="wordcloud-tics", speaker=speaker
        )
        _save_wordcloud_view(
            payload,
            title=f"{speaker} – Verbal Tics",
            filename="wordcloud-tics",
            speaker=speaker,
            source_terms_path=(
                _relative_to_transcript(terms_path) if terms_path else None
            ),
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
        if not _include_speaker_wordcloud(speaker):
            continue
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
        fig, ax = _wordcloud_figure(wc)
        chart_path = None
        try:
            ax.set_title(f"{speaker} – {pos_filter.title()}s")
            fig.tight_layout()
            chart_path = save_speaker_chart(
                fig,
                output_structure,
                base_name,
                speaker,
                f"wordcloud-{pos_filter}",
                dpi=300,
                chart_type=f"pos_{pos_filter}",
                title=f"{speaker} – {pos_filter.title()}s",
                viz_id=f"wordcloud.wordcloud.speaker.{pos_filter}",
                frequencies=freq,
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
            source_terms_path=(
                _relative_to_transcript(terms_path) if terms_path else None
            ),
            thumbnail_path=_relative_to_transcript(chart_path) if chart_path else None,
        )
