from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


_ISO_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z")


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
