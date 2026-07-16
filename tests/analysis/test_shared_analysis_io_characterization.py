"""Characterization and contract tests for shared analysis I/O extraction."""

from __future__ import annotations

import ast
import csv
import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from transcriptx.core.analysis.dynamics.artifact_io import (
    ensure_dynamics_dirs,
    write_events_and_stats,
    write_speaker_stats_files,
)
from transcriptx.core.analysis.dynamics.pauses import PausesAnalysis
from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.generic_numeric import (
    GenericNumericGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.helpers import make_group_output_service
from transcriptx.core.analysis.group_charts.virtual_path import (
    build_group_virtual_transcript_path,
)
from transcriptx.core.analysis.sentiment import SentimentAnalysis
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.models.events import Event
from transcriptx.core.output.output_service import create_output_service
from transcriptx.core.pipeline.module_registry import get_module_registry
from transcriptx.core.utils.validation import sanitize_filename

# ---------------------------------------------------------------------------
# Golden write-order inventories (pre-refactor expectations)
# ---------------------------------------------------------------------------

SUMMARY_PATH_NORMALIZE = (
    ("output_structure", "data_directory"),
    ("output_structure", "charts_directory"),
    ("output_structure", "global_data_directory"),
    ("output_structure", "global_charts_directory"),
    ("output_structure", "speaker_data_directory"),
    ("output_structure", "speaker_charts_directory"),
)


def _normalize_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = json.loads(json.dumps(payload))
    os_block = out.get("output_structure")
    if isinstance(os_block, dict):
        for _, key in SUMMARY_PATH_NORMALIZE:
            if key in os_block:
                os_block[key] = f"<normalized:{key}>"
    return out


def _parse_csv(path: Path) -> List[List[str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [list(row) for row in csv.reader(fh)]


class WriteLog:
    """Record ordered write calls through OutputService / io helpers."""

    def __init__(self) -> None:
        self.calls: List[str] = []

    def record(self, kind: str) -> None:
        self.calls.append(kind)


def _wrap_output_service(svc: Any, log: WriteLog) -> None:
    orig_save_data = svc.save_data
    orig_save_chart = svc.save_chart
    orig_save_summary = svc.save_summary

    def save_data(*args: Any, **kwargs: Any) -> Any:
        fmt = kwargs.get("format_type", "json")
        if len(args) >= 3:
            fmt = args[2]
        log.record(f"save_data:{fmt}")
        return orig_save_data(*args, **kwargs)

    def save_chart(*args: Any, **kwargs: Any) -> Any:
        spec = kwargs.get("spec")
        if spec is None and args:
            spec = args[0]
        viz = getattr(spec, "viz_id", None) if spec is not None else None
        log.record(f"save_chart:{viz}")
        return orig_save_chart(*args, **kwargs)

    def save_summary(*args: Any, **kwargs: Any) -> Any:
        log.record("save_summary")
        return orig_save_summary(*args, **kwargs)

    svc.save_data = save_data  # type: ignore[method-assign]
    svc.save_chart = save_chart  # type: ignore[method-assign]
    svc.save_summary = save_summary  # type: ignore[method-assign]


@pytest.fixture
def transcript_path(tmp_path: Path) -> Path:
    p = tmp_path / "mini.json"
    p.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "speaker": "Alice",
                        "text": "I love this.",
                        "start": 0.0,
                        "end": 1.0,
                    },
                    {
                        "speaker": "Bob",
                        "text": "This is bad.",
                        "start": 1.0,
                        "end": 2.0,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return p


def test_affect_package_not_in_module_registry() -> None:
    registry = get_module_registry()
    assert registry.get_module_info("affect") is None
    available = registry.get_available_modules()
    assert "affect" not in available


def test_shared_helpers_import_boundary() -> None:
    """Helpers must not import domain analysis modules or chart generators."""
    root = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "transcriptx"
        / "core"
        / "analysis"
    )
    forbidden_prefixes = (
        "transcriptx.core.analysis.sentiment",
        "transcriptx.core.analysis.emotion",
        "transcriptx.core.analysis.entity_sentiment",
        "transcriptx.core.analysis.dynamics.pauses",
        "transcriptx.core.analysis.dynamics.echoes",
        "transcriptx.core.analysis.dynamics.moments",
        "transcriptx.core.analysis.dynamics.momentum",
    )
    forbidden_substr = (
        "sentiment_charts",
        "emotion_charts",
        "generic_numeric",
        "GroupChartGenerator",
    )
    helper_files = [
        root / "affect" / "output_helpers.py",
        root / "dynamics" / "artifact_io.py",
        root / "group_charts" / "helpers.py",
    ]
    for path in helper_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
                for prefix in forbidden_prefixes:
                    assert not mod.startswith(prefix), f"{path.name} imports {mod}"
                for sub in forbidden_substr:
                    assert sub not in mod, f"{path.name} imports {mod}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in forbidden_prefixes:
                        assert not alias.name.startswith(prefix)


def test_sentiment_save_results_write_order_and_artifacts(
    transcript_path: Path, tmp_path: Path
) -> None:
    module = SentimentAnalysis()
    results = module.analyze(
        [
            {
                "speaker": "Alice",
                "text": "I love this product!",
                "start": 0.0,
                "end": 1.0,
            },
            {
                "speaker": "Bob",
                "text": "This is terrible.",
                "start": 1.0,
                "end": 2.0,
            },
        ]
    )
    svc = create_output_service(
        str(transcript_path), "sentiment", output_dir=str(tmp_path)
    )
    log = WriteLog()
    _wrap_output_service(svc, log)

    with patch(
        "transcriptx.core.analysis.affect.output_helpers.save_transcript"
    ) as mock_st:
        mock_st.side_effect = lambda *a, **k: log.record("save_transcript")
        module._save_results(results, svc)

    assert log.calls[0] == "save_transcript"
    assert log.calls[1] == "save_data:json"
    assert log.calls[2] == "save_data:csv"
    assert log.calls[-1] == "save_summary"

    base = transcript_path.stem
    module_root = Path(svc.get_output_structure().module_dir)
    assert (module_root / "data" / "global" / f"{base}_sentiment.json").exists()
    assert (module_root / "data" / "global" / f"{base}_sentiment.csv").exists()
    summary = module_root / "data" / "global" / f"{base}_sentiment_summary.json"
    assert summary.exists()
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["module"] == "sentiment"
    _normalize_summary(payload)  # must not raise

    chart_calls = [c for c in log.calls if c.startswith("save_chart:")]
    for c in chart_calls:
        assert c.startswith("save_chart:sentiment.")


def test_sentiment_empty_speaker_branch(transcript_path: Path, tmp_path: Path) -> None:
    """Controlled fixture: empty speaker_segments still writes global + summary."""
    module = SentimentAnalysis()
    results = {
        "segments_with_sentiment": [
            {
                "speaker": "Alice",
                "text": "x",
                "start": 0,
                "sentiment": {"compound": 0.1},
            }
        ],
        "speaker_segments": {},
        "all_rows": [{"start": 0, "text": "x", "compound": 0.1}],
        "global_stats": {"n": 1},
        "speaker_stats": {},
    }
    svc = create_output_service(
        str(transcript_path), "sentiment", output_dir=str(tmp_path)
    )
    log = WriteLog()
    _wrap_output_service(svc, log)
    with patch(
        "transcriptx.core.analysis.affect.output_helpers.save_transcript",
        side_effect=lambda *a, **k: log.record("save_transcript"),
    ):
        module._save_results(results, svc)
    assert "save_data:json" in log.calls
    assert "save_data:csv" in log.calls
    assert log.calls[-1] == "save_summary"
    assert not any(c.startswith("save_chart:") for c in log.calls)


def test_sentiment_failure_injection_partial_writes(
    transcript_path: Path, tmp_path: Path
) -> None:
    module = SentimentAnalysis()
    results = {
        "segments_with_sentiment": [{"speaker": "A", "text": "ok", "start": 0}],
        "speaker_segments": {},
        "all_rows": [{"start": 0, "text": "ok", "compound": 0.2}],
        "global_stats": {},
        "speaker_stats": {},
    }
    svc = create_output_service(
        str(transcript_path), "sentiment", output_dir=str(tmp_path)
    )
    n = {"i": 0}
    orig = svc.save_data

    def failing_save_data(*args: Any, **kwargs: Any) -> Any:
        n["i"] += 1
        if n["i"] == 2:  # fail on CSV after JSON
            raise RuntimeError("injected csv failure")
        return orig(*args, **kwargs)

    svc.save_data = failing_save_data  # type: ignore[method-assign]
    with patch(
        "transcriptx.core.analysis.affect.output_helpers.save_transcript",
        return_value=None,
    ):
        with pytest.raises(RuntimeError, match="injected csv failure"):
            module._save_results(results, svc)

    module_root = Path(svc.get_output_structure().module_dir)
    base = transcript_path.stem
    assert (module_root / "data" / "global" / f"{base}_sentiment.json").exists()
    assert not (module_root / "data" / "global" / f"{base}_sentiment.csv").exists()
    assert not (
        module_root / "data" / "global" / f"{base}_sentiment_summary.json"
    ).exists()


def test_pauses_save_results_events_before_stats_and_dirs(
    transcript_path: Path, tmp_path: Path
) -> None:
    module = PausesAnalysis()
    events = [
        Event(
            event_id="e1",
            kind="long_pause",
            time_start=1.0,
            time_end=2.0,
            speaker="Alice",
            segment_start_idx=0,
            segment_end_idx=0,
            severity=1.0,
            evidence=[],
        )
    ]
    results = {
        "events": events,
        "stats": {"total_gaps": 1},
        "speaker_stats": {"Alice": {"count": 1}},
        "gap_series": [{"gap_seconds": 1.5}],
        "per_segment_pause_count": [],
    }
    svc = create_output_service(
        str(transcript_path), "pauses", output_dir=str(tmp_path)
    )
    module.save_results(results, svc)
    gdir = Path(svc.get_output_structure().global_data_dir)
    assert (gdir / "pauses.events.json").exists()
    assert (gdir / "pauses.stats.json").exists()
    speaker_file = (
        Path(svc.get_output_structure().speaker_data_dir) / "Alice_pauses.stats.json"
    )
    assert speaker_file.exists()
    order: List[str] = []
    with (
        patch(
            "transcriptx.core.analysis.dynamics.artifact_io.save_events_json",
            side_effect=lambda *a, **k: (
                order.append("events"),
                Path(svc.get_output_structure().global_data_dir) / "pauses.events.json",
            )[1],
        ),
        patch(
            "transcriptx.core.analysis.dynamics.artifact_io.save_json",
            side_effect=lambda data, path: order.append(f"json:{Path(path).name}"),
        ),
    ):
        write_events_and_stats(
            svc.get_output_structure(), "pauses", events, {"total_gaps": 1}
        )
    assert order[0] == "events"
    assert order[1] == "json:pauses.stats.json"


def test_ensure_dynamics_dirs_is_mandatory_precondition(tmp_path: Path) -> None:
    """Callers must call ensure_dynamics_dirs; write helpers do not makedirs."""
    from types import SimpleNamespace
    import os

    missing = SimpleNamespace(
        global_data_dir=tmp_path / "missing" / "data" / "global",
        global_charts_dir=tmp_path / "missing" / "charts" / "global",
        speaker_data_dir=tmp_path / "missing" / "data" / "speakers",
    )
    assert not missing.global_charts_dir.exists()
    makedirs_calls: List[Any] = []
    real_makedirs = os.makedirs

    def tracking_makedirs(*args: Any, **kwargs: Any) -> Any:
        makedirs_calls.append(args[0] if args else None)
        return real_makedirs(*args, **kwargs)

    with patch(
        "transcriptx.core.analysis.dynamics.artifact_io.os.makedirs",
        side_effect=tracking_makedirs,
    ):
        # write helper must not call makedirs itself
        ensure_dynamics_dirs(missing)  # this SHOULD call makedirs
    assert makedirs_calls, "ensure_dynamics_dirs must create dirs"
    assert missing.global_data_dir.exists()
    assert missing.global_charts_dir.exists()

    makedirs_calls.clear()
    with patch(
        "transcriptx.core.analysis.dynamics.artifact_io.os.makedirs",
        side_effect=tracking_makedirs,
    ):
        write_events_and_stats(missing, "pauses", [], {"ok": True})
    assert makedirs_calls == [], "write_events_and_stats must not call os.makedirs"
    assert (missing.global_data_dir / "pauses.events.json").exists()
    assert (missing.global_data_dir / "pauses.stats.json").exists()


def test_make_group_output_service_mapping_and_tags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import transcriptx.core.utils.paths as paths_module
    import transcriptx.core.utils.output_standards as output_standards_module

    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir()
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))

    group_root = outputs_root / "group_run"
    group_root.mkdir()
    ts = TranscriptSet.create([str(tmp_path / "a.json")])
    ctx = GroupChartContext(
        group_run_root=group_root,
        group_run_id="run-1",
        agg_id="sentiment",
        transcript_set=ts,
        group_uuid="uuid-1",
    )
    expected_virtual = build_group_virtual_transcript_path(group_root, "sentiment")
    svc = make_group_output_service(ctx, module_name="sentiment", agg_id="sentiment")
    assert svc.transcript_path == expected_virtual
    assert svc.module_name == "sentiment"
    assert Path(svc.transcript_dir).resolve() == group_root.resolve()
    assert svc.run_id == "run-1"
    assert svc._agg_id == "sentiment"
    assert svc._group_uuid == "uuid-1"

    from transcriptx.core.viz.specs import BarCategoricalSpec

    svc.save_chart(
        BarCategoricalSpec(
            viz_id="group.sentiment.session.demo",
            module="sentiment",
            name="demo_bar",
            scope="global",
            chart_intent="bar_categorical",
            title="Demo",
            x_label="x",
            y_label="y",
            categories=["a"],
            values=[1.0],
        ),
        chart_type="bar",
    )
    arts = svc.get_artifacts()
    assert arts
    rel = arts[0]["relative_path"]
    meta = svc._artifact_metadata.get(rel) or {}
    assert "group_aggregate" in (meta.get("tags") or [])
    assert meta.get("agg_id") == "sentiment"
    assert meta.get("group_uuid") == "uuid-1"
    assert meta.get("viz_id") == "group.sentiment.session.demo"
    chart_root = group_root / "sentiment" / "charts"
    assert chart_root.exists()


def test_dynamics_speaker_sanitize_and_collision(tmp_path: Path) -> None:
    from types import SimpleNamespace

    struct = SimpleNamespace(
        global_data_dir=tmp_path / "g",
        global_charts_dir=tmp_path / "c",
        speaker_data_dir=tmp_path / "s",
    )
    ensure_dynamics_dirs(struct, include_speaker_data=True)
    assert sanitize_filename("") == "unnamed"
    paths = write_speaker_stats_files(
        struct,
        "pauses",
        {"Alice/Bob": {"n": 1}, "Alice_Bob": {"n": 2}},
    )
    safe_a = sanitize_filename("Alice/Bob")
    safe_b = sanitize_filename("Alice_Bob")
    if safe_a == safe_b:
        assert len({p.name for p in paths}) == 1
        data = json.loads(paths[-1].read_text(encoding="utf-8"))
        assert data["n"] == 2
    else:
        assert len(paths) == 2


def test_pauses_failure_injection_events_before_stats(
    transcript_path: Path, tmp_path: Path
) -> None:
    svc = create_output_service(
        str(transcript_path), "pauses", output_dir=str(tmp_path)
    )
    ensure_dynamics_dirs(svc.get_output_structure(), include_speaker_data=True)
    with patch(
        "transcriptx.core.analysis.dynamics.artifact_io.save_json",
        side_effect=RuntimeError("injected stats failure"),
    ):
        with pytest.raises(RuntimeError, match="injected stats failure"):
            write_events_and_stats(
                svc.get_output_structure(),
                "pauses",
                [],
                {"total_gaps": 0},
            )
    gdir = Path(svc.get_output_structure().global_data_dir)
    assert (gdir / "pauses.events.json").exists()
    assert not (gdir / "pauses.stats.json").exists()


def test_group_factory_failure_injection(tmp_path: Path) -> None:
    group_root = tmp_path / "group_run"
    group_root.mkdir()
    ts = TranscriptSet.create([str(tmp_path / "a.json")])
    ctx = GroupChartContext(
        group_run_root=group_root,
        group_run_id="run-1",
        agg_id="stats",
        transcript_set=ts,
        group_uuid=None,
    )
    svc = make_group_output_service(ctx, module_name="stats", agg_id="stats")

    with patch.object(svc, "save_chart", side_effect=RuntimeError("chart boom")):
        gen = GenericNumericGroupChartGenerator("stats")
        outcome = {
            "session_rows": [
                {"order_index": 0, "session_label": "S1", "word_count": 10},
                {"order_index": 1, "session_label": "S2", "word_count": 20},
            ]
        }
        # Generator builds its own svc; patch at factory level
        with patch(
            "transcriptx.core.analysis.group_charts.generic_numeric.make_group_output_service",
            return_value=svc,
        ):
            with pytest.raises(RuntimeError, match="chart boom"):
                gen.generate(ctx, outcome)


def test_csv_compared_as_parsed_rows(transcript_path: Path, tmp_path: Path) -> None:
    from transcriptx.core.analysis.affect.output_helpers import save_rows_json_csv

    svc = create_output_service(
        str(transcript_path), "sentiment", output_dir=str(tmp_path)
    )
    rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    _, csv_path = save_rows_json_csv(svc, rows, "sentiment")
    parsed = _parse_csv(Path(csv_path))
    assert parsed[0] == ["a", "b"]
    assert parsed[1] == ["1", "2"]
    assert parsed[2] == ["3", "4"]


def test_entity_sentiment_write_order_is_csv_then_json_documented() -> None:
    """Guard: entity_sentiment must not use JSON-first save_rows_json_csv."""
    src_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "transcriptx"
        / "core"
        / "analysis"
        / "entity_sentiment"
        / "__init__.py"
    )
    src = src_path.read_text(encoding="utf-8")
    assert "save_rows_json_csv" not in src
    idx_csv = src.index('format_type="csv"')
    idx_json = src.index('format_type="json"')
    assert idx_csv < idx_json
