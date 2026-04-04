"""Generation manifest hashing (SSoT for staleness)."""

from __future__ import annotations

import hashlib
import json

from transcriptx.services.corrections_studio.schema import GenerationManifest


def compute_generation_manifest_hash(manifest: GenerationManifest) -> str:
    """Deterministic sha256 hex of canonical manifest JSON."""
    payload = manifest.model_dump(mode="json", exclude_none=True)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
