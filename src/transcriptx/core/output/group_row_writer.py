"""
Standard writer for group aggregation row outputs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from transcriptx.core.analysis.aggregation.schema import (
    serialize_value,
    validate_session_rows,
    validate_speaker_rows,
)
from transcriptx.core.analysis.aggregation.warnings import (
    AggregationWarning,
    build_warning,
)
from transcriptx.core.utils.artifact_writer import write_csv, write_json
from transcriptx.core.utils.run_writer_locks import per_run_lock


def _sort_header(required: List[str], keys: Iterable[str]) -> List[str]:
    seen = set(required)
    extras = [key for key in sorted(keys) if key not in seen]
    return list(required) + extras


def _rows_to_csv(
    rows: List[Dict[str, Any]],
    required: List[str],
    drop_keys: Optional[List[str]] = None,
) -> Tuple[List[List[Any]], List[str]]:
    drop_set = set(drop_keys or [])
    keys = set()
    for row in rows:
        keys.update({k for k in row.keys() if k not in drop_set})
    header = _sort_header(required, keys)
    csv_rows: List[List[Any]] = []
    for row in rows:
        csv_rows.append([serialize_value(row.get(key)) for key in header])
    return csv_rows, header


def write_row_outputs(
    *,
    base_dir: Path,
    agg_id: str,
    session_rows: List[Dict[str, Any]],
    speaker_rows: List[Dict[str, Any]],
    metrics_spec: Optional[List[Dict[str, Any]]] = None,
    content_rows: Optional[List[Dict[str, Any]]] = None,
    content_rows_name: Optional[str] = None,
    bundle: bool = True,
    drop_csv_keys: Optional[List[str]] = None,
    extra_tables: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    schema_version: int = 1,
) -> Tuple[bool, Optional[AggregationWarning]]:
    """
    Write standardized row outputs for a group aggregation.

    Returns (written, warning). When validation fails, no files are written.
    """
    ok_sessions, session_errors = validate_session_rows(session_rows)
    ok_speakers, speaker_errors = validate_speaker_rows(speaker_rows)
    if not ok_sessions or not ok_speakers:
        details = {
            "session_row_errors": session_errors,
            "speaker_row_errors": speaker_errors,
        }
        warning = build_warning(
            code="SCHEMA_VALIDATION_FAILED",
            message="Row validation failed; aggregation output skipped.",
            aggregation_key=agg_id,
            details=details,
        )
        return False, warning

    with per_run_lock(base_dir):
        return _write_row_outputs_body(
            base_dir=base_dir,
            agg_id=agg_id,
            session_rows=session_rows,
            speaker_rows=speaker_rows,
            metrics_spec=metrics_spec,
            content_rows=content_rows,
            content_rows_name=content_rows_name,
            bundle=bundle,
            drop_csv_keys=drop_csv_keys,
            extra_tables=extra_tables,
            schema_version=schema_version,
        )


def _write_row_outputs_body(
    *,
    base_dir: Path,
    agg_id: str,
    session_rows: List[Dict[str, Any]],
    speaker_rows: List[Dict[str, Any]],
    metrics_spec: Optional[List[Dict[str, Any]]] = None,
    content_rows: Optional[List[Dict[str, Any]]] = None,
    content_rows_name: Optional[str] = None,
    bundle: bool = True,
    drop_csv_keys: Optional[List[str]] = None,
    extra_tables: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    schema_version: int = 1,
) -> Tuple[bool, Optional[AggregationWarning]]:
    agg_dir = base_dir / agg_id
    agg_dir.mkdir(parents=True, exist_ok=True)

    write_json(
        agg_dir / "session_rows.json", session_rows, indent=2, ensure_ascii=False
    )
    write_json(
        agg_dir / "speaker_rows.json", speaker_rows, indent=2, ensure_ascii=False
    )

    session_csv_rows, session_header = _rows_to_csv(
        session_rows, required=["transcript_id", "order_index"], drop_keys=drop_csv_keys
    )
    speaker_csv_rows, speaker_header = _rows_to_csv(
        speaker_rows,
        required=["canonical_speaker_id", "display_name", "speaker_key"],
        drop_keys=drop_csv_keys,
    )
    write_csv(agg_dir / "session_rows.csv", session_csv_rows, header=session_header)
    write_csv(agg_dir / "speaker_rows.csv", speaker_csv_rows, header=speaker_header)

    if metrics_spec is not None:
        write_json(
            agg_dir / "metrics_spec.json", metrics_spec, indent=2, ensure_ascii=False
        )

    if content_rows is not None and content_rows_name:
        write_json(
            agg_dir / f"{content_rows_name}.json",
            content_rows,
            indent=2,
            ensure_ascii=False,
        )
        content_csv_rows, content_header = _rows_to_csv(
            content_rows, required=[], drop_keys=drop_csv_keys
        )
        write_csv(
            agg_dir / f"{content_rows_name}.csv",
            content_csv_rows,
            header=content_header,
        )

    if extra_tables:
        for table_name, rows in extra_tables.items():
            if not isinstance(table_name, str) or not table_name:
                continue
            safe_rows = rows if isinstance(rows, list) else []
            write_json(
                agg_dir / f"{table_name}.json",
                safe_rows,
                indent=2,
                ensure_ascii=False,
            )

    if bundle:
        bundle_payload = {
            "schema_version": int(schema_version),
            "aggregation_key": agg_id,
            "session_rows": session_rows,
            "speaker_rows": speaker_rows,
            "metrics_spec": metrics_spec or [],
        }
        if content_rows is not None and content_rows_name:
            bundle_payload[content_rows_name] = content_rows
        if extra_tables:
            for table_name, rows in extra_tables.items():
                if isinstance(table_name, str) and table_name:
                    bundle_payload[table_name] = rows if isinstance(rows, list) else []
        write_json(
            agg_dir / "aggregation.json", bundle_payload, indent=2, ensure_ascii=False
        )

    return True, None
