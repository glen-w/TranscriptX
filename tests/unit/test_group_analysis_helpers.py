"""Unit tests for group_analysis_runner helpers.

File name avoids the substring \"ner\" (e.g. \"runner\") in the path, which
tests/conftest.py would otherwise match to requires_models and skip.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.group_analysis_runner import (
    _attach_session_identity,
    _call_aggregate_fn,
    _row_payload,
    _topo_sort_entries,
    finalize_group_analysis,
)
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap
from transcriptx.core.pipeline.target_resolver import AnalysisScope
from transcriptx.core.utils.config import TranscriptXConfig


@pytest.mark.unit
class TestTopoSortEntries:
    def test_cycle_raises(self) -> None:
        a = SimpleNamespace(agg_id="a", deps=["b"])
        b = SimpleNamespace(agg_id="b", deps=["a"])
        with pytest.raises(ValueError, match="cyclic"):
            _topo_sort_entries([a, b])

    def test_respects_dependencies(self) -> None:
        a = SimpleNamespace(agg_id="a", deps=[])
        b = SimpleNamespace(agg_id="b", deps=["a"])
        c = SimpleNamespace(agg_id="c", deps=["b"])
        out = _topo_sort_entries([c, b, a])
        assert [x.agg_id for x in out] == ["a", "b", "c"]


@pytest.mark.unit
class TestAttachSessionIdentity:
    def test_resolves_transcript_path_first(self) -> None:
        pr = PerTranscriptResult(
            transcript_path="/x/a.json",
            transcript_key="k1",
            run_id="r1",
            order_index=2,
            output_dir="/o",
            module_results={},
        )
        ts = TranscriptSet.create(
            transcript_ids=["/x/a.json"],
            name="n",
            metadata={},
            key=None,
        )

        rows = [{"transcript_path": "/x/a.json"}]

        def fake_tid(r: PerTranscriptResult, t: TranscriptSet) -> str:
            return f"tid:{r.transcript_path}"

        out = _attach_session_identity(rows, [pr], ts, fake_tid)
        assert out[0]["order_index"] == 2
        assert out[0]["transcript_id"] == "tid:/x/a.json"

    def test_falls_back_to_order_index(self) -> None:
        pr = PerTranscriptResult(
            transcript_path="/p0",
            transcript_key="",
            run_id="r",
            order_index=1,
            output_dir="/o",
            module_results={},
        )
        ts = TranscriptSet.create(
            transcript_ids=["/p0"],
            name="n",
            metadata={},
            key=None,
        )

        rows = [{"order_index": 1}]

        out = _attach_session_identity(
            rows,
            [pr],
            ts,
            lambda r, t: 42,
        )
        assert out[0]["transcript_id"] == 42


@pytest.mark.unit
class TestCallAggregateFn:
    def test_three_arg_callable(self) -> None:
        csm = CanonicalSpeakerMap({}, {}, {})
        pr: list[PerTranscriptResult] = []
        ts = TranscriptSet.create(
            transcript_ids=[],
            name="n",
            metadata={},
            key=None,
        )
        aggregations: dict = {}

        def fn(a, b, c):
            return {"n": 3}

        assert _call_aggregate_fn(fn, pr, csm, ts, aggregations) == {"n": 3}

    def test_four_arg_callable(self) -> None:
        csm = CanonicalSpeakerMap({}, {}, {})
        pr = []
        ts = TranscriptSet.create(
            transcript_ids=[],
            name="n",
            metadata={},
            key=None,
        )
        aggregations = {"existing": 1}

        def fn(a, b, c, agg):
            return {"n": 4, "agg": agg}

        r = _call_aggregate_fn(fn, pr, csm, ts, aggregations)
        assert r == {"n": 4, "agg": aggregations}

    def test_varargs_callable_receives_aggregation_context(self) -> None:
        csm = CanonicalSpeakerMap({}, {}, {})
        pr = []
        ts = TranscriptSet.create(transcript_ids=[], name="n", metadata={}, key=None)
        aggregations = {"existing": 1}

        def fn(*args):
            return {"argc": len(args), "agg": args[-1]}

        r = _call_aggregate_fn(fn, pr, csm, ts, aggregations)
        assert r == {"argc": 4, "agg": aggregations}

    def test_uninspectable_callable_falls_back_to_three_args(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        csm = CanonicalSpeakerMap({}, {}, {})
        pr = []
        ts = TranscriptSet.create(transcript_ids=[], name="n", metadata={}, key=None)

        class CallableWithoutSignature:
            def __call__(self, a, b, c):
                return {"ok": True, "count": len((a, b, c))}

        monkeypatch.setattr(
            "transcriptx.core.pipeline.group_analysis_runner.inspect.signature",
            lambda _fn: (_ for _ in ()).throw(ValueError("no signature")),
        )

        r = _call_aggregate_fn(CallableWithoutSignature(), pr, csm, ts, {})
        assert r == {"ok": True, "count": 3}


@pytest.mark.unit
def test_row_payload_excludes_chart_only_and_unknown_keys() -> None:
    payload = _row_payload(
        {
            "session_rows": [{"session": 1}],
            "speaker_rows": [{"speaker": "A"}],
            "metrics_spec": {"x": "mean"},
            "content_rows": [{"text": "hi"}],
            "content_rows_name": "quotes",
            "drop_csv_keys": ["debug"],
            "pooled_wordcloud": {"chart": True},
            "unexpected": "ignored",
        }
    )
    assert payload == {
        "session_rows": [{"session": 1}],
        "speaker_rows": [{"speaker": "A"}],
        "metrics_spec": {"x": "mean"},
        "content_rows": [{"text": "hi"}],
        "content_rows_name": "quotes",
        "drop_csv_keys": ["debug"],
    }


@pytest.mark.unit
def test_finalize_group_analysis_disabled_writes_group_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    calls: dict[str, object] = {"saved_json": []}

    class FakeGroupOutputService:
        def __init__(
            self,
            *,
            group_uuid,
            run_id,
            output_dir,
            scaffold_by_session,
            scaffold_by_speaker,
            scaffold_comparisons,
        ):
            self.base_dir = tmp_path / "groups" / group_uuid / run_id
            self.base_dir.mkdir(parents=True)
            calls["service_init"] = {
                "group_uuid": group_uuid,
                "output_dir": output_dir,
                "scaffold_by_session": scaffold_by_session,
                "scaffold_by_speaker": scaffold_by_speaker,
                "scaffold_comparisons": scaffold_comparisons,
            }

        def write_group_run_metadata(self, **kwargs):
            calls["metadata"] = kwargs

        def save_summary(self, text):
            calls["summary"] = text

        def write_group_manifest(self, **kwargs):
            calls["manifest"] = kwargs

    def fake_save_json(payload, path):
        calls["saved_json"].append((payload, path))

    def fake_write_run_results_summary(**kwargs):
        calls["run_results"] = kwargs

    def fake_write_output_manifest(**kwargs):
        calls["output_manifest"] = kwargs

    monkeypatch.setattr(
        "transcriptx.core.pipeline.group_analysis_runner.GroupOutputService",
        FakeGroupOutputService,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.group_analysis_runner.save_json", fake_save_json
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.group_analysis_runner.write_run_results_summary",
        fake_write_run_results_summary,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.group_analysis_runner.write_output_manifest",
        fake_write_output_manifest,
    )

    config = TranscriptXConfig()
    config.group_analysis.enabled = False
    config.group_analysis.output_dir = str(tmp_path / "groups")
    scope = AnalysisScope(
        scope_type="group",
        uuid="group-uuid",
        key="group-key",
        display_name="Group Name",
    )
    member = SimpleNamespace(
        file_path="/tmp/a.json",
        file_name="a.json",
        id=7,
        uuid="member-uuid",
    )
    per_result = PerTranscriptResult(
        transcript_path="/tmp/a.json",
        transcript_key="tx",
        run_id="run-1",
        order_index=0,
        output_dir="/tmp/out",
        module_results={},
        modules_run=["stats"],
        skipped_modules=[],
    )

    result = finalize_group_analysis(
        scope=scope,
        members=[member],
        resolved_paths=["/tmp/a.json"],
        per_transcript_results=[per_result],
        group_errors=["member warning"],
        selected_modules=["stats", "sentiment"],
        config=config,
    )

    assert result["status"] == "completed"
    assert result["group_uuid"] == "group-uuid"
    assert (
        result["warning"]
        == "Group analysis is disabled in config; aggregation skipped."
    )
    assert calls["metadata"]["member_transcript_ids"] == [7]
    assert "Aggregation disabled" in calls["summary"]
    assert calls["manifest"]["transcript_file_uuids"] == ["member-uuid"]
    assert calls["run_results"]["modules_enabled"] == ["stats", "sentiment"]
    assert calls["run_results"]["modules_run"] == ["stats"]
    assert calls["run_results"]["errors"] == ["member warning"]
    assert calls["output_manifest"]["modules_enabled"] == ["stats", "sentiment"]
    member_payload, member_path = calls["saved_json"][0]
    assert member_path.endswith("group_member_runs.json")
    assert member_payload["members"][0]["transcript_key"] == "tx"


@pytest.mark.unit
def test_finalize_group_analysis_requires_group_scope() -> None:
    config = TranscriptXConfig()
    scope = AnalysisScope(
        scope_type="transcript",
        uuid="transcript-uuid",
        key="transcript-key",
        display_name="Single",
    )

    with pytest.raises(ValueError, match="Group scope is required"):
        finalize_group_analysis(
            scope=scope,
            members=[],
            resolved_paths=[],
            per_transcript_results=[],
            group_errors=[],
            selected_modules=[],
            config=config,
        )


@pytest.mark.unit
def test_finalize_group_analysis_enabled_runs_registry_rows_blobs_and_warnings(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    calls: dict[str, object] = {"saved_json": [], "rows": [], "charts": []}

    class FakeGroupOutputService:
        def __init__(self, *, group_uuid, run_id, output_dir, **_kwargs):
            self.base_dir = tmp_path / "groups" / group_uuid / run_id
            self.base_dir.mkdir(parents=True)

        def write_group_run_metadata(self, **kwargs):
            calls["metadata"] = kwargs

        def save_summary(self, text):
            calls["summary"] = text

        def write_group_manifest(self, **kwargs):
            calls["manifest"] = kwargs

    def fake_save_json(payload, path):
        calls["saved_json"].append((payload, path))

    def fake_write_run_results_summary(**kwargs):
        calls["run_results"] = kwargs

    def fake_write_output_manifest(**kwargs):
        calls["output_manifest"] = kwargs

    def fake_build_warning(**kwargs):
        return kwargs

    def fake_write_row_outputs(**kwargs):
        calls["rows"].append(kwargs)
        if kwargs["agg_id"] == "row_warn":
            return [], {
                "code": "ROW_WARN",
                "aggregation_key": "row_warn",
                "message": "row warning",
            }
        return ["rows.csv"], None

    def fake_run_group_aggregate_charts(**kwargs):
        calls["charts"].append(kwargs)
        if kwargs["agg_id"] == "row_chart_error":
            raise RuntimeError("chart boom")
        return SimpleNamespace(
            warnings=[
                {
                    "code": "GROUP_CHART_FAILED",
                    "aggregation_key": kwargs["agg_id"],
                    "message": "chart warning",
                }
            ]
        )

    def fake_merge_optional_chart_outcome_keys(chart_outcome, outcome):
        if "pooled" in outcome:
            chart_outcome["pooled"] = outcome["pooled"]

    monkeypatch.setattr(
        "transcriptx.core.pipeline.group_analysis_runner.GroupOutputService",
        FakeGroupOutputService,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.group_analysis_runner.save_json", fake_save_json
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.group_analysis_runner.write_run_results_summary",
        fake_write_run_results_summary,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.group_analysis_runner.write_output_manifest",
        fake_write_output_manifest,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.aggregation.registry.build_registry",
        lambda: [
            SimpleNamespace(
                agg_id="unselected",
                deps=[],
                selector=lambda _mods: False,
                aggregate_fn=lambda *_args: {"ignored": True},
                output_type="rows",
            ),
            SimpleNamespace(
                agg_id="missing_dep",
                deps=["not_done"],
                selector=lambda _mods: True,
                aggregate_fn=lambda *_args: {"ignored": True},
                output_type="rows",
            ),
            SimpleNamespace(
                agg_id="warning_outcome",
                deps=[],
                selector=lambda _mods: True,
                aggregate_fn=lambda *_args: {
                    "warning": {
                        "code": "AGG_WARN",
                        "aggregation_key": "warning_outcome",
                        "message": "aggregate warning",
                    }
                },
                output_type="rows",
            ),
            SimpleNamespace(
                agg_id="blob",
                deps=[],
                selector=lambda _mods: True,
                aggregate_fn=lambda *_args: {
                    "blob_name": "summary",
                    "blob_payload": {"ok": True},
                },
                output_type="blob",
            ),
            SimpleNamespace(
                agg_id="row_warn",
                deps=[],
                selector=lambda _mods: True,
                aggregate_fn=lambda *_args: {
                    "session_rows": [{"order_index": 0}],
                    "speaker_rows": [],
                    "metrics_spec": {},
                },
                output_type="rows",
            ),
            SimpleNamespace(
                agg_id="row_chart_error",
                deps=[],
                selector=lambda _mods: True,
                aggregate_fn=lambda *_args: {
                    "session_rows": [{"transcript_key": "tx"}],
                    "speaker_rows": [],
                    "metrics_spec": {},
                    "aggregation_warnings": [
                        {
                            "code": "INNER_WARN",
                            "aggregation_key": "row_chart_error",
                            "message": "inner",
                        }
                    ],
                    "pooled": {"kept": True},
                },
                output_type="rows",
            ),
            SimpleNamespace(
                agg_id="row_chart_ok",
                deps=[],
                selector=lambda _mods: True,
                aggregate_fn=lambda *_args: {
                    "session_rows": [{"session_path": "/tmp/a.json"}],
                    "speaker_rows": [],
                    "metrics_spec": {},
                },
                output_type="rows",
            ),
        ],
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.aggregation.schema.get_transcript_id",
        lambda result, _set: f"tid:{result.order_index}",
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.aggregation.warnings.build_warning",
        fake_build_warning,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.group_charts.runner.run_group_aggregate_charts",
        fake_run_group_aggregate_charts,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.chart_outcome.merge_optional_chart_outcome_keys",
        fake_merge_optional_chart_outcome_keys,
    )
    monkeypatch.setattr(
        "transcriptx.core.output.group_row_writer.write_row_outputs",
        fake_write_row_outputs,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.speaker_normalizer.normalize_speakers_across_transcripts",
        lambda _results: CanonicalSpeakerMap(
            transcript_to_speakers={"tx": {"A": 1}},
            canonical_to_display={1: "A"},
            transcript_to_display={"tx": {"A": "A"}},
        ),
    )

    config = TranscriptXConfig()
    config.group_analysis.enabled = True
    config.group_analysis.output_dir = str(tmp_path / "groups")
    scope = AnalysisScope(
        scope_type="group",
        uuid="group-uuid",
        key="group-key",
        display_name="Group Name",
    )
    member = SimpleNamespace(
        file_path="/tmp/a.json",
        file_name="a.json",
        id=7,
        uuid="member-uuid",
    )
    per_result = PerTranscriptResult(
        transcript_path="/tmp/a.json",
        transcript_key="tx",
        run_id="run-1",
        order_index=0,
        output_dir="/tmp/out",
        module_results={},
        modules_run=["stats"],
        skipped_modules=[],
    )

    result = finalize_group_analysis(
        scope=scope,
        members=[member],
        resolved_paths=["/tmp/a.json"],
        per_transcript_results=[per_result],
        group_errors=["terminal group note"],
        selected_modules=["stats"],
        config=config,
    )

    assert result["status"] == "completed"
    assert set(result["aggregations"]) == {"blob", "row_chart_error", "row_chart_ok"}
    assert result["canonical_speaker_map"]["canonical_to_display"] == {1: "A"}
    assert result["meta"]["warnings_count"] == 5
    assert result["group_phase_metadata"]["chart_failure_count"] == 1
    assert result["group_phase_metadata"]["terminal_errors"] == ["terminal group note"]
    assert calls["run_results"]["modules_run"] == ["stats"]
    assert calls["output_manifest"]["transcript_key"] == "group-uuid"
    assert {row_call["agg_id"] for row_call in calls["rows"]} == {
        "row_warn",
        "row_chart_error",
        "row_chart_ok",
    }
    assert {chart_call["agg_id"] for chart_call in calls["charts"]} == {
        "row_chart_error",
        "row_chart_ok",
    }
    warning_payloads = [
        payload
        for payload, path in calls["saved_json"]
        if str(path).endswith("aggregation_warnings.json")
    ]
    assert warning_payloads
    warning_codes = {warning["code"] for warning in warning_payloads[0]}
    assert {
        "MISSING_DEP",
        "AGG_WARN",
        "ROW_WARN",
        "INNER_WARN",
        "GROUP_CHART_FAILED",
    } <= warning_codes
