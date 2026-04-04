"""
Canonical module execution outcomes: single projection surface for reporting.

Raw facts from execution are normalized here; manifest, run_results, and the
output reporter consume projections derived from the same rules (no duplicate
interpretation of disk vs execution state for primary execution_status).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Literal, Optional, Set, Tuple

from transcriptx.core.pipeline.module_registry import canonical_module_id

ExecutionStatus = Literal["run", "skipped", "failed", "not_requested", "blocked"]

RUN_RESULTS_SCHEMA_VERSION = 2

# Valid combinations for raw outcomes (documentation / validation aid)
# decision: selected → may run; skipped → intentional non-run; blocked → precondition/deps
RawDecision = Literal["selected", "skipped", "blocked"]


@dataclass(frozen=True)
class RawModuleOutcome:
    """Stable raw facts from execution (source for normalization)."""

    module_id: str
    decision: RawDecision
    started: bool = False
    finished: bool = False
    failure: Optional[Dict[str, Any]] = None
    skip_reason: Optional[str] = None
    block_reason: Optional[str] = None
    timing_ms: Optional[float] = None
    used_cache: bool = False
    emitted_artifact_hints: Tuple[str, ...] = ()


@dataclass
class CanonicalModuleOutcome:
    """Canonical per-module row for a run scope (serializable)."""

    module_id: str
    execution_status: ExecutionStatus
    reason_code: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None
    used_cache: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "module_id": self.module_id,
            "execution_status": self.execution_status,
        }
        if self.reason_code is not None:
            d["reason_code"] = self.reason_code
        if self.error_message is not None:
            d["error_message"] = self.error_message
        if self.duration_ms is not None:
            d["duration_ms"] = self.duration_ms
        if self.used_cache:
            d["used_cache"] = True
        return d


def normalize_raw_outcomes(
    raw: Iterable[RawModuleOutcome],
) -> List[CanonicalModuleOutcome]:
    """
    Pure: same raw rows + registry ⇒ same canonical rows (one row per module_id;
    last write wins if duplicates — callers should dedupe upstream).
    """
    rows: List[CanonicalModuleOutcome] = []
    for r in raw:
        mid = canonical_module_id(r.module_id)
        if r.used_cache:
            rows.append(
                CanonicalModuleOutcome(
                    module_id=mid,
                    execution_status="run",
                    reason_code="cache_hit",
                    duration_ms=r.timing_ms,
                    used_cache=True,
                )
            )
            continue
        if r.decision == "blocked" or (r.block_reason and not r.started):
            rows.append(
                CanonicalModuleOutcome(
                    module_id=mid,
                    execution_status="blocked",
                    reason_code=r.block_reason or "blocked",
                )
            )
            continue
        if r.decision == "skipped" or r.skip_reason:
            rows.append(
                CanonicalModuleOutcome(
                    module_id=mid,
                    execution_status="skipped",
                    reason_code=r.skip_reason or "skipped",
                )
            )
            continue
        if r.failure or (r.started and r.finished and r.failure is not None):
            err = None
            if isinstance(r.failure, dict):
                err = str(
                    r.failure.get("error_message") or r.failure.get("message") or ""
                )
            rows.append(
                CanonicalModuleOutcome(
                    module_id=mid,
                    execution_status="failed",
                    error_message=err or "failed",
                    duration_ms=r.timing_ms,
                )
            )
            continue
        if r.finished and r.started:
            rows.append(
                CanonicalModuleOutcome(
                    module_id=mid,
                    execution_status="run",
                    duration_ms=r.timing_ms,
                )
            )
            continue
        if r.decision == "selected" and not r.started:
            rows.append(
                CanonicalModuleOutcome(
                    module_id=mid,
                    execution_status="not_requested",
                    reason_code="not_started",
                )
            )
            continue
        rows.append(
            CanonicalModuleOutcome(
                module_id=mid,
                execution_status="not_requested",
                reason_code="unknown_raw_shape",
            )
        )
    return rows


def _canonical_set(names: Iterable[str]) -> Set[str]:
    return {canonical_module_id(n) for n in names if n}


def project_failed_modules(
    modules_enabled: List[str],
    modules_run: List[str],
    skipped_modules: Optional[List[Any]],
) -> List[str]:
    """
    modules_failed as pure projection: requested modules that neither ran nor
    are recorded as skipped/blocked (canonical id comparison).
    """
    ran = _canonical_set(modules_run)
    skipped_ids: Set[str] = set()
    for entry in skipped_modules or []:
        if isinstance(entry, dict) and entry.get("module") is not None:
            skipped_ids.add(canonical_module_id(str(entry["module"])))
        elif isinstance(entry, str):
            skipped_ids.add(canonical_module_id(entry))
    failed: List[str] = []
    for m in modules_enabled:
        if (
            canonical_module_id(m) not in ran
            and canonical_module_id(m) not in skipped_ids
        ):
            failed.append(m)
    return failed


def normalize_skipped_entries(
    skipped_modules: Optional[List[Any]],
) -> List[Dict[str, Any]]:
    """Normalize skipped/blocked rows for run_results and reporters."""
    out: List[Dict[str, Any]] = []
    for entry in skipped_modules or []:
        if isinstance(entry, dict) and "module" in entry:
            st = entry.get("execution_status", "skipped")
            if st not in ("skipped", "blocked"):
                st = "skipped"
            out.append(
                {
                    "module": str(entry["module"]),
                    "reason": str(entry.get("reason", "Skipped")),
                    "execution_status": st,
                }
            )
        elif isinstance(entry, str):
            out.append(
                {
                    "module": entry,
                    "reason": "Not in registry",
                    "execution_status": "skipped",
                }
            )
    return out


def build_canonical_rows_from_run_lists(
    modules_enabled: List[str],
    modules_run: List[str],
    skipped_modules: Optional[List[Any]],
    errors: Optional[List[str]],
) -> List[CanonicalModuleOutcome]:
    """
    Build canonical rows from pipeline result lists (post-execution projection).
    """
    ran = _canonical_set(modules_run)
    skipped_norm = normalize_skipped_entries(skipped_modules)
    skipped_by_id = {canonical_module_id(s["module"]): s for s in skipped_norm}
    rows: List[CanonicalModuleOutcome] = []
    err_text_by_module: Dict[str, str] = {}
    for err in errors or []:
        if not err:
            continue
        # Best-effort: "module_name: message" from DAG
        if ":" in err:
            mod, _, rest = err.partition(":")
            mod = mod.strip()
            if mod:
                err_text_by_module.setdefault(canonical_module_id(mod), rest.strip())

    enabled_ids = {canonical_module_id(m) for m in modules_enabled}
    for mid in sorted(enabled_ids):
        if mid in ran:
            rows.append(CanonicalModuleOutcome(module_id=mid, execution_status="run"))
            continue
        sk = skipped_by_id.get(mid)
        if sk:
            st: ExecutionStatus = (
                "blocked" if sk.get("execution_status") == "blocked" else "skipped"
            )
            rows.append(
                CanonicalModuleOutcome(
                    module_id=mid,
                    execution_status=st,
                    reason_code=str(sk.get("reason", "")) or None,
                )
            )
            continue
        err = err_text_by_module.get(mid)
        rows.append(
            CanonicalModuleOutcome(
                module_id=mid,
                execution_status="failed",
                error_message=err,
            )
        )
    return rows


def aggregate_group_module_lists(
    selected_modules: List[str],
    per_transcript_results: Any,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Union modules_run across members; merge skips for modules that never ran
    successfully on any member (dedupe by canonical module id).
    """
    ran_c: Set[str] = set()
    for ptr in per_transcript_results:
        for m in getattr(ptr, "modules_run", []) or []:
            ran_c.add(canonical_module_id(m))

    # Policy-based precedence for conflicting skip-like states across members.
    skip_precedence = {"skipped": 0, "blocked": 1}
    skipped_by_cid: Dict[str, Dict[str, Any]] = {}
    for ptr in per_transcript_results:
        for entry in getattr(ptr, "skipped_modules", []) or []:
            if not isinstance(entry, dict) or "module" not in entry:
                continue
            cid = canonical_module_id(str(entry["module"]))
            if cid in ran_c:
                continue
            st = entry.get("execution_status", "skipped")
            if st not in ("skipped", "blocked"):
                st = "skipped"
            candidate = {
                "module": str(entry["module"]),
                "reason": str(entry.get("reason", "Skipped")),
                "execution_status": st,
            }
            existing = skipped_by_cid.get(cid)
            if existing is None:
                skipped_by_cid[cid] = candidate
                continue
            existing_st = str(existing.get("execution_status", "skipped"))
            if skip_precedence.get(st, 0) > skip_precedence.get(existing_st, 0):
                skipped_by_cid[cid] = candidate
    skipped_out = list(skipped_by_cid.values())

    modules_run_out: List[str] = []
    seen_run: Set[str] = set()
    for m in selected_modules:
        cid = canonical_module_id(m)
        if cid in ran_c and cid not in seen_run:
            modules_run_out.append(m)
            seen_run.add(cid)
    for ptr in per_transcript_results:
        for m in getattr(ptr, "modules_run", []) or []:
            cid = canonical_module_id(m)
            if cid in ran_c and cid not in seen_run:
                modules_run_out.append(m)
                seen_run.add(cid)
    return modules_run_out, skipped_out


def assert_run_results_schema_supported(payload: Dict[str, Any]) -> None:
    """Fail fast for non-v2 run_results on the canonical consumption path."""
    ver = payload.get("schema_version", 0)
    if ver != RUN_RESULTS_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported run_results.json schema_version={ver!r}; "
            f"expected == {RUN_RESULTS_SCHEMA_VERSION}. Re-run analysis to regenerate."
        )
