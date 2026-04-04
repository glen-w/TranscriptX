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
from typing import Any

from transcriptx.core.utils.config import get_config

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


@contextmanager
def use_output_service(service):
    global _ACTIVE_OUTPUT_SERVICE
    previous = _ACTIVE_OUTPUT_SERVICE
    _ACTIVE_OUTPUT_SERVICE = service
    try:
        yield
    finally:
        _ACTIVE_OUTPUT_SERVICE = previous


def _save_chart_global(
    fig,
    filename,
    dpi=300,
    chart_type=None,
    title=None,
    viz_id=None,
    *,
    output_service: Any | None = None,
):
    svc = _active_output_service(output_service)
    if not svc:
        return None
    result = svc.save_chart(
        chart_id=filename,
        scope="global",
        static_fig=fig,
        dpi=dpi,
        chart_type=chart_type,
        title=title,
        viz_id=viz_id,
    )
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
    output_service: Any | None = None,
):
    svc = _active_output_service(output_service)
    if not svc:
        return None
    result = svc.save_chart(
        chart_id=filename,
        scope="speaker",
        speaker=speaker,
        static_fig=fig,
        dpi=dpi,
        chart_type=chart_type,
        title=title,
        viz_id=viz_id,
    )
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
    output_service: Any | None = None,
):
    return _save_chart_global(
        fig,
        filename,
        dpi=dpi,
        chart_type=chart_type,
        title=title,
        viz_id=viz_id,
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
