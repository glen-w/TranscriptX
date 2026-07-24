"""Resolve summary inputs for export index pages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Sequence

from transcriptx.export.summary_bodies import (
    strip_summary_markdown,
    summary_text_from_payload,
)
from transcriptx.export.types import ExportTextSummary

_SUMMARY_JSON_SUFFIX = ".json"
_SUMMARY_MD_SUFFIX = ".md"
_SUMMARY_KIND_ORDER = {
    "executive": 0,
    "llm_summary": 1,
    "narrative_summary": 2,
    "llm_speaker_summary": 3,
    "llm_action_items": 4,
    "llm_custom_qa": 5,
    "run_report": 6,
}


def _summary_kind_from_rel_path(
    rel_posix: str,
    *,
    module: Optional[str],
) -> Optional[str]:
    name = Path(rel_posix).name.lower()
    if name == "report.md":
        return "run_report"
    if name.endswith("_llm_summary.json") or name.endswith("_llm_summary.md"):
        return "llm_summary"
    if name.endswith("_narrative_summary.json") or name.endswith(
        "_narrative_summary.md"
    ):
        return "narrative_summary"
    if name.endswith("_llm_speaker_summary.json") or name.endswith(
        "_llm_speaker_summary.md"
    ):
        return "llm_speaker_summary"
    if name.endswith("_llm_action_items.json") or name.endswith("_llm_action_items.md"):
        return "llm_action_items"
    if name.endswith("_llm_custom_qa.json") or name.endswith("_llm_custom_qa.md"):
        return "llm_custom_qa"
    if (
        module == "summary"
        and (name.endswith("_summary.json") or name.endswith("_summary.md"))
        and "_llm_" not in name
        and "_narrative_" not in name
        and "_simplified_transcript_" not in name
    ):
        return "executive"
    return None


def _default_summary_title(kind: str, *, rel_posix: str) -> str:
    if kind == "executive":
        return "Executive Summary"
    if kind == "llm_summary":
        return "LLM Transcript Summary"
    if kind == "narrative_summary":
        return "Narrative Summary"
    if kind == "run_report":
        return "Run Report"
    if kind == "llm_speaker_summary":
        stem = Path(rel_posix).stem
        marker = "_llm_speaker_summary"
        if stem.endswith(marker):
            speaker_token = stem[: -len(marker)].rsplit("_", 1)[-1]
            if speaker_token:
                return f"Speaker Summary — {speaker_token.replace('_', ' ')}"
        return "Speaker Summary"
    if kind == "llm_action_items":
        return "Meeting extracts"
    if kind == "llm_custom_qa":
        return "Custom Questions"
    return "Summary"


def _summary_section_id(kind: str, rel_posix: str) -> str:
    stem = Path(rel_posix).stem.replace("_", "-")
    return f"summary-{kind}-{stem}"


def _load_summary_body(
    *,
    json_path: Optional[Path],
    md_path: Optional[Path],
    kind: str,
    staging_dir: Optional[Path] = None,
) -> tuple[str, dict[str, Any]]:
    payload: Optional[dict[str, Any]] = None
    if kind == "llm_custom_qa" and staging_dir is not None:
        # Prefer authoritative committed loader over bare alias bytes.
        try:
            from transcriptx.core.analysis.llm_custom_qa.readers import (
                load_committed_custom_qa_payload,
            )

            payload = load_committed_custom_qa_payload(Path(staging_dir))
        except Exception:
            payload = None
    if payload is None and json_path is not None and json_path.is_file():
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                payload = raw
        except Exception:
            payload = None

    body = ""
    if payload:
        if kind == "llm_custom_qa":
            schema_id = str(payload.get("schema_id") or "")
            from transcriptx.core.analysis.llm_custom_qa.versioning import (
                SCHEMA_ID,
            )

            if schema_id and schema_id != SCHEMA_ID:
                return "", {}
            if "question_order" in payload:
                try:
                    from transcriptx.core.analysis.llm_custom_qa.structured_contracts import (
                        validate_structured_artifact,
                    )

                    payload = validate_structured_artifact(payload)
                except Exception:
                    return "", {}
        body = summary_text_from_payload(payload, kind=kind)
    if not body and md_path is not None and md_path.is_file():
        try:
            body = strip_summary_markdown(md_path.read_text(encoding="utf-8"))
        except Exception:
            body = ""

    provenance = payload.get("provenance") if isinstance(payload, dict) else {}
    if kind == "llm_speaker_summary" and isinstance(payload, dict):
        speaker = payload.get("speaker")
        if speaker:
            provenance = {**provenance, "speaker": speaker}
    return body, provenance if isinstance(provenance, dict) else {}


def resolve_export_text_summaries(
    *,
    staging_dir: Path,
    copied: Sequence[tuple[Any, Path]],
) -> list[ExportTextSummary]:
    """Load prose summaries from copied export artifacts for the index page."""
    grouped: dict[str, dict[str, Any]] = {}

    for artifact, rel in copied:
        rel_posix = rel.as_posix()
        module = getattr(artifact, "module", None)
        kind = _summary_kind_from_rel_path(rel_posix, module=module)
        if kind is None:
            continue
        if kind == "llm_speaker_summary" and rel_posix.endswith(
            "_llm_speaker_summary_index.json"
        ):
            continue

        stem = Path(rel_posix).stem
        group_key = f"{kind}|{stem}"
        entry = grouped.setdefault(
            group_key,
            {
                "kind": kind,
                "rel_posix": rel_posix,
                "title": getattr(artifact, "title", None),
                "json_path": None,
                "md_path": None,
            },
        )
        path = staging_dir / rel
        if rel_posix.endswith(_SUMMARY_JSON_SUFFIX):
            entry["json_path"] = path
        elif rel_posix.endswith(_SUMMARY_MD_SUFFIX):
            entry["md_path"] = path

    summaries: list[ExportTextSummary] = []
    ordered = sorted(
        grouped.values(),
        key=lambda item: (
            _SUMMARY_KIND_ORDER.get(str(item["kind"]), 99),
            str(item["rel_posix"]),
        ),
    )
    for entry in ordered:
        kind = str(entry["kind"])
        rel_posix = str(entry["rel_posix"])
        body, provenance = _load_summary_body(
            json_path=entry.get("json_path"),
            md_path=entry.get("md_path"),
            kind=kind,
            staging_dir=staging_dir if kind == "llm_custom_qa" else None,
        )
        if not body:
            continue
        title = str(entry.get("title") or "").strip()
        if not title:
            title = _default_summary_title(kind, rel_posix=rel_posix)
        if kind == "llm_speaker_summary":
            speaker = provenance.get("speaker")
            if speaker:
                title = f"Speaker Summary — {speaker}"
        summaries.append(
            ExportTextSummary(
                section_id=_summary_section_id(kind, rel_posix),
                title=title,
                body=body,
                provenance=provenance,
            )
        )
    return summaries


def resolve_export_llm_summary(
    *,
    staging_dir: Path,
    copied: Sequence[tuple[Any, Path]],
) -> Optional[ExportTextSummary]:
    """Backward-compatible helper returning the first LLM transcript summary."""
    from transcriptx.core.analysis.group_llm_synthesis.resolve import (
        ResolverCache,
        is_group_run,
        load_group_llm_summary,
        load_text_under_generation,
    )
    from transcriptx.core.analysis.group_llm_synthesis.paths import (
        global_summary_md_rel,
    )

    if is_group_run(staging_dir):
        cache = ResolverCache()
        payload = load_group_llm_summary(staging_dir, cache=cache)
        if payload and str(payload.get("summary") or "").strip():
            md = load_text_under_generation(
                staging_dir, global_summary_md_rel(), cache=cache
            )
            body = strip_summary_markdown(md) if md else str(payload["summary"])
            prov = payload.get("provenance")
            return ExportTextSummary(
                section_id="group-llm-summary",
                title="Cross-session LLM Summary",
                body=body,
                provenance=prov if isinstance(prov, dict) else {},
            )

    for summary in resolve_export_text_summaries(
        staging_dir=staging_dir, copied=copied
    ):
        if summary.get("title") == "LLM Transcript Summary":
            return summary
    return None
