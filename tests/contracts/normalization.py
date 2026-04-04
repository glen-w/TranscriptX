from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

_ISO_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z")


ARTIFACT_FAMILIES: dict[str, dict[str, Any]] = {
    "report_user_report": {"module": None, "kind": "data_txt", "contains": "report"},
    "transcript_output": {
        "module": None,
        "kind": "transcript",
        "contains": "transcripts/",
    },
    "stats_data": {
        "kind_in": {"data_json", "data_csv", "data_txt"},
        "contains_any": ("stats", "report"),
    },
    "sentiment_chart": {
        "module": "sentiment",
        "kind_in": {"chart_static", "chart_dynamic"},
    },
    "wordcloud_chart": {
        "module": "wordclouds",
        "kind_in": {"chart_static", "chart_dynamic"},
    },
    "highlights_report": {"module": "highlights", "kind": "data_txt"},
    "ner_map_dynamic": {
        "module": "ner",
        "kind": "chart_dynamic",
        "contains": "maps/html/",
    },
    "ner_map_static": {
        "module": "ner",
        "kind": "chart_static",
        "contains": "maps/images/",
    },
    "group_aggregate_chart": {
        "module": "group",
        "kind_in": {"chart_static", "chart_dynamic"},
    },
}


def normalize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Normalize manifest content for stable snapshots."""
    normalized = json.loads(json.dumps(manifest))
    run_meta = normalized.get("run_metadata", {})
    if isinstance(run_meta, dict):
        run_meta.pop("timestamp", None)
        # Remove size to avoid file-system variance
        run_meta.pop("total_size_bytes", None)
        if "config_hash" in run_meta:
            run_meta["config_hash"] = "<hash>"
        version_hash = run_meta.get("version_hash")
        if isinstance(version_hash, dict):
            run_meta["version_hash"] = {k: "<hash>" for k in version_hash}

    artifacts = normalized.get("artifacts", [])
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if isinstance(artifact, dict):
                if "id" in artifact:
                    artifact["id"] = "<id>"
                artifact.pop("mtime", None)
                artifact.pop("bytes", None)
                produced_by = artifact.get("produced_by")
                if isinstance(produced_by, str) and "/" in produced_by:
                    module, _hash = produced_by.split("/", 1)
                    artifact["produced_by"] = f"{module}/<hash>"
        normalized["artifacts"] = sorted(
            artifacts,
            key=lambda item: (item.get("rel_path", ""), item.get("kind", "")),
        )

    return normalized


def normalize_golden_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Normalize manifest fields used by golden run contracts."""
    normalized = normalize_manifest(manifest)
    run_meta = normalized.get("run_metadata", {})
    if isinstance(run_meta, dict):
        run_meta.pop("audio_rel_path", None)
    artifacts = normalized.get("artifacts", [])
    if isinstance(artifacts, list):
        cleaned: list[dict[str, Any]] = []
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            row = {
                "rel_path": artifact.get("rel_path"),
                "module": artifact.get("module"),
                "kind": artifact.get("kind"),
                "tags": sorted(artifact.get("tags", [])),
                "scope": artifact.get("scope"),
                "speaker": artifact.get("speaker"),
            }
            cleaned.append(row)
        normalized["artifacts"] = sorted(
            cleaned,
            key=lambda item: (
                item.get("module") or "",
                item.get("kind") or "",
                item.get("rel_path") or "",
            ),
        )
    return normalized


def assert_rel_paths_match_pattern(
    manifest: dict[str, Any], pattern: str, module: str | None = None
) -> None:
    regex = re.compile(pattern)
    rows = manifest.get("artifacts", [])
    matched = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        if module is not None and row.get("module") != module:
            continue
        rel_path = str(row.get("rel_path", ""))
        if regex.search(rel_path):
            matched = True
            break
    assert matched, f"No artifact matched pattern={pattern!r}, module={module!r}"


def _artifact_matches_family(artifact: dict[str, Any], family: str) -> bool:
    rule = ARTIFACT_FAMILIES[family]
    module = rule.get("module")
    if module is not None and artifact.get("module") != module:
        return False
    module_in = rule.get("module_in")
    if module_in is not None and artifact.get("module") not in module_in:
        return False
    kind = rule.get("kind")
    if kind is not None and artifact.get("kind") != kind:
        return False
    kind_in = rule.get("kind_in")
    if kind_in is not None and artifact.get("kind") not in kind_in:
        return False
    contains = rule.get("contains")
    if contains is not None and contains not in str(artifact.get("rel_path", "")):
        return False
    contains_any = rule.get("contains_any")
    if contains_any is not None and not any(
        token in str(artifact.get("rel_path", "")) for token in contains_any
    ):
        return False
    return True


def assert_module_has_artifact_family(manifest: dict[str, Any], family: str) -> None:
    assert family in ARTIFACT_FAMILIES, f"Unknown artifact family: {family}"
    artifacts = manifest.get("artifacts", [])
    has_match = any(
        isinstance(row, dict) and _artifact_matches_family(row, family)
        for row in artifacts
    )
    assert has_match, f"Expected artifact family missing: {family}"


def assert_no_artifact_family_for_module(
    manifest: dict[str, Any], module: str, family: str
) -> None:
    assert family in ARTIFACT_FAMILIES, f"Unknown artifact family: {family}"
    artifacts = manifest.get("artifacts", [])
    leaked = [
        row
        for row in artifacts
        if isinstance(row, dict)
        and row.get("module") == module
        and _artifact_matches_family(row, family)
    ]
    assert not leaked, f"Unexpected artifacts for family={family}, module={module}"


def normalize_stats_txt(text: str) -> str:
    """Normalize stats text output by stripping timestamps and extra whitespace."""
    text = _ISO_TS_RE.sub("<timestamp>", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def normalize_csv(path: Path) -> dict[str, Any]:
    """Load CSV and normalize headers + rows for stable snapshot comparisons."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    if not rows:
        return {"headers": [], "rows": []}
    headers = rows[0]
    body = rows[1:]
    # Sort rows for deterministic comparisons when order is not meaningful.
    body_sorted = sorted(body, key=lambda row: [str(item) for item in row])
    return {"headers": headers, "rows": body_sorted}
