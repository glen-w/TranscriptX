"""
Compact provenance helpers for Markdown outputs.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


def _dedupe(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    output: List[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def build_md_provenance(
    module_name: str,
    *,
    context: Any | None = None,
    payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    provenance: Dict[str, Any] = {
        "module": module_name,
        "used": [],
        "missing": [],
        "input_source": None,
        "segments": None,
        "speakers": None,
    }

    if payload:
        inputs = payload.get("inputs") or {}
        for key, label in (
            ("used_highlights", "highlights"),
            ("used_sentiment", "sentiment"),
            ("used_emotion", "emotion"),
        ):
            if key in inputs:
                if inputs.get(key):
                    provenance["used"].append(label)
                else:
                    provenance["missing"].append(label)

        payload_prov = payload.get("provenance") or {}
        if payload_prov:
            provenance["input_source"] = payload_prov.get("input_source")
            provenance["segments"] = payload_prov.get("segment_count")
            speakers_named = payload_prov.get("speaker_count_named")
            speakers_total = payload_prov.get("speaker_count_total")
            if speakers_named is not None and speakers_total is not None:
                provenance["speakers"] = f"{speakers_named}/{speakers_total}"

        modules = payload.get("modules") or {}
        if modules:
            for module_id, info in modules.items():
                status = str(info.get("status", "missing_input"))
                if status == "ok":
                    provenance["used"].append(module_id)
                else:
                    provenance["missing"].append(module_id)

    if context and not payload:
        for module_id, label in (("sentiment", "sentiment"), ("emotion", "emotion")):
            if context.get_analysis_result(module_id):
                provenance["used"].append(label)
            else:
                provenance["missing"].append(label)

    provenance["used"] = _dedupe(provenance.get("used", []))
    provenance["missing"] = _dedupe(provenance.get("missing", []))
    return provenance


def render_provenance_footer_md(prov: Dict[str, Any]) -> str:
    lines = ["---", "Provenance"]
    if prov.get("input_source"):
        lines.append(f"- Input: {prov['input_source']}")
    if prov.get("segments") is not None:
        segments = prov.get("segments")
        speakers = prov.get("speakers")
        if speakers:
            lines.append(f"- Segments: {segments} | Speakers: {speakers}")
        else:
            lines.append(f"- Segments: {segments}")
    used = prov.get("used") or []
    if used:
        lines.append(f"- Used: {', '.join(used)}")
    missing = prov.get("missing") or []
    if missing:
        lines.append(f"- Missing: {', '.join(missing)}")
    lines.append("")
    return "\n".join(lines)
