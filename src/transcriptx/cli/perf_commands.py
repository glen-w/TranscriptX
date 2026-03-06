"""
CLI commands for performance span queries.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import typer
from rich.console import Console
from rich.table import Table


console = Console()
app = typer.Typer(name="perf", help="Performance span queries", no_args_is_help=True)


def _parse_since(value: str) -> timedelta:
    value = value.strip().lower()
    if value.endswith("d"):
        return timedelta(days=int(value[:-1]))
    if value.endswith("h"):
        return timedelta(hours=int(value[:-1]))
    if value.endswith("m"):
        return timedelta(minutes=int(value[:-1]))
    return timedelta(days=int(value))


def _parse_filters(filters: Optional[List[str]]) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    if not filters:
        return parsed
    for raw in filters:
        if "=" not in raw:
            raise typer.BadParameter(f"Invalid filter '{raw}'. Use key=value format.")
        key, value = raw.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _percentile(values: List[float], percentile: float) -> Optional[float]:
    if not values:
        return None
    values = sorted(values)
    if percentile <= 0:
        return values[0]
    if percentile >= 100:
        return values[-1]
    k = (len(values) - 1) * (percentile / 100.0)
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[f]
    d0 = values[f] * (c - k)
    d1 = values[c] * (k - f)
    return d0 + d1


@app.command("top")
def top(
    since: str = typer.Option(
        "7d", "--since", help="Lookback window, e.g. 7d, 24h, 30m"
    ),
    group_by: str = typer.Option(
        "name", "--group-by", help="Group by span name or attribute key"
    ),
    filters: Optional[List[str]] = typer.Option(
        None, "--filter", "-f", help="Filter spans by attribute key=value"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Max groups to show"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output"),
) -> None:
    """Show top span groups by duration statistics."""
    start_date = datetime.utcnow() - _parse_since(since)
    filter_map = _parse_filters(filters)

    from transcriptx.database.database import get_session
    from transcriptx.database.repositories import PerformanceSpanRepository

    session = get_session()
    try:
        repo = PerformanceSpanRepository(session)
        spans = repo.query_spans(
            start_date=start_date,
            status_code="OK",
            attributes_filter=filter_map or None,
        )
    finally:
        session.close()

    grouped: Dict[str, List[float]] = {}
    for span in spans:
        if span.duration_ms is not None:
            duration = span.duration_ms / 1000.0
        elif span.start_time and span.end_time:
            duration = (span.end_time - span.start_time).total_seconds()
        else:
            continue

        if group_by == "name":
            key = span.name
        else:
            key = (span.attributes_json or {}).get(group_by, "unknown")
        grouped.setdefault(str(key), []).append(duration)

    rows = []
    for key, durations in grouped.items():
        durations.sort()
        rows.append(
            {
                "group": key,
                "count": len(durations),
                "p50": _percentile(durations, 50) or 0,
                "p90": _percentile(durations, 90) or 0,
                "p95": _percentile(durations, 95) or 0,
                "avg": sum(durations) / len(durations),
                "total": sum(durations),
            }
        )

    rows.sort(key=lambda item: item["p90"], reverse=True)
    rows = rows[:limit]

    if json_output:
        print(json.dumps(rows, indent=2))
        raise typer.Exit(code=0)

    table = Table(title="Performance spans")
    table.add_column("Group", justify="left")
    table.add_column("Count", justify="right")
    table.add_column("P50 (s)", justify="right")
    table.add_column("P90 (s)", justify="right")
    table.add_column("P95 (s)", justify="right")
    table.add_column("Avg (s)", justify="right")
    table.add_column("Total (s)", justify="right")

    for row in rows:
        table.add_row(
            row["group"],
            str(row["count"]),
            f"{row['p50']:.2f}",
            f"{row['p90']:.2f}",
            f"{row['p95']:.2f}",
            f"{row['avg']:.2f}",
            f"{row['total']:.2f}",
        )

    console.print(table)
