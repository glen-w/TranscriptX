"""
Group aggregation for semantic similarity.

B14: centroid motif matching within a comparable provenance cohort.
``repetition_rows`` remain the ``content_rows`` contract; ``motif_rows`` and
``semantic_similarity_pooled`` are additive.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from transcriptx.core.analysis.aggregation.common import extract_payload
from transcriptx.core.analysis.aggregation.rows import _session_row_base
from transcriptx.core.analysis.aggregation.schema import get_transcript_id
from transcriptx.core.analysis.semantic_similarity.motifs import deserialize_centroid
from transcriptx.core.analysis.semantic_similarity.output import (
    POOLED_SCHEMA_VERSION,
    reader_accepts_schema,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap
from transcriptx.core.utils.artifact_writer import write_json
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

_SEMANTIC_MODULE_PREFERENCE = ("semantic_similarity",)


def _pick_semantic_payload(
    module_results: Dict[str, Any],
) -> Tuple[Optional[str], Dict[str, Any]]:
    for module_id in _SEMANTIC_MODULE_PREFERENCE:
        if module_id not in module_results:
            continue
        payload = extract_payload(module_results, module_id)
        if payload:
            return module_id, payload
    return None, {}


def _summary_scalars(payload: Dict[str, Any]) -> Dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    total = payload.get("total_repetitions")
    if total is None:
        total = summary.get("total_repetitions")
    unique = payload.get("unique_patterns")
    if unique is None:
        unique = summary.get("unique_patterns")
    if total is None:
        speaker_reps = payload.get("speaker_repetitions") or {}
        cross = payload.get("cross_speaker_repetitions") or []
        self_count = (
            sum(len(v) for v in speaker_reps.values() if isinstance(v, list))
            if isinstance(speaker_reps, dict)
            else 0
        )
        cross_count = len(cross) if isinstance(cross, list) else 0
        total = self_count + cross_count
    return {
        "total_repetitions": int(total or 0),
        "unique_patterns": int(unique or 0),
        "mode": payload.get("mode"),
        "skipped": bool(payload.get("skipped")),
    }


def _flatten_repetitions(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    speaker_reps = payload.get("speaker_repetitions") or {}
    if isinstance(speaker_reps, dict):
        for speaker, reps in speaker_reps.items():
            if not isinstance(reps, list):
                continue
            for rep in reps:
                if isinstance(rep, dict):
                    rows.append(
                        {**rep, "kind": rep.get("type") or "self", "speaker": speaker}
                    )
    cross = payload.get("cross_speaker_repetitions") or []
    if isinstance(cross, list):
        for rep in cross:
            if isinstance(rep, dict):
                rows.append({**rep, "kind": rep.get("type") or "cross"})
    return rows


def _segment_field(seg: Any, key: str) -> Any:
    if isinstance(seg, dict):
        return seg.get(key)
    return None


def _has_motif_envelope(payload: Dict[str, Any]) -> bool:
    return "motif_export_status" in payload and "eligible_segment_count" in payload


def _session_motif_eligibility(
    module_id: str, payload: Dict[str, Any]
) -> Tuple[str, str | None]:
    """Return (inclusion_status, exclude_reason)."""
    if module_id != "semantic_similarity":
        return "excluded", "legacy_module"
    schema = str(payload.get("schema_version") or "")
    if not reader_accepts_schema(schema):
        return "excluded", "unsupported_schema"
    if not _has_motif_envelope(payload):
        return "excluded", "old_schema_missing_envelope"
    status = str(payload.get("motif_export_status") or "")
    comparability = str(
        payload.get("comparability")
        or (payload.get("provenance") or {}).get("comparability")
        or ""
    )
    if comparability == "incomparable":
        return "excluded", "incomparable_backend"
    if status in ("dependency_failure", "skipped"):
        return "excluded", status
    if status in ("ok", "valid_zero", "partial", "timeout"):
        # timeout/partial may still contribute motifs if present
        return "eligible", None
    return "excluded", f"motif_export_status:{status or 'missing'}"


def _group_motif_id(creating_transcript_id: str, local_motif_id: str) -> str:
    raw = f"{creating_transcript_id}:{local_motif_id}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape or a.size == 0:
        return float("nan")
    return float(np.dot(a, b))


def _match_motifs_across_sessions(
    ordered_sessions: List[Dict[str, Any]],
    *,
    threshold: float,
    min_sessions_for_recurring: int,
    max_motifs_per_group: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[str]]:
    """
    ordered_sessions items:
      order_index, transcript_id, motifs (list of local motif dicts with centroid vec)
    """
    warnings: List[str] = []
    group_motifs: List[Dict[str, Any]] = []
    # each: id, centroid, weight, appearances: [{order_index, transcript_id, local_id, sim, size, share}]
    session_assignments: Dict[int, Dict[str, str]] = {}  # order -> local->group

    for sess in ordered_sessions:
        order = int(sess["order_index"])
        tid = str(sess["transcript_id"])
        locals_ = list(sess.get("motifs") or [])
        used_group: set[str] = set()
        used_local: set[str] = set()
        assignments: Dict[str, str] = {}

        candidates: List[Tuple[float, str, str, int, int]] = []
        for li, local in enumerate(locals_):
            local_id = str(local["local_motif_id"])
            lvec = local["centroid_vec"]
            for gi, gm in enumerate(group_motifs):
                sim = _cosine(lvec, gm["centroid"])
                if not np.isfinite(sim) or sim < float(threshold):
                    continue
                candidates.append(
                    (float(sim), str(gm["group_motif_id"]), local_id, gi, li)
                )

        candidates.sort(key=lambda t: (-t[0], t[1], t[2]))
        for sim, gid, lid, gi, li in candidates:
            if gid in used_group or lid in used_local:
                continue
            used_group.add(gid)
            used_local.add(lid)
            assignments[lid] = gid
            gm = group_motifs[gi]
            local = locals_[li]
            w_old = float(gm["weight"])
            w_new = float(local.get("size") or 1)
            updated = (gm["centroid"] * w_old + local["centroid_vec"] * w_new) / (
                w_old + w_new
            )
            nrm = float(np.linalg.norm(updated))
            if nrm > 1e-12:
                updated = updated / nrm
            gm["centroid"] = updated
            gm["weight"] = w_old + w_new
            gm["appearances"].append(
                {
                    "order_index": order,
                    "transcript_id": tid,
                    "local_motif_id": lid,
                    "match_similarity": sim,
                    "size": int(local.get("size") or 0),
                    "eligible_segment_share": float(
                        local.get("eligible_segment_share") or 0.0
                    ),
                    "exemplar_text": local.get("exemplar_text"),
                }
            )

        for li, local in enumerate(locals_):
            lid = str(local["local_motif_id"])
            if lid in used_local:
                continue
            gid = _group_motif_id(tid, lid)
            group_motifs.append(
                {
                    "group_motif_id": gid,
                    "centroid": local["centroid_vec"].copy(),
                    "weight": float(local.get("size") or 1),
                    "appearances": [
                        {
                            "order_index": order,
                            "transcript_id": tid,
                            "local_motif_id": lid,
                            "match_similarity": 1.0,
                            "size": int(local.get("size") or 0),
                            "eligible_segment_share": float(
                                local.get("eligible_segment_share") or 0.0
                            ),
                            "exemplar_text": local.get("exemplar_text"),
                        }
                    ],
                    "seed_segment_refs": list(local.get("segment_refs") or []),
                }
            )
            assignments[lid] = gid
            used_local.add(lid)

        session_assignments[order] = assignments

    # Build motif_rows + prevalence matrix
    orders = [int(s["order_index"]) for s in ordered_sessions]
    motif_rows: List[Dict[str, Any]] = []
    for gm in group_motifs:
        apps = gm["appearances"]
        session_count = len({a["order_index"] for a in apps})
        status = (
            "recurring"
            if session_count >= int(min_sessions_for_recurring)
            else "singleton"
        )
        presence = {int(a["order_index"]): a for a in apps}
        presence_series = [1.0 if o in presence else 0.0 for o in orders]
        share_series = [
            float(presence[o]["eligible_segment_share"]) if o in presence else 0.0
            for o in orders
        ]
        size_series = [
            float(presence[o]["size"]) if o in presence else 0.0 for o in orders
        ]
        # prevalence slope via simple least-squares on presence
        slope = _presence_slope(orders, presence_series)
        first = min(a["order_index"] for a in apps)
        last = max(a["order_index"] for a in apps)
        mean_sim = float(np.mean([float(a["match_similarity"]) for a in apps]))
        exemplar = next(
            (a.get("exemplar_text") for a in apps if a.get("exemplar_text")), None
        )
        motif_rows.append(
            {
                "group_motif_id": gm["group_motif_id"],
                "status": status,
                "session_count": session_count,
                "first_order_index": first,
                "last_order_index": last,
                "mean_match_similarity": mean_sim,
                "presence_slope": slope,
                "exemplar_text": exemplar,
                "appearances": apps,
                "presence_by_order": {
                    str(o): presence_series[i] for i, o in enumerate(orders)
                },
                "strength_by_order": {
                    str(o): size_series[i] for i, o in enumerate(orders)
                },
                "share_by_order": {
                    str(o): share_series[i] for i, o in enumerate(orders)
                },
            }
        )

    motif_rows.sort(
        key=lambda r: (
            0 if r["status"] == "recurring" else 1,
            -int(r["session_count"]),
            -float(r.get("mean_match_similarity") or 0.0),
            str(r["group_motif_id"]),
        )
    )
    truncated = False
    if len(motif_rows) > int(max_motifs_per_group):
        motif_rows = motif_rows[: int(max_motifs_per_group)]
        truncated = True
        warnings.append("max_motifs_per_group")

    # Session transition drift: 1 - Jaccard on group-motif presence vs previous session.
    drift_by_order: Dict[int, float | None] = {}
    prev_set: set[str] | None = None
    for sess in ordered_sessions:
        order = int(sess["order_index"])
        assigns = session_assignments.get(order) or {}
        present_ids = set(assigns.values())
        if prev_set is None:
            drift_by_order[order] = None
        else:
            union = prev_set | present_ids
            if not union:
                drift_by_order[order] = 0.0
            else:
                inter = prev_set & present_ids
                jaccard = len(inter) / float(len(union))
                drift_by_order[order] = float(1.0 - jaccard)
        prev_set = present_ids

    pooled = {
        "schema_version": POOLED_SCHEMA_VERSION,
        "order_indexes": orders,
        "motif_ids": [r["group_motif_id"] for r in motif_rows],
        "strength_matrix": [
            [float(r["strength_by_order"].get(str(o), 0.0)) for o in orders]
            for r in motif_rows
        ],
        "share_matrix": [
            [float(r["share_by_order"].get(str(o), 0.0)) for o in orders]
            for r in motif_rows
        ],
        "presence_matrix": [
            [float(r["presence_by_order"].get(str(o), 0.0)) for o in orders]
            for r in motif_rows
        ],
        "recurring_motif_ids": [
            r["group_motif_id"] for r in motif_rows if r["status"] == "recurring"
        ],
        "truncation": {
            "truncated": truncated,
            "max_motifs_per_group": int(max_motifs_per_group),
            "motif_row_count": len(motif_rows),
        },
        "drift_by_order": {str(k): v for k, v in drift_by_order.items()},
    }
    return motif_rows, pooled, warnings


def _presence_slope(orders: List[int], presence: List[float]) -> float | None:
    if len(orders) < 2:
        return None
    xs = np.asarray(orders, dtype=np.float64)
    ys = np.asarray(presence, dtype=np.float64)
    x_mean = float(xs.mean())
    y_mean = float(ys.mean())
    denom = float(((xs - x_mean) ** 2).sum())
    if denom <= 1e-12:
        return 0.0
    return float(((xs - x_mean) * (ys - y_mean)).sum() / denom)


def aggregate_semantic_similarity_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """
    Aggregate semantic similarity session scalars, repetition rows, and B14 motifs.

    Compare + centroid match within a comparable provenance cohort; TF-IDF
    backends are incomparable. Embeddings are not fully re-pooled.
    """
    del canonical_speaker_map
    try:
        cfg = get_config().analysis.semantic_similarity
        match_threshold = float(cfg.cross_session_match_threshold)
        min_recurring = int(cfg.min_sessions_for_recurring)
        max_group = int(cfg.max_motifs_per_group)
    except Exception:
        match_threshold = 0.75
        min_recurring = 2
        max_group = 40

    session_rows: List[Dict[str, Any]] = []
    repetition_rows: List[Dict[str, Any]] = []
    eligible_for_cohort: List[Dict[str, Any]] = []
    excluded_members: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for result in per_transcript_results:
        module_id, payload = _pick_semantic_payload(result.module_results)
        if not module_id or not payload:
            continue
        transcript_id = get_transcript_id(result, transcript_set)
        scalars = _summary_scalars(payload)
        session_row = _session_row_base(result, transcript_set)
        session_row.update(scalars)
        session_row["semantic_module"] = module_id

        inclusion, excl_reason = _session_motif_eligibility(module_id, payload)
        prov = (
            payload.get("provenance")
            if isinstance(payload.get("provenance"), dict)
            else {}
        )
        key = str(
            payload.get("provenance_compatibility_key")
            or prov.get("provenance_compatibility_key")
            or ""
        )
        dim = prov.get("vector_dimension")
        status = payload.get("motif_export_status")
        session_row["provenance_compatibility_key"] = key or None
        session_row["motif_export_status"] = status
        session_row["comparability"] = payload.get("comparability") or prov.get(
            "comparability"
        )
        session_row["inclusion"] = inclusion
        session_row["inclusion_reason"] = excl_reason

        if inclusion != "eligible":
            session_row["motif_count"] = None
            session_row["recurring_motif_count"] = None
            session_row["drift_score"] = None
            session_row["included_in_comparison"] = False
            excluded_members.append(
                {
                    "transcript_id": transcript_id,
                    "order_index": result.order_index,
                    "reason": excl_reason,
                }
            )
        else:
            motifs_raw = (
                payload.get("motifs") if isinstance(payload.get("motifs"), list) else []
            )
            # Validate centroids / dimensions
            valid_locals: List[Dict[str, Any]] = []
            for m in motifs_raw:
                if not isinstance(m, dict):
                    continue
                vec = deserialize_centroid(m.get("centroid"))
                if vec is None:
                    warnings.append(f"malformed_centroid:{transcript_id}")
                    continue
                if dim is not None and int(dim) != int(vec.size):
                    warnings.append(f"dimension_mismatch:{transcript_id}")
                    continue
                valid_locals.append({**m, "centroid_vec": vec})
            motif_count: int | None
            if str(status) == "valid_zero":
                motif_count = 0
            elif str(status) == "ok":
                motif_count = len(valid_locals)
            else:
                # partial / timeout / other abstentions: null scalar (plan §10)
                motif_count = None
            session_row["motif_count"] = motif_count
            session_row["included_in_comparison"] = True
            eligible_for_cohort.append(
                {
                    "order_index": result.order_index,
                    "transcript_id": transcript_id,
                    "provenance_key": key,
                    "vector_dimension": (
                        int(dim)
                        if dim is not None
                        else (
                            int(valid_locals[0]["centroid_vec"].size)
                            if valid_locals
                            else None
                        )
                    ),
                    "motifs": valid_locals,
                    "session_row_ref": session_row,
                }
            )

        session_rows.append(session_row)

        for rep in _flatten_repetitions(payload):
            seg1 = rep.get("segment1")
            seg2 = rep.get("segment2")
            text1 = str(_segment_field(seg1, "text") or "")
            text2 = str(_segment_field(seg2, "text") or "")
            speaker1 = _segment_field(seg1, "speaker") or rep.get("speaker")
            speaker2 = _segment_field(seg2, "speaker")
            similarity = rep.get("similarity")
            kind = str(rep.get("kind") or "unknown")
            hash_payload = (
                f"{transcript_id}:{kind}:{speaker1}:{speaker2}:"
                f"{text1[:120]}:{text2[:120]}"
            )
            repetition_rows.append(
                {
                    "id": hashlib.sha1(hash_payload.encode("utf-8")).hexdigest(),
                    "order_index": result.order_index,
                    "kind": kind,
                    "similarity": similarity,
                    "speaker": speaker1,
                    "speaker_2": speaker2,
                    "text": text1,
                    "text_2": text2,
                    "source_transcript_id": transcript_id,
                    "source_run_relpath": result.output_dir,
                    "semantic_module": module_id,
                }
            )

    if not session_rows:
        return None

    # Primary cohort: among keys, maximize (member_count, key); reject dim mismatches inside key
    by_key: Dict[str, List[Dict[str, Any]]] = {}
    for item in eligible_for_cohort:
        k = str(item.get("provenance_key") or "")
        if not k:
            excluded_members.append(
                {
                    "transcript_id": item["transcript_id"],
                    "order_index": item["order_index"],
                    "reason": "missing_provenance_key",
                }
            )
            item["session_row_ref"]["included_in_comparison"] = False
            item["session_row_ref"]["motif_count"] = None
            continue
        by_key.setdefault(k, []).append(item)

    primary_key = ""
    primary_members: List[Dict[str, Any]] = []
    if by_key:
        primary_key = max(by_key.keys(), key=lambda k: (len(by_key[k]), k))
        # Enforce dimension consistency within primary
        dims = [
            m["vector_dimension"]
            for m in by_key[primary_key]
            if m.get("vector_dimension") is not None
        ]
        primary_dim = dims[0] if dims else None
        for m in by_key[primary_key]:
            if primary_dim is not None and m.get("vector_dimension") not in (
                None,
                primary_dim,
            ):
                excluded_members.append(
                    {
                        "transcript_id": m["transcript_id"],
                        "order_index": m["order_index"],
                        "reason": "dimension_mismatch",
                    }
                )
                m["session_row_ref"]["included_in_comparison"] = False
                m["session_row_ref"]["motif_count"] = None
                m["session_row_ref"]["inclusion_reason"] = "dimension_mismatch"
                continue
            primary_members.append(m)
        # Mark non-primary eligible as excluded from comparison
        for k, members in by_key.items():
            if k == primary_key:
                continue
            for m in members:
                excluded_members.append(
                    {
                        "transcript_id": m["transcript_id"],
                        "order_index": m["order_index"],
                        "reason": "non_primary_cohort",
                    }
                )
                m["session_row_ref"]["included_in_comparison"] = False
                m["session_row_ref"]["inclusion_reason"] = "non_primary_cohort"

    primary_members.sort(key=lambda m: (int(m["order_index"]), str(m["transcript_id"])))

    motif_rows: List[Dict[str, Any]] = []
    pooled: Dict[str, Any] = {
        "schema_version": POOLED_SCHEMA_VERSION,
        "order_indexes": [],
        "motif_ids": [],
        "strength_matrix": [],
        "share_matrix": [],
        "presence_matrix": [],
        "recurring_motif_ids": [],
        "truncation": {"truncated": False},
        "drift_by_order": {},
    }
    match_warnings: List[str] = []
    if primary_members:
        motif_rows, pooled, match_warnings = _match_motifs_across_sessions(
            primary_members,
            threshold=match_threshold,
            min_sessions_for_recurring=min_recurring,
            max_motifs_per_group=max_group,
        )
        warnings.extend(match_warnings)
        drift_map = pooled.get("drift_by_order") or {}
        recurring_ids = set(pooled.get("recurring_motif_ids") or [])
        for m in primary_members:
            row = m["session_row_ref"]
            order = int(m["order_index"])
            row["drift_score"] = drift_map.get(str(order))
            # recurring count: motifs appearing this session that are recurring
            appearing = {
                mr["group_motif_id"]
                for mr in motif_rows
                if any(int(a["order_index"]) == order for a in mr["appearances"])
            }
            row["recurring_motif_count"] = len(appearing & recurring_ids)
            if (
                row.get("motif_count") is None
                and str(row.get("motif_export_status")) == "valid_zero"
            ):
                row["motif_count"] = 0

    pooled["primary_cohort_key"] = primary_key
    pooled["primary_cohort_member_count"] = len(primary_members)
    pooled["excluded_members"] = excluded_members
    pooled["warnings"] = sorted(set(warnings))

    repetition_rows.sort(
        key=lambda row: (
            row.get("order_index", 0),
            -(float(row.get("similarity") or 0.0)),
        )
    )

    # Persist additive B14 artifacts: motif_rows via extra_tables (row writer);
    # pooled blob written here (not a list table). Soft-fail if output dir missing.
    group_output_dir = transcript_set.metadata.get("group_output_dir")
    if group_output_dir:
        try:
            agg_dir = Path(str(group_output_dir)) / "semantic_similarity"
            agg_dir.mkdir(parents=True, exist_ok=True)
            write_json(
                agg_dir / "semantic_similarity_pooled.json",
                pooled,
                indent=2,
                ensure_ascii=False,
            )
        except Exception as exc:
            logger.warning(
                "Failed to write semantic_similarity_pooled.json: %s",
                exc,
                exc_info=True,
            )

    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "content_rows": repetition_rows,
        "content_rows_name": "repetition_rows",
        "motif_rows": motif_rows,
        "extra_tables": {"motif_rows": motif_rows},
        "semantic_similarity_pooled": pooled,
        "primary_cohort_key": primary_key,
        "primary_cohort_member_count": len(primary_members),
        "excluded_members": excluded_members,
        "warnings": pooled["warnings"],
        "metrics_spec": [
            {
                "name": "total_repetitions",
                "format": "int",
                "description": "Repetition matches in session",
            },
            {
                "name": "unique_patterns",
                "format": "int",
                "description": "Unique repetition patterns / clusters",
            },
            {
                "name": "motif_count",
                "format": "int",
                "description": "Exported motifs (null when unsupported/abstained)",
            },
            {
                "name": "recurring_motif_count",
                "format": "int",
                "description": "Recurring motifs present in session",
            },
            {
                "name": "drift_score",
                "format": "float",
                "description": "Transition distance vs previous comparable session",
            },
            {
                "name": "similarity",
                "format": "float",
                "description": "Pair similarity score",
            },
        ],
        "aggregation_note": (
            "Compare + centroid match within comparable provenance cohort; "
            "TF-IDF motifs are incomparable; embeddings are not fully re-pooled. "
            "repetition_rows remain content_rows."
        ),
    }
