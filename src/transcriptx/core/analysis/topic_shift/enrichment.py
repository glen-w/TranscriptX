"""Optional LLM enrichment sidecar for topic_shift (boundaries immutable)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from transcriptx.core.analysis.llm_generational_store import (
    begin_generation,
    commit_and_activate,
    load_active_artifact,
)
from transcriptx.core.analysis.topic_shift.enrichment_resolve import (
    resolve_topic_shift_enrichment_model,
)
from transcriptx.core.analysis.topic_shift.store import content_digest
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.io import save_json

logger = get_logger()

ENRICHMENT_SCHEMA = "topic_shift_enrichment_schema_v1"
PROMPT_VERSION = "topic_shift_enrichment_prompt_v1"
STORE_DIRNAME = ".topic_shift_enrichment"
ARTIFACT_NAME = "topic_shift.enrichment.json"


def build_skipped_enrichment(
    *,
    deterministic_generation_id: str,
    deterministic_digest: str,
    skip_reason: str,
    spans: Sequence[Mapping[str, Any]],
    model: str | None = None,
    selection_source: str | None = None,
) -> dict[str, Any]:
    entries = []
    for span in spans:
        sid = str(span.get("span_id") or "")
        entries.append(
            {
                "span_id": sid,
                "title": None,
                "summary": None,
                "key_points": [],
                "title_source": "deterministic_fallback",
                "error_category": skip_reason,
            }
        )
    analytical = None
    ui_mode = "chapter_titles"
    return {
        "schema_version": ENRICHMENT_SCHEMA,
        "prompt_version": PROMPT_VERSION,
        "outcome": "skipped",
        "skip_reason": skip_reason,
        "deterministic_generation_id": deterministic_generation_id,
        "deterministic_digest": deterministic_digest,
        "model": model,
        "selection_source": selection_source,
        "entries": entries,
        "overall_summary": None,
        "ui_mode": ui_mode,
        "analytical_status_hint": analytical,
    }


def _ui_mode_for(spans_envelope: Mapping[str, Any], spans: Sequence[Mapping[str, Any]]) -> str:
    status = spans_envelope.get("analytical_status")
    if status == "no_shift_detected" and len(spans) == 1:
        return "overall_summary"
    return "chapter_titles"


def _try_generate_titles(
    *,
    model: str,
    spans: Sequence[Mapping[str, Any]],
    llm_cfg: Any,
) -> tuple[str, list[dict[str, Any]], str | None]:
    """
    Attempt structured titles. Returns (outcome, entries, overall_summary).

    Soft-fails to skipped/partial without raising into the deterministic path.
    """
    try:
        from transcriptx.core.llm.ollama_client import (
            OllamaClient,
            resolve_ollama_base_url,
        )
    except Exception as exc:  # pragma: no cover
        logger.info("topic_shift enrichment: OllamaClient unavailable: %s", exc)
        return "skipped", [], None

    # Build a compact prompt; never ask the model to move boundaries.
    lines = []
    for span in spans[:40]:
        label = str(span.get("label") or span.get("span_id") or "segment")
        hints = span.get("keyword_hints") or []
        hint_txt = ", ".join(str(h) for h in hints[:8])
        lines.append(
            f"<SPAN id={span.get('span_id')!s} label={label!s} hints={hint_txt!s}/>"
        )
    prompt = (
        "You label conversation chapters. Do NOT invent, move, merge, or remove "
        "boundaries. Return JSON only with keys: entries (list of "
        "{span_id, title, summary, key_points}), optional overall_summary.\n"
        "Spans:\n" + "\n".join(lines)
    )
    try:
        base = resolve_ollama_base_url(
            str(getattr(llm_cfg, "base_url", None) or "http://localhost:11434")
        )
        timeout = float(getattr(llm_cfg, "request_timeout", 120.0) or 120.0)
        client = OllamaClient(
            base_url=base,
            model=model,
            seed=int(getattr(llm_cfg, "seed", 42) or 42),
            request_timeout=min(timeout, 180.0),
            availability_timeout=float(
                getattr(llm_cfg, "availability_timeout", 7.5) or 7.5
            ),
            max_output_tokens=1024,
        )
        raw = client.generate(
            prompt=prompt,
            temperature=0.2,
            response_format="json",
            max_tokens=1024,
        )
    except Exception as exc:
        logger.info("topic_shift enrichment generate failed: %s", exc)
        return "skipped", [], None

    text = str(raw or "").strip()
    if not text:
        return "skipped", [], None
    # Best-effort JSON extract
    import json
    import re

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return "skipped", [], None
    try:
        parsed = json.loads(match.group(0))
    except ValueError:
        return "skipped", [], None
    if not isinstance(parsed, dict):
        return "skipped", [], None
    by_id = {
        str(e.get("span_id")): e
        for e in (parsed.get("entries") or [])
        if isinstance(e, dict) and e.get("span_id")
    }
    entries: list[dict[str, Any]] = []
    filled = 0
    for span in spans:
        sid = str(span.get("span_id") or "")
        hit = by_id.get(sid)
        if hit and str(hit.get("title") or "").strip():
            filled += 1
            entries.append(
                {
                    "span_id": sid,
                    "title": str(hit.get("title")).strip()[:120],
                    "summary": (
                        str(hit.get("summary")).strip()[:800]
                        if hit.get("summary")
                        else None
                    ),
                    "key_points": [
                        str(p).strip()[:200]
                        for p in (hit.get("key_points") or [])[:5]
                        if str(p).strip()
                    ],
                    "title_source": "llm",
                    "error_category": None,
                }
            )
        else:
            entries.append(
                {
                    "span_id": sid,
                    "title": None,
                    "summary": None,
                    "key_points": [],
                    "title_source": "deterministic_fallback",
                    "error_category": "missing_in_response",
                }
            )
    overall = parsed.get("overall_summary")
    overall_s = str(overall).strip()[:1200] if overall else None
    if filled == 0:
        return "skipped", entries, overall_s
    if filled < len(spans):
        return "partial", entries, overall_s
    return "success", entries, overall_s


def maybe_run_topic_shift_enrichment(
    *,
    module_output_dir: Path,
    spans_envelope: Mapping[str, Any],
    llm_cfg: Any | None = None,
    llm_enabled: bool | None = None,
) -> dict[str, Any]:
    """
    Run after deterministic ACTIVE exists. Never mutates boundaries.

    Failures are recorded as skipped/partial enrichment generations; they never
    invalidate deterministic ACTIVE.
    """
    spans = list(spans_envelope.get("coverage_spans") or [])
    det_gid = str(spans_envelope.get("deterministic_generation_id") or "")
    # Digest excludes volatile attempt stamps beyond the generation id binding.
    det_digest = content_digest(
        {
            "coverage_spans": spans,
            "analytical_status": spans_envelope.get("analytical_status"),
            "schema_version": spans_envelope.get("schema_version"),
            "semantics_version": spans_envelope.get("semantics_version"),
            "backend": spans_envelope.get("backend"),
        }
    )
    ui_mode = _ui_mode_for(spans_envelope, spans)

    if llm_cfg is None:
        try:
            llm_cfg = get_config().llm
        except Exception:
            llm_cfg = None
    if llm_enabled is None:
        llm_enabled = bool(getattr(llm_cfg, "enabled", False)) if llm_cfg else False

    if not spans:
        payload = build_skipped_enrichment(
            deterministic_generation_id=det_gid,
            deterministic_digest=det_digest,
            skip_reason="no_spans",
            spans=[],
        )
        payload["ui_mode"] = ui_mode
    elif not llm_enabled:
        payload = build_skipped_enrichment(
            deterministic_generation_id=det_gid,
            deterministic_digest=det_digest,
            skip_reason="llm_disabled",
            spans=spans,
        )
        payload["ui_mode"] = ui_mode
    else:
        resolved = resolve_topic_shift_enrichment_model(llm_cfg)
        if resolved.status != "ok" or not resolved.model:
            payload = build_skipped_enrichment(
                deterministic_generation_id=det_gid,
                deterministic_digest=det_digest,
                skip_reason=resolved.skip_reason or "no_model",
                spans=spans,
            )
            payload["ui_mode"] = ui_mode
        else:
            outcome, entries, overall = _try_generate_titles(
                model=resolved.model, spans=spans, llm_cfg=llm_cfg
            )
            if not entries:
                payload = build_skipped_enrichment(
                    deterministic_generation_id=det_gid,
                    deterministic_digest=det_digest,
                    skip_reason="generation_failed",
                    spans=spans,
                    model=resolved.model,
                    selection_source=resolved.source,
                )
                payload["ui_mode"] = ui_mode
            else:
                payload = {
                    "schema_version": ENRICHMENT_SCHEMA,
                    "prompt_version": PROMPT_VERSION,
                    "outcome": outcome,
                    "skip_reason": None if outcome != "skipped" else "generation_failed",
                    "deterministic_generation_id": det_gid,
                    "deterministic_digest": det_digest,
                    "model": resolved.model,
                    "selection_source": resolved.source,
                    "entries": entries,
                    "overall_summary": overall,
                    "ui_mode": ui_mode,
                }

    staged = begin_generation(
        Path(module_output_dir),
        store_dirname=STORE_DIRNAME,
        extra_meta={
            "deterministic_generation_id": det_gid,
            "deterministic_digest": det_digest,
        },
    )
    staged.write_json(ARTIFACT_NAME, payload)
    commit_and_activate(
        staged,
        rel_paths=[ARTIFACT_NAME],
        status=str(payload.get("outcome") or "skipped"),
    )

    data_global = Path(module_output_dir) / "data" / "global"
    data_global.mkdir(parents=True, exist_ok=True)
    save_json(payload, str(data_global / ARTIFACT_NAME))
    return payload


def load_active_enrichment(module_output_dir: Path) -> dict[str, Any] | None:
    store = Path(module_output_dir) / STORE_DIRNAME
    raw = load_active_artifact(store, ARTIFACT_NAME)
    return raw if isinstance(raw, dict) else None
