"""Safe readers for llm_custom_qa analytical artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from transcriptx.core.analysis.llm_custom_qa.commit import (
    analytical_artifacts_readable,
    read_active_generation_id,
)
from transcriptx.core.analysis.llm_custom_qa.constants import MODULE_NAME
from transcriptx.core.analysis.llm_custom_qa.versioning import (
    COMMIT_MARKER_SCHEMA_VERSION,
    SCHEMA_ID,
)


def _module_succeeded(run_root: Path) -> bool:
    results_path = run_root / "run_results.json"
    if not results_path.exists():
        return False
    try:
        data = json.loads(results_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    modules_run = [str(x) for x in (data.get("modules_run") or []) if x]
    modules_failed = [str(x) for x in (data.get("modules_failed") or []) if x]
    if MODULE_NAME in modules_failed:
        return False
    if MODULE_NAME in modules_run:
        return True
    modules = data.get("modules") or data.get("module_results") or []
    if isinstance(modules, dict):
        row = modules.get(MODULE_NAME) or {}
        return str(row.get("status") or "").lower() == "success"
    if isinstance(modules, list):
        for row in modules:
            if not isinstance(row, dict):
                continue
            name = row.get("module") or row.get("module_name")
            if name == MODULE_NAME:
                return str(row.get("status") or "").lower() == "success"
    return False


def resolve_custom_qa_stem(
    run_root: Path,
    *,
    base_name: Optional[str] = None,
    module_result: Optional[dict[str, Any]] = None,
) -> Optional[Path]:
    """Canonical stem locator — no rglob authority.

    Prefers module_result artifact path, then module-scoped
    ``llm_custom_qa/data/global/{base}_llm_custom_qa``, then legacy
    ``data/global/`` layouts.
    """
    run_root = Path(run_root)
    if module_result:
        for key in ("artifact_path", "json_path", "output_path"):
            raw = module_result.get(key)
            if raw:
                p = Path(raw)
                name = p.name
                # Generation-named: {stem}.json.{gid}
                if f"_{MODULE_NAME}.json." in name:
                    stem_name = name.split(".json.", 1)[0]
                    return p.parent / stem_name
                if p.suffix == ".json":
                    return p.with_suffix("")
                return p
        artifacts = module_result.get("artifacts") or []
        for art in artifacts:
            if not isinstance(art, dict):
                continue
            path = art.get("path") or art.get("file")
            if not path:
                continue
            p = Path(path)
            name = p.name
            if f"_{MODULE_NAME}.json." in name:
                stem_name = name.split(".json.", 1)[0]
                return p.parent / stem_name
            if name.endswith(f"_{MODULE_NAME}.json"):
                return p.with_suffix("")

    candidate_dirs = (
        run_root / MODULE_NAME / "data" / "global",
        run_root / "data" / "global",
        run_root,
    )
    if base_name:
        for directory in candidate_dirs:
            candidate = directory / f"{base_name}_{MODULE_NAME}"
            if (
                Path(f"{candidate}.active").exists()
                or Path(f"{candidate}.json").exists()
                or any(directory.glob(f"{base_name}_{MODULE_NAME}.json.*"))
            ):
                return candidate

    for directory in candidate_dirs:
        if not directory.is_dir():
            continue
        # Prefer alias finals; else a single generation-named JSON.
        aliases = sorted(directory.glob(f"*_{MODULE_NAME}.json"))
        if len(aliases) == 1:
            return aliases[0].with_suffix("")
        gens = sorted(
            p
            for p in directory.glob(f"*_{MODULE_NAME}.json.*")
            if ".staging." not in p.name
        )
        stems = {p.name.split(".json.", 1)[0] for p in gens}
        if len(stems) == 1:
            return directory / next(iter(stems))
    return None


def find_committed_custom_qa_artifact(run_root: Path) -> Optional[Path]:
    """Return the committed JSON alias path when readable, else None."""
    if not _module_succeeded(Path(run_root)):
        return None
    stem = resolve_custom_qa_stem(Path(run_root))
    if stem is None:
        return None
    if not analytical_artifacts_readable(stem=stem, module_succeeded=True):
        return None
    alias = Path(f"{stem}.json")
    return alias if alias.exists() else None


def load_committed_custom_qa_payload(
    run_root: Path,
    *,
    base_name: Optional[str] = None,
    module_result: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """Load via active→marker validation; dispatch validators by artifact schema_id."""
    if not _module_succeeded(Path(run_root)):
        return None
    stem = resolve_custom_qa_stem(
        Path(run_root), base_name=base_name, module_result=module_result
    )
    if stem is None:
        return None
    gid = read_active_generation_id(stem)
    if gid is None:
        return None
    if not analytical_artifacts_readable(stem=stem, module_succeeded=True):
        return None

    # Prefer generation-named file when present; else bare alias.
    gen_json = Path(f"{stem}.json.{gid}")
    alias_json = Path(f"{stem}.json")
    path = gen_json if gen_json.exists() else alias_json
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None

    schema_id = str(data.get("schema_id") or "")
    if schema_id and schema_id != SCHEMA_ID:
        return None
    # Structured artifacts require question_order validation.
    if "question_order" in data:
        try:
            from transcriptx.core.analysis.llm_custom_qa.structured_contracts import (
                validate_structured_artifact,
            )

            return validate_structured_artifact(data)
        except Exception:
            return None
    return data


def marker_schema_version(stem: Path, generation_id: str) -> str:
    marker = Path(f"{stem}.commit.{generation_id}")
    if not marker.exists():
        return COMMIT_MARKER_SCHEMA_VERSION
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return COMMIT_MARKER_SCHEMA_VERSION
    return str(data.get("commit_marker_schema_version") or COMMIT_MARKER_SCHEMA_VERSION)


def load_group_member_failures(
    run_root: Path,
    *,
    agg_id: str = "llm_custom_qa",
) -> list[dict[str, Any]]:
    """Load group member failures via the group content loader (no bare path)."""
    from transcriptx.web.blocks.group_content import load_group_content_rows

    return load_group_content_rows(Path(run_root), agg_id, "qa_member_failures")
