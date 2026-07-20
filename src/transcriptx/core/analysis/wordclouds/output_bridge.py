"""
Active output service and chart/data save helpers for wordcloud analysis.

The module-level ``_ACTIVE_OUTPUT_SERVICE`` is set by ``use_output_service`` and by
legacy paths such as ``run_all_wordclouds``. It is not only used for saving charts:
``_runtime_flags`` on the service also supplies **ignored_speaker_ids** and
**speaker_key_aliases**, which affect eligibility and speaker key resolution in
analysis helpers (see ``_get_ignored_ids`` / ``_resolve_speaker_key``).

Leaf functions accept an optional ``output_service`` argument. When provided, that
instance is used; when ``None``, behavior falls back to ``_ACTIVE_OUTPUT_SERVICE``
so existing callers and tests keep working while explicit threading is introduced
incrementally.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping

from transcriptx.core.analysis.chart_descriptions.schemas import MAX_EVIDENCE_LABELS
from transcriptx.core.utils.config import get_config
from transcriptx.core.viz.specs import PreRenderedFigureSpec
from transcriptx.utils.text_utils import is_eligible_named_speaker

_ACTIVE_OUTPUT_SERVICE = None


def _active_output_service(output_service: Any | None) -> Any | None:
    return output_service if output_service is not None else _ACTIVE_OUTPUT_SERVICE


def _get_ignored_ids(output_service: Any | None = None) -> set[str]:
    svc = _active_output_service(output_service)
    if not svc:
        return set()
    ignored = svc._runtime_flags.get("ignored_speaker_ids")
    return ignored if isinstance(ignored, set) else set()


def _resolve_speaker_key(speaker: str, output_service: Any | None = None) -> str:
    svc = _active_output_service(output_service)
    if not svc:
        return speaker
    aliases = svc._runtime_flags.get("speaker_key_aliases", {})
    if isinstance(aliases, dict):
        return aliases.get(str(speaker), str(speaker))
    return str(speaker)


def _include_speaker_wordcloud(
    speaker: str | None, output_service: Any | None = None
) -> bool:
    """Return False when per-speaker wordclouds should skip unidentified labels."""
    if not speaker or speaker in {"ALL", "wordcloud-ALL"}:
        return True
    svc = _active_output_service(output_service)
    if svc and svc._runtime_flags.get("include_unidentified_speakers"):
        return True
    config = get_config()
    exclude = getattr(
        getattr(config, "analysis", None),
        "exclude_unidentified_from_speaker_charts",
        True,
    )
    if not exclude:
        return True
    return is_eligible_named_speaker(
        speaker,
        _resolve_speaker_key(speaker, output_service),
        _get_ignored_ids(output_service),
    )


@contextmanager
def use_output_service(service):
    global _ACTIVE_OUTPUT_SERVICE
    previous = _ACTIVE_OUTPUT_SERVICE
    _ACTIVE_OUTPUT_SERVICE = service
    try:
        yield
    finally:
        _ACTIVE_OUTPUT_SERVICE = previous


def _top_terms_evidence(
    frequencies: Mapping[str, Any] | None,
    *,
    limit: int = MAX_EVIDENCE_LABELS,
) -> tuple[list[str], list[float]]:
    if not frequencies:
        return [], []
    ranked = sorted(
        ((str(term), float(weight)) for term, weight in frequencies.items()),
        key=lambda item: (-item[1], item[0]),
    )[:limit]
    return [term for term, _ in ranked], [weight for _, weight in ranked]


def _wordcloud_chart_spec(
    fig,
    *,
    filename: str,
    scope: str,
    speaker: str | None,
    title: str | None,
    viz_id: str | None,
    frequencies: Mapping[str, Any] | None,
    module: str,
) -> PreRenderedFigureSpec:
    labels, values = _top_terms_evidence(frequencies)
    final_viz_id = viz_id or f"{module}.{filename}.{scope}"
    return PreRenderedFigureSpec(
        viz_id=final_viz_id,
        module=module,
        name=filename,
        scope=scope,  # type: ignore[arg-type]
        chart_intent="pre_rendered",
        title=title or filename,
        speaker=speaker,
        figure=fig,
        labels=labels,
        values=values,
        transformations=["source:wordcloud_frequencies"] if labels else (),
        notes="Wordcloud raster; top terms listed in evidence labels/values.",
    )


def _save_chart_global(
    fig,
    filename,
    dpi=300,
    chart_type=None,
    title=None,
    viz_id=None,
    *,
    frequencies: Mapping[str, Any] | None = None,
    output_service: Any | None = None,
):
    svc = _active_output_service(output_service)
    if not svc:
        return None
    module = getattr(svc, "module_name", None) or "wordclouds"
    spec = _wordcloud_chart_spec(
        fig,
        filename=filename,
        scope="global",
        speaker=None,
        title=title,
        viz_id=viz_id,
        frequencies=frequencies,
        module=module,
    )
    result = svc.save_chart(spec, dpi=dpi, chart_type=chart_type)
    return result.get("static")


def _save_chart_speaker(
    fig,
    speaker,
    filename,
    dpi=300,
    chart_type=None,
    title=None,
    viz_id=None,
    *,
    frequencies: Mapping[str, Any] | None = None,
    output_service: Any | None = None,
):
    svc = _active_output_service(output_service)
    if not svc:
        return None
    module = getattr(svc, "module_name", None) or "wordclouds"
    spec = _wordcloud_chart_spec(
        fig,
        filename=filename,
        scope="speaker",
        speaker=speaker,
        title=title,
        viz_id=viz_id,
        frequencies=frequencies,
        module=module,
    )
    result = svc.save_chart(spec, dpi=dpi, chart_type=chart_type)
    return result.get("static")


def save_global_chart(
    fig,
    output_structure,
    base_name,
    filename,
    dpi=300,
    chart_type=None,
    title=None,
    viz_id=None,
    *,
    frequencies: Mapping[str, Any] | None = None,
    output_service: Any | None = None,
):
    return _save_chart_global(
        fig,
        filename,
        dpi=dpi,
        chart_type=chart_type,
        title=title,
        viz_id=viz_id,
        frequencies=frequencies,
        output_service=output_service,
    )


def save_speaker_chart(
    fig,
    output_structure,
    base_name,
    speaker,
    filename,
    dpi=300,
    chart_type=None,
    title=None,
    viz_id=None,
    *,
    frequencies: Mapping[str, Any] | None = None,
    output_service: Any | None = None,
):
    return _save_chart_speaker(
        fig,
        speaker,
        filename,
        dpi=dpi,
        chart_type=chart_type,
        title=title,
        viz_id=viz_id,
        frequencies=frequencies,
        output_service=output_service,
    )


def _get_dynamic_views_mode() -> str:
    config = get_config()
    return getattr(config.output, "dynamic_views", "auto")


def _should_generate_views() -> bool:
    """Return whether to emit wordcloud explorer HTML.

    Only ``dynamic_views='off'`` skips generation. ``auto`` and ``on`` are
    treated the same (both enabled) until a distinct policy is needed; the
    explorer is self-contained in the browser and does not depend on optional
    Python chart libraries.
    """
    mode = _get_dynamic_views_mode()
    if mode == "off":
        return False
    return True


def _relative_to_transcript(path: str | Path, output_service: Any | None = None) -> str:
    svc = _active_output_service(output_service)
    if not svc:
        return str(path)
    path_obj = Path(path)
    try:
        return path_obj.relative_to(Path(svc.transcript_dir)).as_posix()
    except ValueError:
        return path_obj.as_posix()
