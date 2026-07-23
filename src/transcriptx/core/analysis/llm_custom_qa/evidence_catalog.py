"""Evidence pack catalog for llm_custom_qa (soft deps; per-module loaders)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from transcriptx.core.analysis.llm_custom_qa.versioning import EVIDENCE_CATALOG_VERSION

PackState = str  # missing|invalid|incompatible|empty|available|budget_omitted

CATALOG_PACK_IDS: tuple[str, ...] = (
    "interactions",
    "summary",
    "highlights",
    "llm_action_items",
    "topic_shift",
    "sentiment",
    "emotion",
    "moments",
    "insights",
)


@dataclass(frozen=True)
class PackSpec:
    pack_id: str
    title: str
    blurb: str
    module_name: str
    renderer_version: str
    supports_speaker_filter: bool


PACK_SPECS: dict[str, PackSpec] = {
    "interactions": PackSpec(
        "interactions",
        "Interactions",
        "Turn-taking and interaction summary",
        "interactions",
        "1",
        False,
    ),
    "summary": PackSpec(
        "summary", "Summary", "Meeting narrative/summary", "summary", "1", False
    ),
    "highlights": PackSpec(
        "highlights", "Highlights", "Sectioned highlight bullets", "highlights", "1", False
    ),
    "llm_action_items": PackSpec(
        "llm_action_items",
        "Action items",
        "LLM action items",
        "llm_action_items",
        "1",
        True,
    ),
    "topic_shift": PackSpec(
        "topic_shift",
        "Topic shifts",
        "Topic shift titles/summaries",
        "topic_shift",
        "1",
        False,
    ),
    "sentiment": PackSpec(
        "sentiment", "Sentiment", "Sentiment rollups", "sentiment", "1", True
    ),
    "emotion": PackSpec(
        "emotion", "Emotion", "Emotion assignment shares", "emotion", "1", True
    ),
    "moments": PackSpec(
        "moments", "Moments", "Top-ranked moments", "moments", "1", False
    ),
    "insights": PackSpec(
        "insights", "Insights", "Key themes / notable moments", "insights", "1", False
    ),
}


@dataclass(frozen=True)
class EvidenceSnapshot:
    pack_id: str
    state: PackState
    fingerprint: str
    payload_bytes: bytes
    schema_id: Optional[str]
    renderer_version: str
    supports_speaker_filter: bool


def expand_evidence_pack_ids(setting: Optional[list[str]]) -> tuple[str, ...]:
    """Expand null sentinel to full catalog; [] stays empty; filter unknown."""
    if setting is None:
        return CATALOG_PACK_IDS
    known = set(CATALOG_PACK_IDS)
    return tuple(sorted({p for p in setting if p in known}))


def _fingerprint_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _try_load_module_payload(
    *,
    pack_id: str,
    context: Any,
    run_root: Optional[Path],
) -> tuple[PackState, Optional[dict[str, Any]], Optional[str]]:
    """Load via context result first, then soft miss — never hard-fail."""
    spec = PACK_SPECS[pack_id]
    payload: Any = None
    schema_id: Optional[str] = None
    if context is not None and hasattr(context, "get_analysis_result"):
        try:
            payload = context.get_analysis_result(spec.module_name)
        except Exception:
            payload = None
    if payload is None and run_root is not None:
        # Soft disk probe: look for common JSON artifact names without claiming
        # custom-QA marker authority for foreign modules.
        try:
            matches = sorted(run_root.rglob(f"*_{spec.module_name}.json"))
            if matches:
                import json

                raw = matches[0].read_text(encoding="utf-8")
                payload = json.loads(raw)
        except Exception:
            payload = None
    if payload is None:
        return "missing", None, None
    if not isinstance(payload, dict):
        return "invalid", None, None
    if not payload:
        return "empty", {}, schema_id
    schema_id = str(payload.get("schema_id") or "") or None
    return "available", payload, schema_id


def load_evidence_snapshots(
    *,
    enabled_pack_ids: tuple[str, ...],
    context: Any = None,
    run_root: Optional[Path] = None,
) -> dict[str, EvidenceSnapshot]:
    """Load each pack once into immutable snapshots (canonical JSON bytes)."""
    import json

    out: dict[str, EvidenceSnapshot] = {}
    for pack_id in enabled_pack_ids:
        spec = PACK_SPECS[pack_id]
        state, payload, schema_id = _try_load_module_payload(
            pack_id=pack_id, context=context, run_root=run_root
        )
        if payload is None:
            payload_bytes = b""
        else:
            payload_bytes = json.dumps(
                payload, sort_keys=True, ensure_ascii=False, default=str
            ).encode("utf-8")
        out[pack_id] = EvidenceSnapshot(
            pack_id=pack_id,
            state=state,
            fingerprint=_fingerprint_bytes(payload_bytes) if payload_bytes else "",
            payload_bytes=payload_bytes,
            schema_id=schema_id,
            renderer_version=spec.renderer_version,
            supports_speaker_filter=spec.supports_speaker_filter,
        )
    return out


def render_pack_for_prompt(
    snapshot: EvidenceSnapshot,
    *,
    char_budget: int,
    speaker_key: Optional[str] = None,
) -> str:
    """Compact untrusted prompt text; never leak other speakers' utterances."""
    if snapshot.state != "available" or not snapshot.payload_bytes:
        return ""
    import json

    try:
        data = json.loads(snapshot.payload_bytes.decode("utf-8"))
    except Exception:
        return ""
    if speaker_key and snapshot.supports_speaker_filter:
        # Prefer speaker-keyed slices when present; else omit (empty).
        for key in ("by_speaker", "speakers", "speaker_summaries"):
            block = data.get(key)
            if isinstance(block, dict) and speaker_key in block:
                data = block[speaker_key]
                break
            if isinstance(block, list):
                matched = [
                    row
                    for row in block
                    if isinstance(row, dict)
                    and str(row.get("speaker_key") or row.get("speaker") or "")
                    == speaker_key
                ]
                if matched:
                    data = matched
                    break
        else:
            # No speaker slice — do not dump full multi-speaker payload
            return ""
    text = json.dumps(data, ensure_ascii=False, default=str)
    if len(text) > char_budget:
        return text[: max(0, char_budget - 1)] + "…"
    return text


def router_catalog_entries(
    snapshots: dict[str, EvidenceSnapshot],
) -> list[dict[str, Any]]:
    entries = []
    for pack_id, snap in snapshots.items():
        spec = PACK_SPECS[pack_id]
        entries.append(
            {
                "pack_id": pack_id,
                "title": spec.title,
                "blurb": spec.blurb,
                "available": snap.state == "available",
            }
        )
    return entries


def catalog_version() -> str:
    return EVIDENCE_CATALOG_VERSION
