#!/usr/bin/env python3
"""Final 1.0 Thorough stress pass: speaker-complete transcripts + groups.

Selection: managed transcripts / groups where every diarized speaker is named
or ignored (speaker_map_status=complete for all members).

Model: qwen2.5:7b (~7.6B, ~6B-class project recommendation).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

OUT = Path(__file__).resolve().parent
SUMMARY_PATH = OUT / "batch_summary.json"
LOG_PATH = OUT / "batch.log"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _log(msg: str) -> None:
    line = f"[{_now()}] {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
            ).strip()
        )
    except Exception:
        return "unknown"


def _pkg_version() -> str:
    try:
        import transcriptx

        return str(getattr(transcriptx, "__version__", "unknown"))
    except Exception:
        return "unknown"


def _load_perf(run_dir: Path) -> dict:
    for cand in (
        run_dir / ".transcriptx" / "run_performance.json",
        run_dir / "run_performance.json",
    ):
        if cand.is_file():
            return json.loads(cand.read_text(encoding="utf-8"))
    return {}


def _module_rows(perf: dict) -> list[dict]:
    analysis = perf.get("analysis") or {}
    modules = analysis.get("modules") or analysis.get("module_timings") or []
    rows: list[dict] = []
    if isinstance(modules, list):
        for m in modules:
            if not isinstance(m, dict):
                continue
            mid = m.get("module_id") or m.get("module") or m.get("name")
            dur = m.get("duration_s")
            if dur is None and m.get("duration_ms") is not None:
                dur = float(m["duration_ms"]) / 1000.0
            rows.append(
                {
                    "module": mid,
                    "status": m.get("status") or m.get("outcome"),
                    "duration_s": round(float(dur), 3) if dur is not None else None,
                }
            )
    elif isinstance(modules, dict):
        for mid, m in modules.items():
            if not isinstance(m, dict):
                continue
            dur = m.get("duration_s")
            if dur is None and m.get("duration_ms") is not None:
                dur = float(m["duration_ms"]) / 1000.0
            rows.append(
                {
                    "module": mid,
                    "status": m.get("status") or m.get("outcome"),
                    "duration_s": round(float(dur), 3) if dur is not None else None,
                }
            )
    rows.sort(key=lambda r: (r.get("duration_s") is None, -(r.get("duration_s") or 0)))
    return rows


def _llm_summary(perf: dict) -> dict:
    llm = perf.get("llm") or {}
    if not isinstance(llm, dict):
        return {}
    wall_ms = llm.get("logical_wall_ms")
    return {
        "call_count": llm.get("call_count"),
        "success_count": llm.get("success_count"),
        "failure_count": llm.get("failure_count"),
        "logical_wall_s": round(float(wall_ms) / 1000.0, 1) if wall_ms is not None else None,
        "models": llm.get("models"),
        "tokens_eval_count": llm.get("eval_count"),
        "prompt_eval_count": llm.get("prompt_eval_count"),
    }


def _write_summary(payload: dict) -> None:
    payload["updated"] = _now()
    SUMMARY_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _ensure_ollama_model(model: str) -> None:
    import urllib.request

    body = json.dumps(
        {"model": model, "prompt": "ping", "stream": False, "options": {"num_predict": 1}}
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read().decode())
    _log(f"ollama warm model={data.get('model')} load_ns={data.get('load_duration')}")


def main() -> int:
    from transcriptx.app.models.requests import AnalysisRequest, GroupAnalysisRequest
    from transcriptx.app.workflows.analysis import run_analysis, run_group_analysis
    from transcriptx.core.analysis.llm_support.model_selection import LlmModelSelection
    from transcriptx.core.analysis.selection import resolve_analysis_preset
    from transcriptx.core.utils.audio_availability import has_resolvable_audio
    from transcriptx.services.speaker_studio.segment_index import (
        transcript_summary_from_loaded_segments,
    )
    from transcriptx.io import load_segments
    from transcriptx.core.store.group_manifest_store import GroupManifestStore

    MODEL = "qwen2.5:7b"
    if LOG_PATH.exists():
        LOG_PATH.unlink()

    _log("stress pass start")
    _ensure_ollama_model(MODEL)

    tx_dir = ROOT / "data" / "transcripts"
    managed = []
    for path in sorted(tx_dir.glob("*.json")):
        if path.name.endswith(".speaker_map.json"):
            continue
        try:
            ts = transcript_summary_from_loaded_segments(path, load_segments(str(path)))
        except Exception as exc:
            managed.append(
                {
                    "id": path.stem,
                    "file": path.name,
                    "status": "error",
                    "error": str(exc),
                }
            )
            continue
        managed.append(
            {
                "id": path.stem,
                "file": path.name,
                "path": str(path),
                "status": ts.speaker_map_status,
                "segments": ts.segment_count,
                "unique_speakers": ts.unique_speaker_count,
                "unidentified": ts.unidentified_speaker_count,
                "ignored": ts.ignored_speaker_count,
            }
        )

    qualifying_tx = [m for m in managed if m.get("status") == "complete"]
    complete_names = {m["file"] for m in qualifying_tx}

    store = GroupManifestStore()
    groups, warnings = store.list_groups_best_effort()
    qualifying_groups = []
    for g in groups:
        members = [Path(str(m)).name for m in (g.members or [])]
        if members and all(m in complete_names for m in members):
            qualifying_groups.append(
                {
                    "group_id": g.group_id,
                    "name": g.name,
                    "members": members,
                    "description": getattr(g, "description", None),
                }
            )

    summary: dict = {
        "started": _now(),
        "status": "running",
        "package_version": _pkg_version(),
        "git_sha_short": _git_sha(),
        "environment": "native host + Ollama localhost:11434",
        "model": MODEL,
        "model_params": "~7.6B",
        "model_rationale": (
            "Closest available ~6B-class text LLM; project-recommended for "
            "structured JSON analysis (Q4_K_M)."
        ),
        "mode": "full",
        "analysis_preset": "thorough",
        "selection_rule": (
            "managed transcripts with speaker_map_status=complete; "
            "groups whose every member is in that set"
        ),
        "managed_inventory": managed,
        "qualifying_transcripts": qualifying_tx,
        "qualifying_groups": qualifying_groups,
        "group_list_warnings_n": len(warnings),
        "runs": [],
    }
    _write_summary(summary)
    _log(
        f"qualifying transcripts={len(qualifying_tx)} groups={len(qualifying_groups)} "
        f"model={MODEL}"
    )

    selection = LlmModelSelection(mode="shared", shared_model=MODEL)

    # --- transcripts ---
    for item in qualifying_tx:
        path = Path(item["path"])
        plan = resolve_analysis_preset(
            "thorough",
            target="transcript",
            transcript_targets=[path],
            audio_resolver=has_resolvable_audio,
        )
        _log(
            f"START transcript {path.name} modules={len(plan.module_ids)} "
            f"preset=thorough model={MODEL}"
        )
        t0 = time.perf_counter()
        rec: dict = {
            "kind": "transcript",
            "id": item["id"],
            "file": path.name,
            "modules_requested": list(plan.module_ids),
            "started": _now(),
        }
        try:
            result = run_analysis(
                AnalysisRequest(
                    transcript_path=path,
                    mode=plan.mode,
                    modules=list(plan.module_ids),
                    profile=plan.profile,
                    analysis_preset="thorough",
                    include_unidentified_speakers=False,
                    llm_model_selection=selection,
                )
            )
            wall = time.perf_counter() - t0
            run_dir = Path(result.run_dir) if result.run_dir else Path()
            perf = _load_perf(run_dir) if run_dir.exists() else {}
            module_rows = _module_rows(perf)
            failed = [
                r["module"]
                for r in module_rows
                if str(r.get("status") or "").upper() in {"FAIL", "FAILED", "ERROR"}
            ]
            rec.update(
                {
                    "success": bool(result.success),
                    "status": result.status,
                    "errors": list(result.errors or []),
                    "warnings_n": len(result.warnings or []),
                    "wall_s": round(wall, 1),
                    "duration_seconds": result.duration_seconds,
                    "run_dir": str(run_dir),
                    "modules_executed": list(result.modules_executed or []),
                    "modules_n": len(result.modules_executed or []),
                    "perf_final_status": perf.get("final_status"),
                    "perf_execution_status": perf.get("execution_status"),
                    "perf_wall_clock_s": (
                        round(float(perf["wall_clock_duration_ms"]) / 1000.0, 1)
                        if perf.get("wall_clock_duration_ms") is not None
                        else None
                    ),
                    "llm": _llm_summary(perf),
                    "modules_failed": failed,
                    "top_modules_s": module_rows[:15],
                }
            )
            _log(
                f"DONE transcript {path.name} status={result.status} "
                f"wall_s={rec['wall_s']} errors={len(result.errors or [])}"
            )
        except Exception as exc:
            wall = time.perf_counter() - t0
            rec.update(
                {
                    "success": False,
                    "status": "exception",
                    "errors": [str(exc)],
                    "wall_s": round(wall, 1),
                    "traceback": traceback.format_exc(),
                }
            )
            _log(f"FAIL transcript {path.name}: {exc}")
        summary["runs"].append(rec)
        _write_summary(summary)

    # --- groups ---
    for g in qualifying_groups:
        member_paths = [ROOT / "data" / "transcripts" / m for m in g["members"]]
        plan = resolve_analysis_preset(
            "thorough",
            target="group",
            transcript_targets=member_paths,
            audio_resolver=has_resolvable_audio,
        )
        _log(
            f"START group {g['name']!r} id={g['group_id'][:8]}… "
            f"members={g['members']} modules={len(plan.module_ids)}"
        )
        t0 = time.perf_counter()
        rec = {
            "kind": "group",
            "id": g["group_id"],
            "name": g["name"],
            "members": g["members"],
            "modules_requested": list(plan.module_ids),
            "started": _now(),
        }
        try:
            result = run_group_analysis(
                GroupAnalysisRequest(
                    group_uuid=g["group_id"],
                    mode=plan.mode,
                    modules=list(plan.module_ids),
                    profile=plan.profile,
                    analysis_preset="thorough",
                    include_unidentified_speakers=False,
                    llm_model_selection=selection,
                )
            )
            wall = time.perf_counter() - t0
            run_dir = Path(result.run_dir) if result.run_dir else Path()
            perf = _load_perf(run_dir) if run_dir.exists() else {}
            module_rows = _module_rows(perf)
            failed = [
                r["module"]
                for r in module_rows
                if str(r.get("status") or "").upper() in {"FAIL", "FAILED", "ERROR"}
            ]
            rec.update(
                {
                    "success": bool(result.success),
                    "status": result.status,
                    "errors": list(result.errors or []),
                    "warnings_n": len(result.warnings or []),
                    "aggregation_warnings_n": len(result.aggregation_warnings or []),
                    "wall_s": round(wall, 1),
                    "duration_seconds": result.duration_seconds,
                    "run_dir": str(run_dir),
                    "modules_executed": list(result.modules_executed or []),
                    "modules_n": len(result.modules_executed or []),
                    "perf_final_status": perf.get("final_status"),
                    "perf_execution_status": perf.get("execution_status"),
                    "perf_wall_clock_s": (
                        round(float(perf["wall_clock_duration_ms"]) / 1000.0, 1)
                        if perf.get("wall_clock_duration_ms") is not None
                        else None
                    ),
                    "llm": _llm_summary(perf),
                    "modules_failed": failed,
                    "top_modules_s": module_rows[:15],
                }
            )
            _log(
                f"DONE group {g['name']!r} status={result.status} "
                f"wall_s={rec['wall_s']} errors={len(result.errors or [])}"
            )
        except Exception as exc:
            wall = time.perf_counter() - t0
            rec.update(
                {
                    "success": False,
                    "status": "exception",
                    "errors": [str(exc)],
                    "wall_s": round(wall, 1),
                    "traceback": traceback.format_exc(),
                }
            )
            _log(f"FAIL group {g['name']!r}: {exc}")
        summary["runs"].append(rec)
        _write_summary(summary)

    tx_walls = [r["wall_s"] for r in summary["runs"] if r.get("kind") == "transcript" and "wall_s" in r]
    grp_walls = [r["wall_s"] for r in summary["runs"] if r.get("kind") == "group" and "wall_s" in r]
    # Prefer strict: succeeded/completed only for pass; partial counts as soft.
    hard_ok = all(
        bool(r.get("success")) and str(r.get("status")) in {"succeeded", "completed"}
        for r in summary["runs"]
    )
    summary["totals"] = {
        "transcript_wall_sum_s": round(sum(tx_walls), 1),
        "group_wall_sum_s": round(sum(grp_walls), 1),
        "corpus_wall_sum_s": round(sum(tx_walls) + sum(grp_walls), 1),
        "transcript_wall_sum_min": round(sum(tx_walls) / 60.0, 1),
        "group_wall_sum_min": round(sum(grp_walls) / 60.0, 1),
        "corpus_wall_sum_min": round((sum(tx_walls) + sum(grp_walls)) / 60.0, 1),
        "runs_n": len(summary["runs"]),
        "all_success_flag": all(bool(r.get("success")) for r in summary["runs"]),
        "all_hard_success": hard_ok,
    }
    summary["finished"] = _now()
    summary["status"] = "passed" if hard_ok else ("partial" if all(bool(r.get("success")) for r in summary["runs"]) else "failed")
    _write_summary(summary)
    _log(f"stress pass finished status={summary['status']} totals={summary['totals']}")
    return 0 if hard_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
