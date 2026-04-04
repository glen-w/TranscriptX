"""
Run-aware report input resolution.

Uses run_results.json as the canonical source for module execution state and
chooses the best summary source per module (preferred → fallback). Falls back
to manifest-based artifact discovery only when needed. Decides report_contribution_status
(full_section, mention_only, omitted) using a minimum viable section payload contract.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.pipeline.manifest_loader import (
    load_artifact_manifest,
    load_run_results,
)
from transcriptx.core.pipeline.run_outcome_truth import status_for_module
from transcriptx.core.pipeline.run_outcome_truth import project_canonical_outcomes

# Report contribution status: how the report uses the module's output.
REPORT_CONTRIBUTION_FULL_SECTION = "full_section"
REPORT_CONTRIBUTION_MENTION_ONLY = "mention_only"
REPORT_CONTRIBUTION_OMITTED = "omitted"

# Module execution status (canonical read model).
MODULE_STATUS_SUCCEEDED = "succeeded"
MODULE_STATUS_SKIPPED = "skipped"
MODULE_STATUS_BLOCKED = "blocked"
MODULE_STATUS_FAILED = "failed"


@dataclass(frozen=True)
class CanonicalReportInputSpec:
    """Per-module canonical report input: paths and minimum viable contract."""

    module_id: str
    preferred_paths: Tuple[str, ...]  # rel path templates with {base}
    fallback_paths: Tuple[str, ...] = ()  # e.g. legacy or chart-only
    required_keys: Tuple[str, ...] = ()  # keys that must exist and pass quality check
    support_level: str = "basic"  # "fully_supported" | "basic" | "artifact_only"


# Canonical report input mapping: preferred path(s), fallback(s), required_keys, support level.
# Paths are relative to run_dir; {base} is replaced with base_name.
CANONICAL_REPORT_INPUT_SPECS: Tuple[CanonicalReportInputSpec, ...] = (
    CanonicalReportInputSpec(
        "sentiment",
        ("sentiment/data/global/{base}_sentiment_summary.json",),
        required_keys=("mean_compound",),
        support_level="fully_supported",
    ),
    CanonicalReportInputSpec(
        "emotion",
        ("emotion/data/global/{base}_emotion_summary.json",),
        required_keys=("dominant_emotion",),
        support_level="fully_supported",
    ),
    CanonicalReportInputSpec(
        "acts",
        (
            "acts/data/global/{base}_acts_summary.json",
            "acts/data/{base}_acts_summary.json",
        ),
        required_keys=("act_counts",),
        support_level="fully_supported",
    ),
    CanonicalReportInputSpec(
        "interactions",
        ("interactions/data/global/{base}_speaker_summary.json",),
        required_keys=("speakers",),
        support_level="fully_supported",
    ),
    CanonicalReportInputSpec(
        "ner",
        ("ner/{base}_ner-entities.json",),
        required_keys=("entities",),
        support_level="fully_supported",
    ),
    CanonicalReportInputSpec(
        "entity_sentiment",
        (
            "entity_sentiment/data/global/{base}_summary.json",
            "entity_sentiment/data/{base}_entity_sentiment_summary.json",
        ),
        required_keys=("entities",),
        support_level="basic",
    ),
    CanonicalReportInputSpec(
        "conversation_loops",
        ("conversation_loops/data/{base}_conversation_loops_summary.json",),
        required_keys=("loops",),
        support_level="basic",
    ),
    CanonicalReportInputSpec(
        "contagion",
        ("contagion/data/{base}_contagion_summary.json",),
        required_keys=("contagion_scores",),
        support_level="basic",
    ),
    CanonicalReportInputSpec(
        "wordclouds",
        ("wordclouds/data/global/{base}_wordcloud_summary.json",),
        required_keys=("top_words",),
        support_level="basic",
    ),
    CanonicalReportInputSpec(
        "tics",
        ("tics/data/global/{base}_tics_summary.json",),
        required_keys=("tics",),
        support_level="fully_supported",
    ),
    CanonicalReportInputSpec(
        "understandability",
        ("understandability/data/global/{base}_understandability.json",),
        required_keys=("scores",),
        support_level="basic",
    ),
    CanonicalReportInputSpec(
        "temporal_dynamics",
        ("temporal_dynamics/data/global/{base}_temporal_dynamics_summary.json",),
        required_keys=("phases",),
        support_level="basic",
    ),
    CanonicalReportInputSpec(
        "pauses",
        ("pauses/data/global/{base}_pauses_summary.json",),
        required_keys=("pause_rate",),
        support_level="basic",
    ),
    CanonicalReportInputSpec(
        "momentum",
        ("momentum/data/global/{base}_momentum_summary.json",),
        required_keys=("stall_index",),
        support_level="basic",
    ),
    CanonicalReportInputSpec(
        "highlights",
        ("highlights/data/global/{base}_highlights.json",),
        required_keys=("highlights",),
        support_level="basic",
    ),
    CanonicalReportInputSpec(
        "summary",
        ("summary/data/global/{base}_summary.json",),
        required_keys=("brief",),
        support_level="fully_supported",
    ),
    CanonicalReportInputSpec(
        "affect_tension",
        ("affect_tension/data/global/{base}_affect_tension_summary.json",),
        required_keys=("tension",),
        support_level="basic",
    ),
)


def _load_run_results(run_dir: Path) -> Optional[Dict[str, Any]]:
    """Load run_results.json; return None if missing or invalid."""
    path = run_dir / "run_results.json"
    if not path.exists():
        return None
    try:
        return load_run_results(path)
    except Exception:
        return None


def _load_manifest(run_dir: Path) -> Optional[Dict[str, Any]]:
    """Load manifest.json (artifact manifest); return None if missing or invalid."""
    path = run_dir / "manifest.json"
    if not path.exists():
        return None
    try:
        return load_artifact_manifest(path)
    except Exception:
        return None


def _module_status_from_run_results(
    module_id: str,
    run_results: Dict[str, Any],
) -> str:
    """Derive module_status from canonical run-outcome projection."""
    status = status_for_module(module_id, run_results, default_if_missing="requested")
    if status == "succeeded":
        return MODULE_STATUS_SUCCEEDED
    if status == "failed":
        return MODULE_STATUS_FAILED
    if status in {"blocked", "skipped"}:
        return status
    # requested/enabled are non-completed in report context.
    return MODULE_STATUS_SKIPPED


def _resolve_canonical_path(
    run_dir: Path,
    base_name: str,
    paths: Tuple[str, ...],
) -> Optional[Path]:
    """Return first path that exists; paths are templates with {base}."""
    for template in paths:
        rel = template.format(base=base_name)
        full = run_dir / rel
        if full.exists():
            return full
    return None


def _passes_minimum_viable_contract(
    path: Path,
    required_keys: Tuple[str, ...],
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Minimum viable section payload contract:
    - File exists, non-zero bytes, parses as JSON
    - Contains required keys
    - Simple quality: non-empty, non-zero where numeric, not all-null for key fields.

    Returns (passed, parsed_data, error_message).
    """
    if not path.exists():
        return False, None, "file missing"
    try:
        raw = path.read_bytes()
    except OSError as e:
        return False, None, str(e)
    if len(raw) == 0:
        return False, None, "file empty"
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return False, None, f"invalid JSON: {e}"
    if not isinstance(data, dict):
        return False, None, "root is not an object"
    for key in required_keys:
        if key not in data:
            return False, data, f"missing required key: {key}"
        val = data[key]
        if val is None:
            return False, data, f"required key {key} is null"
        if isinstance(val, (list, dict)) and len(val) == 0:
            return False, data, f"required key {key} is empty"
        if isinstance(val, (int, float)) and val == 0 and key in ("mean_compound",):
            # Allow zero for mean_compound (neutral sentiment)
            pass
        elif isinstance(val, (int, float)) and val == 0:
            # Other numeric keys: zero might be valid; allow but could tighten later
            pass
    return True, data, None


def _artifact_paths_for_module(manifest: Dict[str, Any], module_id: str) -> List[str]:
    """Return list of rel_paths for artifacts belonging to module_id."""
    artifacts = manifest.get("artifacts") or []
    return [a["rel_path"] for a in artifacts if a.get("module") == module_id]


@dataclass
class ModuleResolutionResult:
    """Result of resolving one module for the report."""

    module_id: str
    module_status: str  # ran | skipped | failed
    report_contribution_status: str  # full_section | mention_only | omitted
    best_input_path: Optional[str] = None  # rel_path if found
    parsed_data: Optional[Dict[str, Any]] = None  # if passes contract
    reason: Optional[str] = None
    warning: Optional[str] = None  # if ran, expected input, but failed to extract


def resolve_report_inputs(
    run_dir: Path,
    base_name: str,
    *,
    run_results: Optional[Dict[str, Any]] = None,
    manifest: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, ModuleResolutionResult], List[str]]:
    """
    Resolve report inputs for all modules that have a canonical spec or appear in run_results.

    - run_results.json is the canonical source for module execution state.
    - For each module that ran, chooses best summary source (preferred → fallback).
    - Falls back to manifest-based artifact discovery only when needed.
    - Applies minimum viable section payload contract for full_section.

    Returns (module_id -> ModuleResolutionResult, warnings).
    Warnings: when a module ran, canonical input was expected, but resolver failed to extract usable data.
    """
    run_dir = Path(run_dir).resolve()
    run_results = run_results or _load_run_results(run_dir)
    manifest = manifest or _load_manifest(run_dir)

    specs_by_module: Dict[str, CanonicalReportInputSpec] = {
        s.module_id: s for s in CANONICAL_REPORT_INPUT_SPECS
    }
    # All modules we might report on: canonical projection rows + known specs.
    all_relevant = set()
    if run_results:
        for row in project_canonical_outcomes(run_results):
            all_relevant.add(row.module_id)
    all_relevant |= set(specs_by_module.keys())

    results: Dict[str, ModuleResolutionResult] = {}
    warnings: List[str] = []

    for module_id in sorted(all_relevant):
        module_status = (
            _module_status_from_run_results(module_id, run_results)
            if run_results
            else MODULE_STATUS_SKIPPED
        )

        spec = specs_by_module.get(module_id)
        if not spec:
            results[module_id] = ModuleResolutionResult(
                module_id=module_id,
                module_status=module_status,
                report_contribution_status=REPORT_CONTRIBUTION_OMITTED,
                reason="no canonical report input spec",
            )
            continue

        if module_status in (MODULE_STATUS_SKIPPED, MODULE_STATUS_BLOCKED):
            results[module_id] = ModuleResolutionResult(
                module_id=module_id,
                module_status=module_status,
                report_contribution_status=REPORT_CONTRIBUTION_OMITTED,
                reason=(
                    "module blocked"
                    if module_status == MODULE_STATUS_BLOCKED
                    else "module skipped"
                ),
            )
            continue

        if module_status == MODULE_STATUS_FAILED:
            results[module_id] = ModuleResolutionResult(
                module_id=module_id,
                module_status=module_status,
                report_contribution_status=REPORT_CONTRIBUTION_OMITTED,
                reason="module failed",
            )
            continue

        # Module succeeded: choose best input (preferred then fallback)
        all_paths = spec.preferred_paths + spec.fallback_paths
        best_path = _resolve_canonical_path(run_dir, base_name, all_paths)
        if not best_path and manifest:
            artifact_paths = _artifact_paths_for_module(manifest, module_id)
            if artifact_paths:
                for rel in artifact_paths:
                    if not rel.endswith(".json"):
                        continue
                    full = run_dir / rel
                    if full.exists():
                        best_path = full
                        break
                if not best_path and artifact_paths:
                    for rel in artifact_paths:
                        full = run_dir / rel
                        if full.exists():
                            best_path = full
                            break
        if not best_path:
            results[module_id] = ModuleResolutionResult(
                module_id=module_id,
                module_status=module_status,
                report_contribution_status=REPORT_CONTRIBUTION_OMITTED,
                reason="no artifact found",
            )
            continue

        rel_path = best_path.relative_to(run_dir).as_posix()
        passed, parsed_data, contract_error = _passes_minimum_viable_contract(
            best_path, spec.required_keys
        )
        if passed and parsed_data is not None:
            results[module_id] = ModuleResolutionResult(
                module_id=module_id,
                module_status=module_status,
                report_contribution_status=REPORT_CONTRIBUTION_FULL_SECTION,
                best_input_path=rel_path,
                parsed_data=parsed_data,
                reason="canonical input passed contract",
            )
        else:
            # Module ran and we found a path but it failed contract -> mention_only + warning
            msg = f"{module_id}: expected summary at {rel_path}, not found or invalid"
            if contract_error:
                msg += f" ({contract_error})"
            warnings.append(msg)
            results[module_id] = ModuleResolutionResult(
                module_id=module_id,
                module_status=module_status,
                report_contribution_status=REPORT_CONTRIBUTION_MENTION_ONLY,
                best_input_path=rel_path,
                reason=contract_error or "failed minimum viable contract",
                warning=msg,
            )

    return results, warnings
