"""Matplotlib / wordcloud rendering and explorer view registration."""

from __future__ import annotations

from collections import Counter
from typing import Any

from transcriptx.core.analysis.wordclouds.output_bridge import (
    _active_output_service,
    _relative_to_transcript,
    _should_generate_views,
    save_global_chart,
    save_speaker_chart,
)
from transcriptx.core.analysis.wordclouds.terms_io import (
    _build_terms_payload,
    _build_wordcloud_explorer_html,
    _save_terms_json,
)
from transcriptx.core.utils.lazy_imports import get_wordcloud, lazy_pyplot
from transcriptx.core.utils.nlp_utils import tokenize_and_filter
from transcriptx.core.utils.notifications import notify_user

plt = lazy_pyplot()


def _save_wordcloud_view(
    payload: dict[str, Any],
    *,
    title: str,
    filename: str,
    speaker: str | None,
    source_terms_path: str | None,
    thumbnail_path: str | None,
    output_service: Any | None = None,
) -> None:
    svc = _active_output_service(output_service)
    if not svc or not _should_generate_views():
        return
    html = _build_wordcloud_explorer_html(title, payload)
    depends_on = [path for path in [source_terms_path, thumbnail_path] if path]
    viz_suffix = None
    if speaker:
        viz_suffix = str(speaker).replace(" ", "_").replace("/", "_")
    viz_id = f"wordclouds.{filename}.view"
    if viz_suffix:
        viz_id = f"{viz_id}.{viz_suffix}"
    svc.save_view_html(
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


def _wordcloud_figure(
    wc,
    *,
    figsize: tuple[float, float] = (10, 5),
    interpolation: str = "bilinear",
):
    """Return ``(fig, ax)`` with the wordcloud drawn as a raster.

    Uses ``Axes.imshow(wc.to_array())`` instead of ``pyplot.imshow(wc)`` so
    matplotlib does not run ``pyplot.sci()`` (which assumes the image is on
    ``gca()`` and can fail under concurrent pyplot use).
    """
    fig, ax = plt.subplots(figsize=figsize)
    ax.imshow(wc.to_array(), interpolation=interpolation)
    ax.axis("off")
    return fig, ax


def generate_wordcloud(
    text: str,
    output_structure,
    base_name: str,
    speaker: str,
    filename: str,
    chart_type: str = "basic",
    title: str = "Word Cloud",
    viz_id: str | None = None,
    *,
    output_service: Any | None = None,
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
    fig, ax = _wordcloud_figure(wc)
    chart_path = None
    view_speaker = None if speaker == "wordcloud-ALL" else speaker
    try:
        ax.set_title(title)
        fig.tight_layout()

        if speaker == "wordcloud-ALL":
            chart_path = save_global_chart(
                fig,
                output_structure,
                base_name,
                filename,
                dpi=300,
                chart_type=chart_type,
                title=title,
                viz_id=viz_id,
                frequencies=freq,
                output_service=output_service,
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
                title=title,
                viz_id=viz_id,
                frequencies=freq,
                output_service=output_service,
            )
    finally:
        plt.close(fig)

    payload = _build_terms_payload(
        dict(freq),
        variant="basic",
        variant_key="basic_unigram",
        speaker=view_speaker,
        ngram=1,
        metric="count",
        output_service=output_service,
    )
    terms_path = _save_terms_json(
        payload, filename=filename, speaker=view_speaker, output_service=output_service
    )
    _save_wordcloud_view(
        payload,
        title=title,
        filename=filename,
        speaker=view_speaker,
        source_terms_path=(
            _relative_to_transcript(terms_path, output_service) if terms_path else None
        ),
        thumbnail_path=(
            _relative_to_transcript(chart_path, output_service) if chart_path else None
        ),
        output_service=output_service,
    )
    notify_user(
        f"✅ Word cloud saved for {speaker}", technical=False, section="wordclouds"
    )

    return freq
