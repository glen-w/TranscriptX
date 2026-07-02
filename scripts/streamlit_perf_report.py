#!/usr/bin/env python3
"""Summarize Streamlit perf JSONL runs into markdown tables."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

TIMING_COLUMNS = [
    ("total_wall_time_ms", "Total wall time"),
    ("import_bootstrap", "Import/bootstrap"),
    ("session_discovery", "Session discovery"),
    ("home_summary", "Home summary"),
    ("transcript_discovery", "Transcript discovery"),
    ("transcript_validation", "Transcript validation"),
    ("segment_metadata_load", "Segment metadata load"),
    ("render_routing", "Render/routing"),
]

COUNT_COLUMNS = [
    "transcript_json_files",
    "valid_canonical_transcripts",
    "valid_managed_transcripts",
    "invalid_or_legacy_files",
    "output_run_dirs",
    "recent_runs_returned",
    "groups_returned",
    "segments_loaded",
    "json_files_read",
    "json_files_read_more_than_once",
    "warnings_emitted",
    "cache_hit_or_miss",
]


def _load_runs(path: Path) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("event") == "run_summary":
            runs.append(row)
    return runs


def _scenario_name(run: dict[str, Any]) -> str:
    return str(run.get("scenario") or run.get("page") or run.get("run_id"))


def _fmt_ms(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "-"


def _print_timing_table(runs: list[dict[str, Any]]) -> None:
    headers = ["Scenario"] + [label for _, label in TIMING_COLUMNS] + ["Notes"]
    print("## Timing Table")
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for run in runs:
        totals = run.get("section_totals_ms", {})
        row = [_scenario_name(run)]
        for key, _label in TIMING_COLUMNS:
            if key == "total_wall_time_ms":
                row.append(_fmt_ms(run.get("total_wall_time_ms")))
            else:
                row.append(_fmt_ms(totals.get(key)))
        row.append(str(run.get("notes") or ""))
        print("| " + " | ".join(row) + " |")
    print()


def _print_count_table(runs: list[dict[str, Any]]) -> None:
    print("## Count Table")
    headers = ["Scenario"] + COUNT_COLUMNS
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for run in runs:
        counts = run.get("counts", {})
        cache_summary = ",".join(
            f"{name}:{state}"
            for name, state in sorted((run.get("cache_hit_or_miss") or {}).items())
        )
        row = [_scenario_name(run)]
        for key in COUNT_COLUMNS:
            if key == "warnings_emitted":
                row.append(str(run.get("warnings_emitted", 0)))
            elif key == "json_files_read_more_than_once":
                row.append(str(run.get("json_files_read_more_than_once", 0)))
            elif key == "cache_hit_or_miss":
                row.append(cache_summary)
            else:
                row.append(str(counts.get(key, 0)))
        print("| " + " | ".join(row) + " |")
    print()


def _print_duplicate_report(runs: list[dict[str, Any]]) -> None:
    print("## Duplicate File Reads")
    for run in runs:
        duplicates = run.get("duplicate_file_reads", [])
        print(f"### {_scenario_name(run)}")
        if not duplicates:
            print("No duplicate JSON reads recorded.\n")
            continue
        print("| Path | Count | Sections | Purposes |")
        print("|---|---:|---|---|")
        for entry in duplicates:
            print(
                "| {path} | {count} | {sections} | {purposes} |".format(
                    path=entry.get("path", ""),
                    count=entry.get("count", 0),
                    sections=", ".join(entry.get("sections", [])),
                    purposes=", ".join(entry.get("purposes", [])),
                )
            )
        print()


def _print_cache_summary(runs: list[dict[str, Any]]) -> None:
    print("## Cache Summary")
    aggregate: dict[str, Counter[str]] = {}
    for run in runs:
        for cache_name, state in (run.get("cache_hit_or_miss") or {}).items():
            aggregate.setdefault(cache_name, Counter())[state] += 1
    if not aggregate:
        print("No cache activity recorded.\n")
        return
    print("| Cache | Hits | Misses |")
    print("|---|---:|---:|")
    for cache_name in sorted(aggregate):
        bucket = aggregate[cache_name]
        print(f"| {cache_name} | {bucket.get('hit', 0)} | {bucket.get('miss', 0)} |")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to JSONL output file")
    args = parser.parse_args()

    runs = _load_runs(args.path)
    _print_timing_table(runs)
    _print_count_table(runs)
    _print_duplicate_report(runs)
    _print_cache_summary(runs)


if __name__ == "__main__":
    main()
