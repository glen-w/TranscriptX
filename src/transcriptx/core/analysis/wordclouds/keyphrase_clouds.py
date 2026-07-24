"""Emit keyphrase wordcloud variants from validated upstream keyphrases rows."""

from __future__ import annotations

from typing import Any

from transcriptx.core.analysis.keyphrases.contract import SCHEMA_ID, SEMANTICS_VERSION
from transcriptx.core.analysis.wordclouds.models import WordcloudTerm, WordcloudTerms
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
from transcriptx.core.analysis.wordclouds.terms_io import _save_terms_json
from transcriptx.core.utils.lazy_imports import lazy_pyplot

plt = lazy_pyplot()

METHOD_VARIANT_KEYS = {
    "noun_chunks": "keyphrase_noun_chunks",
    "yake": "keyphrase_yake",
    "keybert": "keyphrase_keybert",
}


def _validate_upstream(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_id") not in (None, SCHEMA_ID):
        return None
    if payload.get("semantics_version") not in (None, SEMANTICS_VERSION):
        return None
    return payload


def _build_keyphrase_terms_payload(
    freq: dict[str, float],
    token_counts: dict[str, int],
    *,
    method: str,
    variant_key: str,
    speaker: str | None,
    upstream_schema_id: str,
    upstream_semantics_version: str,
) -> dict[str, Any]:
    sorted_items = sorted(freq.items(), key=lambda item: (-item[1], item[0]))
    terms = [
        WordcloudTerm(
            term=term,
            value=float(value),
            rank=idx + 1,
            kind="keyphrase",
            token_count=token_counts.get(term),
        )
        for idx, (term, value) in enumerate(sorted_items)
    ]
    payload = WordcloudTerms(
        source="wordclouds",
        variant=f"keyphrases_{method}",
        variant_key=variant_key,
        speaker=speaker,
        ngram=None,
        metric="rank_weight",
        terms=terms,
        method=method,
        upstream_schema_id=upstream_schema_id,
        upstream_semantics_version=upstream_semantics_version,
    )
    return payload.to_dict()


def _render_keyphrase_cloud(
    freq: dict[str, float],
    *,
    title: str,
    filename: str,
    viz_id: str,
    speaker: str | None,
    method: str,
    variant_key: str,
    token_counts: dict[str, int],
    upstream_schema_id: str,
    upstream_semantics_version: str,
    output_structure: Any,
    base_name: str,
) -> str | None:
    if not freq:
        return None
    try:
        WordCloud = _get_wordcloud_class()
    except Exception:
        return None
    wc = WordCloud(
        width=800, height=400, background_color="white"
    ).generate_from_frequencies(freq)
    fig, ax = _wordcloud_figure(wc)
    try:
        ax.set_title(title)
        fig.tight_layout()
        if speaker:
            chart_path = save_speaker_chart(
                fig,
                output_structure,
                base_name,
                speaker,
                filename,
                dpi=300,
                chart_type="keyphrases",
                title=title,
                viz_id=viz_id,
                frequencies=freq,
            )
        else:
            chart_path = save_global_chart(
                fig,
                output_structure,
                base_name,
                filename,
                dpi=300,
                chart_type="keyphrases",
                title=title,
                viz_id=viz_id,
                frequencies=freq,
            )
    finally:
        plt.close(fig)

    payload = _build_keyphrase_terms_payload(
        freq,
        token_counts,
        method=method,
        variant_key=variant_key,
        speaker=speaker,
        upstream_schema_id=upstream_schema_id,
        upstream_semantics_version=upstream_semantics_version,
    )
    terms_path = _save_terms_json(
        payload,
        filename=filename.replace(" ", "_"),
        speaker=speaker,
    )
    _save_wordcloud_view(
        payload,
        title=title,
        filename=filename.replace(" ", "_"),
        speaker=speaker,
        source_terms_path=_relative_to_transcript(terms_path) if terms_path else None,
        thumbnail_path=_relative_to_transcript(chart_path) if chart_path else None,
    )
    return chart_path


def emit_keyphrase_wordclouds(
    keyphrases_payload: dict[str, Any] | None,
    *,
    output_structure: Any,
    base_name: str,
) -> list[dict[str, Any]]:
    """Emit global/per-speaker keyphrase clouds. Returns skipped_variants entries."""
    skipped: list[dict[str, Any]] = []
    payload = _validate_upstream(keyphrases_payload)
    if payload is None:
        for method, variant_key in METHOD_VARIANT_KEYS.items():
            skipped.append(
                {
                    "variant_key": variant_key,
                    "reason": "upstream_missing_or_stale_schema",
                }
            )
        return skipped

    schema_id = str(payload.get("schema_id") or SCHEMA_ID)
    semantics = str(payload.get("semantics_version") or SEMANTICS_VERSION)
    gbm = payload.get("global_by_method") or {}
    sbm = payload.get("speakers_by_method") or {}
    if not isinstance(gbm, dict):
        gbm = {}
    if not isinstance(sbm, dict):
        sbm = {}

    for method, variant_key in METHOD_VARIANT_KEYS.items():
        block = gbm.get(method)
        if not isinstance(block, dict):
            skipped_methods = {
                str(s.get("method"))
                for s in (payload.get("skipped_methods") or [])
                if isinstance(s, dict)
            }
            methods_run = {str(m) for m in (payload.get("methods_run") or [])}
            if method in methods_run:
                skipped.append(
                    {
                        "variant_key": variant_key,
                        "reason": "malformed_upstream_rows",
                    }
                )
            elif method in skipped_methods or method not in methods_run:
                skipped.append(
                    {
                        "variant_key": variant_key,
                        "reason": "upstream_method_absent_or_skipped",
                    }
                )
            continue
        phrases = block.get("phrases") or []
        if not isinstance(phrases, list):
            skipped.append(
                {"variant_key": variant_key, "reason": "malformed_upstream_rows"}
            )
            continue
        freq_pair = _freq_from_phrases(phrases)
        freq, token_counts = freq_pair[0], freq_pair[1]
        if not freq:
            skipped.append(
                {"variant_key": variant_key, "reason": "no_positive_rank_weights"}
            )
            continue
        scope = "global"
        viz_id = f"wordcloud.wordcloud.{scope}.keyphrases_{method}"
        _render_keyphrase_cloud(
            freq,
            title=f"Keyphrases ({method}) — All Speakers",
            filename=f"wordcloud-keyphrases-{method}-ALL",
            viz_id=viz_id,
            speaker=None,
            method=method,
            variant_key=variant_key,
            token_counts=token_counts,
            upstream_schema_id=schema_id,
            upstream_semantics_version=semantics,
            output_structure=output_structure,
            base_name=base_name,
        )

        by_speaker = sbm.get(method) if isinstance(sbm, dict) else None
        if not isinstance(by_speaker, dict):
            continue
        for speaker, sp_block in sorted(by_speaker.items()):
            if not _include_speaker_wordcloud(speaker):
                continue
            if not isinstance(sp_block, dict):
                continue
            sp_phrases = sp_block.get("phrases") or []
            if not isinstance(sp_phrases, list):
                continue
            sp_pair = _freq_from_phrases(sp_phrases)
            sp_freq, sp_tokens = sp_pair[0], sp_pair[1]
            if not sp_freq:
                continue
            viz_id_sp = f"wordcloud.wordcloud.speaker.keyphrases_{method}"
            _render_keyphrase_cloud(
                sp_freq,
                title=f"Keyphrases ({method}) — {speaker}",
                filename=f"wordcloud-keyphrases-{method}",
                viz_id=viz_id_sp,
                speaker=speaker,
                method=method,
                variant_key=variant_key,
                token_counts=sp_tokens,
                upstream_schema_id=schema_id,
                upstream_semantics_version=semantics,
                output_structure=output_structure,
                base_name=base_name,
            )

    return skipped


def _freq_from_phrases(
    phrases: list[Any],
) -> tuple[dict[str, float], dict[str, int]]:
    freq: dict[str, float] = {}
    token_counts: dict[str, int] = {}
    for row in phrases:
        if not isinstance(row, dict):
            continue
        phrase = str(row.get("phrase") or "").strip()
        weight = float(row.get("rank_weight") or 0.0)
        if not phrase or weight <= 0:
            continue
        freq[phrase] = weight
        token_counts[phrase] = int(row.get("token_count") or len(phrase.split()) or 1)
    return freq, token_counts
