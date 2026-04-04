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
    _topo_sort_entries,
)
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


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
