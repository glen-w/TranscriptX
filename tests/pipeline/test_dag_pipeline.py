"""
Unit tests for transcriptx.core.pipeline.dag_pipeline (DAGPipeline, helpers).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.domain.module_requirements import Requirement
from transcriptx.core.pipeline.dag_pipeline import (
    DAGPipeline,
    ModuleExecOutcome,
    create_dag_pipeline,
    run_dag_pipeline,
)
from transcriptx.core.pipeline.module_registry import ModuleInfo
from transcriptx.core.pipeline.dag_pipeline_finalize import finalize_execution_results
from transcriptx.core.utils.run_report import ModuleResult, RunReport
from transcriptx.io.speaker_map_resolver import sidecar_path_for


def _minimal_module_info(
    *,
    name: str = "stub",
    requires_multiple_speakers: bool = False,
    min_named_speakers: int = 1,
    gate_on_turn_taking_speakers: bool = False,
) -> ModuleInfo:
    return ModuleInfo(
        name=name,
        description="stub",
        category="light",
        dependencies=[],
        determinism_tier="T0",
        requirements=[Requirement.SEGMENTS],
        enhancements=[],
        requires_multiple_speakers=requires_multiple_speakers,
        min_named_speakers=min_named_speakers,
        gate_on_turn_taking_speakers=gate_on_turn_taking_speakers,
    )


def _patch_execute_io_and_context():
    return (
        # Must patch where PipelineContext is referenced for execute_pipeline
        # (dag_pipeline_run imports the class by name).
        patch("transcriptx.core.pipeline.dag_pipeline_run.PipelineContext"),
        patch("transcriptx.core.pipeline.dag_pipeline.validate_transcript_file"),
        patch("transcriptx.core.pipeline.dag_pipeline.validate_output_directory"),
    )


class TestComputeReviewBeforeRun:
    def test_compute_review_returns_dict(self, tmp_path, temp_transcript_file):
        p = DAGPipeline()
        p.add_module("alpha", "A", "light", [], MagicMock())
        p.finalize()
        out = str(tmp_path / "out")
        r = p.compute_review_before_run(
            transcript_path=str(temp_transcript_file),
            selected_modules=["alpha"],
            output_dir=out,
        )
        assert isinstance(r, dict)
        assert r["transcript_name"] == temp_transcript_file.name
        assert r["output_dir"] == out
        assert sidecar_path_for(temp_transcript_file).name == (
            f"{temp_transcript_file.stem}.speaker_map.json"
        )
        assert "modules_will_run" in r and "modules_skipped" in r
        assert "alpha" in r["modules_will_run"]

    def test_compute_review_dependency_failure_returns_skipped(
        self, tmp_path, temp_transcript_file
    ):
        p = DAGPipeline()
        p.add_module("x", "X", "light", [], MagicMock())
        p.finalize()
        with patch.object(
            p, "resolve_dependencies", side_effect=ValueError("unresolvable")
        ):
            r = p.compute_review_before_run(
                transcript_path=str(temp_transcript_file),
                selected_modules=["x"],
                output_dir=str(tmp_path / "out"),
            )
        assert r["modules_will_run"] == []
        assert any(
            s.get("reason") == "dependency resolution failed"
            for s in r["modules_skipped"]
        )


class TestCreateDAGPipeline:
    def test_create_dag_pipeline(self):
        dag = create_dag_pipeline()
        assert isinstance(dag, DAGPipeline)
        assert len(dag.nodes) > 0
        assert "sentiment" in dag.nodes or "stats" in dag.nodes

    def test_create_dag_pipeline_uses_shared_registry_accessor(self):
        with patch(
            "transcriptx.core.pipeline.dag_pipeline.get_module_registry"
        ) as mock_get:
            fake_registry = MagicMock()
            fake_registry.get_available_modules.return_value = []
            mock_get.return_value = fake_registry
            create_dag_pipeline()
        mock_get.assert_called_once()


class TestDAGPipeline:
    def test_add_module(self):
        p = DAGPipeline()
        fn = MagicMock()
        p.add_module("m1", "desc", "light", [], fn)
        assert "m1" in p.nodes
        assert p.nodes["m1"].function is fn
        assert p.nodes["m1"].category == "light"

    def test_resolve_dependencies_no_deps(self):
        p = DAGPipeline()
        p.add_module("a", "A", "light", [], MagicMock())
        p.add_module("b", "B", "medium", [], MagicMock())
        order = p.resolve_dependencies(["b", "a"])
        assert set(order) == {"a", "b"}

    def test_resolve_dependencies_with_deps(self):
        p = DAGPipeline()
        p.add_module("base", "B", "light", [], MagicMock())
        p.add_module("top", "T", "medium", ["base"], MagicMock())
        order = p.resolve_dependencies(["top"])
        assert order.index("base") < order.index("top")

    def test_resolve_dependencies_transitive(self):
        p = DAGPipeline()
        p.add_module("l1", "L1", "light", [], MagicMock())
        p.add_module("l2", "L2", "medium", ["l1"], MagicMock())
        p.add_module("l3", "L3", "heavy", ["l2"], MagicMock())
        order = p.resolve_dependencies(["l3"])
        assert order == ["l1", "l2", "l3"]

    def test_resolve_dependencies_multiple_dependents(self):
        p = DAGPipeline()
        p.add_module("core", "C", "light", [], MagicMock())
        p.add_module("d1", "D1", "medium", ["core"], MagicMock())
        p.add_module("d2", "D2", "medium", ["core"], MagicMock())
        order = p.resolve_dependencies(["d1", "d2"])
        assert order.index("core") < order.index("d1")
        assert order.index("core") < order.index("d2")

    def test_resolve_dependencies_complex_chain(self):
        p = DAGPipeline()
        for name, deps in [
            ("m0", []),
            ("m1", ["m0"]),
            ("m2", ["m0"]),
            ("m3", ["m1", "m2"]),
        ]:
            p.add_module(name, name, "light", deps, MagicMock())
        order = p.resolve_dependencies(["m3"])
        assert order.index("m0") < order.index("m1")
        assert order.index("m0") < order.index("m2")
        assert order.index("m1") < order.index("m3")
        assert order.index("m2") < order.index("m3")

    def test_sort_by_category(self):
        p = DAGPipeline()
        p.add_module("h", "H", "heavy", [], MagicMock())
        p.add_module("l", "L", "light", [], MagicMock())
        p.add_module("med", "M", "medium", [], MagicMock())
        modules = ["h", "med", "l"]
        sorted_m = p.sort_by_category(modules)
        assert sorted_m[0] == "l" and sorted_m[1] == "med" and sorted_m[2] == "h"

    def test_topological_sort_cycle_detection(self):
        p = DAGPipeline()
        p.add_module("a", "A", "light", ["b"], MagicMock())
        p.add_module("b", "B", "light", ["a"], MagicMock())
        with pytest.raises(ValueError, match="Circular dependency"):
            p.topological_sort(["a", "b"])

    def test_execute_pipeline_invalid_transcript(self, tmp_path):
        p = DAGPipeline()
        p.add_module("x", "X", "light", [], MagicMock())
        p.finalize()
        bad = tmp_path / "bad.txt"
        bad.write_text("{}")
        ctx = MagicMock()
        r = p.execute_pipeline(
            transcript_path=str(bad),
            selected_modules=["x"],
            output_dir=str(tmp_path / "o"),
            context=ctx,
            named_speaker_count=1,
        )
        assert r.get("status") == "failed" or r["errors"]

    def test_execute_pipeline_missing_dependency_error_message(self):
        p = DAGPipeline()
        p.add_module("orphan", "O", "light", ["not_registered"], MagicMock())
        with pytest.raises(ValueError, match="Missing dependencies"):
            p.resolve_dependencies(["orphan"])

    def test_execute_pipeline_success(self, tmp_path, temp_transcript_file):
        p = DAGPipeline()
        mod_fn = MagicMock()
        p.add_module("only", "Only", "light", [], mod_fn)
        p.finalize()
        sp = {"SPEAKER_00": "A", "SPEAKER_01": "B"}
        ctx_cm = _patch_execute_io_and_context()
        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A", "text": "t"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            r = p.execute_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["only"],
                output_dir=str(tmp_path / "out"),
                context=mc,
                named_speaker_count=2,
            )
        assert "only" in r["execution_order"]
        assert "only" in r["modules_run"]
        assert mod_fn.called

    def test_execute_pipeline_module_error(self, tmp_path, temp_transcript_file):
        p = DAGPipeline()
        p.add_module(
            "boom", "B", "light", [], MagicMock(side_effect=RuntimeError("no"))
        )
        p.finalize()
        sp = {"SPEAKER_00": "A", "SPEAKER_01": "B"}
        ctx_cm = _patch_execute_io_and_context()
        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            r = p.execute_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["boom"],
                output_dir=str(tmp_path / "out"),
                context=mc,
                named_speaker_count=2,
            )
        assert r["errors"]
        assert "boom" in r["execution_order"]

    def test_execute_pipeline_no_internal_parallel_warning(
        self, tmp_path, temp_transcript_file, caplog
    ):
        import logging

        caplog.set_level(logging.WARNING)
        p = DAGPipeline()
        p.add_module("p", "P", "light", [], MagicMock())
        p.finalize()
        sp = {"SPEAKER_00": "A", "SPEAKER_01": "B"}
        ctx_cm = _patch_execute_io_and_context()
        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            p.execute_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["p"],
                output_dir=str(tmp_path / "out"),
                context=mc,
                named_speaker_count=2,
            )
        assert not any(
            "parallel=True is ignored" in r.getMessage() for r in caplog.records
        )

    def test_execute_pipeline_skips_multi_speaker_module(
        self, tmp_path, temp_transcript_file
    ):
        p = DAGPipeline()
        p.add_module("multi_only", "M", "light", [], MagicMock())
        p.finalize()
        sp = {"SPEAKER_00": "A", "SPEAKER_01": "B"}
        info = _minimal_module_info(name="multi_only", requires_multiple_speakers=True)
        ctx_cm = _patch_execute_io_and_context()
        with (
            ctx_cm[0] as mock_ctx_cls,
            ctx_cm[1],
            ctx_cm[2],
            patch(
                "transcriptx.core.pipeline.module_registry.get_module_info",
                return_value=info,
            ),
            patch(
                "transcriptx.core.pipeline.dag_pipeline_run.gating_named_speaker_count",
                return_value=1,
            ),
        ):
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "OnlyOne"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            r = p.execute_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["multi_only"],
                output_dir=str(tmp_path / "out"),
                context=mc,
                named_speaker_count=1,
            )
        skipped = {x["module"] for x in r["skipped_modules"]}
        assert "multi_only" in skipped

    def test_execute_pipeline_runs_ungated_module_on_diarized_speakers(
        self, tmp_path, temp_transcript_file
    ):
        """When ungated, diarized (un-named) speakers count so the module runs."""
        p = DAGPipeline()
        p.add_module("turn_only", "T", "light", [], MagicMock())
        p.finalize()
        sp = {"SPEAKER_00": "SPEAKER_00", "SPEAKER_01": "SPEAKER_01"}
        info = _minimal_module_info(
            name="turn_only",
            requires_multiple_speakers=True,
        )
        diarized_segments = [
            {"speaker": "SPEAKER_00", "text": "first turn here"},
            {"speaker": "SPEAKER_01", "text": "second turn here"},
        ]
        ctx_cm = _patch_execute_io_and_context()
        with (
            ctx_cm[0] as mock_ctx_cls,
            ctx_cm[1],
            ctx_cm[2],
            patch(
                "transcriptx.core.pipeline.module_registry.get_module_info",
                return_value=info,
            ),
            patch(
                "transcriptx.core.pipeline.dag_pipeline_run.gating_named_speaker_count",
                return_value=0,
            ),
        ):
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = diarized_segments
            mc.get_speaker_map.return_value = sp
            mc.get_runtime_flags.return_value = {"allow_unnamed_speakers": True}
            mock_ctx_cls.return_value = mc
            r = p.execute_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["turn_only"],
                output_dir=str(tmp_path / "out"),
                context=mc,
                named_speaker_count=0,
            )
        skipped = {x["module"] for x in r["skipped_modules"]}
        assert "turn_only" not in skipped

    def test_execute_pipeline_skips_diarized_when_not_ungated(
        self, tmp_path, temp_transcript_file
    ):
        """Without ungate, diarized-only transcripts skip named-speaker modules."""
        p = DAGPipeline()
        p.add_module("named_only", "N", "light", [], MagicMock())
        p.finalize()
        sp = {"SPEAKER_00": "SPEAKER_00", "SPEAKER_01": "SPEAKER_01"}
        info = _minimal_module_info(name="named_only", min_named_speakers=1)
        diarized_segments = [
            {"speaker": "SPEAKER_00", "text": "first turn here"},
            {"speaker": "SPEAKER_01", "text": "second turn here"},
        ]
        ctx_cm = _patch_execute_io_and_context()
        with (
            ctx_cm[0] as mock_ctx_cls,
            ctx_cm[1],
            ctx_cm[2],
            patch(
                "transcriptx.core.pipeline.module_registry.get_module_info",
                return_value=info,
            ),
            patch(
                "transcriptx.core.pipeline.dag_pipeline_run.gating_named_speaker_count",
                return_value=0,
            ),
        ):
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = diarized_segments
            mc.get_speaker_map.return_value = sp
            mc.get_runtime_flags.return_value = {"allow_unnamed_speakers": False}
            mock_ctx_cls.return_value = mc
            r = p.execute_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["named_only"],
                output_dir=str(tmp_path / "out"),
                context=mc,
                named_speaker_count=0,
            )
        skipped = {x["module"] for x in r["skipped_modules"]}
        assert "named_only" in skipped

    def test_execute_pipeline_skips_ungated_module_single_speaker(
        self, tmp_path, temp_transcript_file
    ):
        """Ungated multi-speaker module still skips a single-speaker transcript."""
        p = DAGPipeline()
        p.add_module("turn_only", "T", "light", [], MagicMock())
        p.finalize()
        sp = {"SPEAKER_00": "SPEAKER_00"}
        info = _minimal_module_info(
            name="turn_only",
            requires_multiple_speakers=True,
        )
        single_speaker_segments = [
            {"speaker": "SPEAKER_00", "text": "first turn here"},
            {"speaker": "SPEAKER_00", "text": "second turn here"},
        ]
        ctx_cm = _patch_execute_io_and_context()
        with (
            ctx_cm[0] as mock_ctx_cls,
            ctx_cm[1],
            ctx_cm[2],
            patch(
                "transcriptx.core.pipeline.module_registry.get_module_info",
                return_value=info,
            ),
            patch(
                "transcriptx.core.pipeline.dag_pipeline_run.gating_named_speaker_count",
                return_value=0,
            ),
        ):
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = single_speaker_segments
            mc.get_speaker_map.return_value = sp
            mc.get_runtime_flags.return_value = {"allow_unnamed_speakers": True}
            mock_ctx_cls.return_value = mc
            r = p.execute_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["turn_only"],
                output_dir=str(tmp_path / "out"),
                context=mc,
                named_speaker_count=0,
            )
        skipped = {x["module"] for x in r["skipped_modules"]}
        assert "turn_only" in skipped


class TestDAGPipelineEdgeCases:
    def test_deterministic_ordering(self):
        p = DAGPipeline()
        assert p._make_deterministic(["z", "a", "m"]) == ["a", "m", "z"]

    def test_cycle_detection_direct(self):
        p = DAGPipeline()
        p.add_module("a", "A", "light", ["b"], MagicMock())
        p.add_module("b", "B", "light", ["a"], MagicMock())
        with pytest.raises(ValueError, match="Circular dependency"):
            p.resolve_dependencies(["a"])

    def test_cycle_detection_transitive(self):
        p = DAGPipeline()
        p.add_module("a", "A", "light", ["c"], MagicMock())
        p.add_module("b", "B", "light", ["a"], MagicMock())
        p.add_module("c", "C", "light", ["b"], MagicMock())
        with pytest.raises(ValueError, match="Circular dependency"):
            p.resolve_dependencies(["a"])

    def test_circular_dependency_error(self):
        p = DAGPipeline()
        p.add_module("u", "U", "light", ["v"], MagicMock())
        p.add_module("v", "V", "light", ["u"], MagicMock())
        with pytest.raises(ValueError, match="Circular dependency"):
            p.resolve_dependencies(["u"])

    def test_implicit_dependencies(self):
        p = DAGPipeline()
        p.add_module("emotion", "E", "light", [], MagicMock())
        p.add_module("contagion", "C", "medium", [], MagicMock())
        order = p.resolve_dependencies(["contagion"])
        assert "emotion" in order
        assert order.index("emotion") < order.index("contagion")

    def test_missing_dependency_handling(self, tmp_path, temp_transcript_file):
        """When a dependency module fails, dependents report missing_dependencies."""
        p = DAGPipeline()
        p.add_module(
            "dep",
            "D",
            "light",
            [],
            MagicMock(side_effect=RuntimeError("dep failed")),
        )
        p.add_module("needs", "N", "light", ["dep"], MagicMock())
        p.finalize()
        sp = {"SPEAKER_00": "A", "SPEAKER_01": "B"}
        ctx_cm = _patch_execute_io_and_context()
        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            r = p.execute_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["dep", "needs"],
                output_dir=str(tmp_path / "out"),
                context=mc,
                named_speaker_count=2,
            )
        # Missing deps are non-fatal: recorded as blocked skips, not pipeline errors.
        assert not any("Missing dependencies" in e for e in r["errors"])
        skipped = r.get("skipped_modules") or []
        assert any(
            isinstance(s, dict)
            and s.get("module") == "needs"
            and s.get("execution_status") == "blocked"
            and (
                "Missing dependencies" in str(s.get("reason", ""))
                or "Dependency not satisfied" in str(s.get("reason", ""))
            )
            for s in skipped
        )

    def test_partial_execution_on_failure(self, tmp_path, temp_transcript_file):
        p = DAGPipeline()
        p.add_module("ok", "OK", "light", [], MagicMock())
        p.add_module("bad", "BAD", "light", [], MagicMock(side_effect=Exception("x")))
        p.add_module("after", "AF", "light", [], MagicMock())
        p.finalize()
        sp = {"SPEAKER_00": "A", "SPEAKER_01": "B"}
        ctx_cm = _patch_execute_io_and_context()
        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            r = p.execute_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["ok", "bad", "after"],
                output_dir=str(tmp_path / "out"),
                context=mc,
                named_speaker_count=2,
            )
        assert "bad" in r["execution_order"] and "after" in r["execution_order"]
        assert r["errors"]
        assert "after" in r["modules_run"]

    def test_large_dependency_graph(self):
        p = DAGPipeline()
        for i in range(20):
            deps = [f"n{i - 1}"] if i else []
            p.add_module(f"n{i}", f"N{i}", "light", deps, MagicMock())
        order = p.resolve_dependencies(["n19"])
        assert len(order) == 20
        for i in range(1, 20):
            assert order.index(f"n{i - 1}") < order.index(f"n{i}")

    def test_get_dependency_graph(self):
        p = DAGPipeline()
        p.add_module("a", "A", "light", [], MagicMock())
        p.add_module("b", "B", "light", ["a"], MagicMock())
        g = p.get_dependency_graph(["b"])
        assert g["b"] == ["a"]
        assert g["a"] == []

    def test_check_missing_dependencies(self):
        p = DAGPipeline()
        p.add_module("d", "D", "light", [], MagicMock())
        node = p.nodes["d"]
        assert p._check_missing_dependencies(node, []) == []

    def test_category_ordering_enforcement(self):
        p = DAGPipeline()
        p.add_module("heavy_first", "H", "heavy", [], MagicMock())
        p.add_module("light_second", "L", "light", [], MagicMock())
        order = p.resolve_dependencies(["heavy_first", "light_second"])
        assert order[0] == "light_second"
        assert order[1] == "heavy_first"

    def test_preflight_check(self, tmp_path, temp_transcript_file):
        p = DAGPipeline()
        p.add_module("pf", "P", "light", [], MagicMock())
        p.finalize()
        pre = p.preflight_check(["pf"])
        assert "all_importable" in pre
        assert isinstance(pre["warnings"], list)

    def test_preflight_check_missing_module(self):
        p = DAGPipeline()
        p.finalize()
        pre = p.preflight_check(["not_there"])
        assert "not_there" in pre["skipped_modules"]

    def test_finalize_registry(self):
        p = DAGPipeline()
        p.add_module("a", "A", "light", [], MagicMock())
        p.finalize()
        assert p._finalized

    def test_finalize_with_errors(self):
        p = DAGPipeline()
        p.add_module("bad", "B", "light", ["missing"], MagicMock())
        with pytest.raises(ValueError, match="validation failed|Missing"):
            p.finalize()

    def test_validate_dependencies_success(self):
        p = DAGPipeline()
        p.add_module("v", "V", "light", [], MagicMock())
        ok, errs = p.validate_dependencies()
        assert ok and not errs

    def test_validate_dependencies_missing(self):
        p = DAGPipeline()
        p.add_module("v", "V", "light", ["ghost"], MagicMock())
        ok, errs = p.validate_dependencies()
        assert not ok
        assert any("not registered" in e for e in errs)

    def test_validate_dependencies_cycle(self):
        p = DAGPipeline()
        p.add_module("a", "A", "light", ["b"], MagicMock())
        p.add_module("b", "B", "light", ["a"], MagicMock())
        ok, errs = p.validate_dependencies()
        assert not ok
        assert any("Circular" in e for e in errs)

    def test_execute_pipeline_sequential_with_injected_context(
        self, tmp_path, temp_transcript_file
    ):
        p = DAGPipeline()
        p.add_module("s", "S", "light", [], MagicMock())
        p.finalize()
        sp = {"SPEAKER_00": "A", "SPEAKER_01": "B"}
        ctx_cm = _patch_execute_io_and_context()
        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            r = p.execute_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["s"],
                output_dir=str(tmp_path / "out"),
                context=mc,
                named_speaker_count=2,
            )
        assert "s" in r["modules_run"]

    def test_timeout_per_module(self):
        p = DAGPipeline()
        p.add_module("t", "T", "light", [], MagicMock(), timeout_seconds=123)
        assert p.nodes["t"].timeout_seconds == 123


class TestSortByCategory:
    def test_sort_by_category_light_before_medium_before_heavy(self):
        p = DAGPipeline()
        p.add_module("heavy_m", "H", "heavy", [], MagicMock())
        p.add_module("light_m", "L", "light", [], MagicMock())
        p.add_module("med_m", "M", "medium", [], MagicMock())
        out = p.sort_by_category(["heavy_m", "med_m", "light_m"])
        assert out == ["light_m", "med_m", "heavy_m"]

    def test_sort_by_category_preserves_dependency_order(self):
        p = DAGPipeline()
        p.add_module("base", "B", "heavy", [], MagicMock())
        p.add_module(
            "dep", "D", "light", ["base"], MagicMock()
        )  # depends on heavy — base runs first
        out = p.sort_by_category(["dep", "base"])
        assert out.index("base") < out.index("dep")


class TestRunDAGPipeline:
    def test_run_dag_pipeline_delegates_to_dag(self, tmp_path, temp_transcript_file):
        with (
            patch(
                "transcriptx.core.pipeline.dag_pipeline.create_dag_pipeline"
            ) as mock_create,
            patch(
                "transcriptx.core.pipeline.dag_pipeline.resolve_output_dir_for_run",
                return_value=str(tmp_path / "out"),
            ),
            patch(
                "transcriptx.core.pipeline.dag_pipeline.build_execute_pipeline_context"
            ) as mock_build_context,
        ):
            dag = MagicMock()
            context = MagicMock()
            mock_build_context.return_value = (context, 2)
            dag.execute_pipeline.return_value = {"ok": True}
            mock_create.return_value = dag
            r = run_dag_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment"],
            )
            assert r == {"ok": True}
            dag.execute_pipeline.assert_called_once()
            kw = dag.execute_pipeline.call_args.kwargs
            assert kw["transcript_path"] == str(temp_transcript_file)
            assert kw["selected_modules"] == ["sentiment"]
            assert kw["context"] is context
            assert kw["named_speaker_count"] == 2
            context.close.assert_called_once()


class TestExecutePipelineFakeDAG:
    @pytest.fixture
    def pipeline(self):
        p = DAGPipeline()
        p.add_module("m", "Mod", "light", [], MagicMock())
        p.finalize()
        return p

    def test_should_abort_pipeline_returns_true_for_speaker_map_error(self, pipeline):
        out = ModuleExecOutcome(
            status="failed",
            error="No speaker map available for this transcript",
        )
        assert pipeline._should_abort_pipeline(out, {"errors": []}) is True

    def test_should_abort_pipeline_returns_false_for_other_error(self, pipeline):
        out = ModuleExecOutcome(status="failed", error="Some random failure")
        assert pipeline._should_abort_pipeline(out, {"errors": []}) is False

    def test_reduce_module_outcome_has_no_side_effect_calls(self, pipeline):
        results = {
            "module_results": {},
            "modules_run": [],
            "skipped_modules": [],
            "errors": [],
            "cache_hits": [],
        }
        outcome = ModuleExecOutcome(
            status="success", module_result={"status": "success"}
        )
        with (
            patch("transcriptx.core.pipeline.dag_pipeline.notify_user") as mock_notify,
            patch(
                "transcriptx.core.pipeline.dag_pipeline.log_analysis_complete"
            ) as mock_log_ok,
            patch(
                "transcriptx.core.pipeline.dag_pipeline.log_analysis_error"
            ) as mock_log_err,
        ):
            pipeline._reduce_module_outcome("m", outcome, results)
        assert "m" in results["modules_run"]
        mock_notify.assert_not_called()
        mock_log_ok.assert_not_called()
        mock_log_err.assert_not_called()

    def test_success_path_records_in_results_and_run_report(
        self, tmp_path, temp_transcript_file, pipeline
    ):
        sp = {"SPEAKER_00": "A", "SPEAKER_01": "B"}
        rr = RunReport(transcript_hash="h", run_id="r")
        success = ModuleExecOutcome(
            status="success",
            module_result={"status": "success"},
            duration_ms=10.0,
        )
        ctx_cm = _patch_execute_io_and_context()
        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            with patch.object(pipeline, "_execute_single_module", return_value=success):
                r = pipeline.execute_pipeline(
                    transcript_path=str(temp_transcript_file),
                    selected_modules=["m"],
                    output_dir=str(tmp_path / "out"),
                    run_report=rr,
                    context=mc,
                    named_speaker_count=2,
                )
        assert "m" in r["modules_run"]
        assert rr.modules["m"].status == ModuleResult.RUN

    def test_exception_path_records_error_and_run_report_fail(
        self, tmp_path, temp_transcript_file, pipeline
    ):
        sp = {"SPEAKER_00": "A", "SPEAKER_01": "B"}
        rr = RunReport(transcript_hash="h", run_id="r")
        fail = ModuleExecOutcome(
            status="failed",
            error="boom",
            duration_ms=1.0,
        )
        ctx_cm = _patch_execute_io_and_context()
        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            with patch.object(pipeline, "_execute_single_module", return_value=fail):
                r = pipeline.execute_pipeline(
                    transcript_path=str(temp_transcript_file),
                    selected_modules=["m"],
                    output_dir=str(tmp_path / "out"),
                    run_report=rr,
                    context=mc,
                    named_speaker_count=2,
                )
        assert r["errors"]
        assert rr.modules["m"].status == ModuleResult.FAIL

    def test_abort_logic_stops_loop_on_critical_error(
        self, tmp_path, temp_transcript_file
    ):
        p = DAGPipeline()
        p.add_module("m", "M", "light", [], MagicMock())
        p.add_module("m2", "M2", "light", [], MagicMock())
        p.finalize()
        sp = {"SPEAKER_00": "A", "SPEAKER_01": "B"}
        crit = ModuleExecOutcome(
            status="failed",
            error="Speaker mapping required before analysis",
        )
        ok = ModuleExecOutcome(status="success", module_result={}, duration_ms=1.0)
        ctx_cm = _patch_execute_io_and_context()
        seq = [crit, ok]

        def _side_effect(*_a, **_k):
            return seq.pop(0) if seq else ok

        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            with patch.object(p, "_execute_single_module", side_effect=_side_effect):
                r = p.execute_pipeline(
                    transcript_path=str(temp_transcript_file),
                    selected_modules=["m", "m2"],
                    output_dir=str(tmp_path / "out"),
                    context=mc,
                    named_speaker_count=2,
                )
        # Critical abort maps to pipeline status "aborted" (not "failed").
        assert r.get("status") == "aborted"
        assert "m2" not in r["modules_run"]

    def test_event_collector_records_module_started_completed(
        self, tmp_path, temp_transcript_file, pipeline
    ):
        sp = {"SPEAKER_00": "A", "SPEAKER_01": "B"}
        ev = ModuleExecOutcome(status="success", module_result={}, duration_ms=5.0)
        ctx_cm = _patch_execute_io_and_context()
        events: list = []
        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            with patch.object(pipeline, "_execute_single_module", return_value=ev):
                pipeline.execute_pipeline(
                    transcript_path=str(temp_transcript_file),
                    selected_modules=["m"],
                    output_dir=str(tmp_path / "out"),
                    event_collector=events,
                    context=mc,
                    named_speaker_count=2,
                )
        kinds = [e.get("event") for e in events]
        assert "run_started" in kinds
        assert "module_started" in kinds
        assert "module_completed" in kinds


class TestOnEventCallback:
    def test_on_event_receives_events(self, tmp_path, temp_transcript_file):
        p = DAGPipeline()
        p.add_module("e", "E", "light", [], MagicMock())
        p.finalize()
        sp = {"SPEAKER_00": "A", "SPEAKER_01": "B"}
        received: list = []
        ctx_cm = _patch_execute_io_and_context()
        ev = ModuleExecOutcome(status="success", module_result={}, duration_ms=3.0)
        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            with patch.object(p, "_execute_single_module", return_value=ev):
                p.execute_pipeline(
                    transcript_path=str(temp_transcript_file),
                    selected_modules=["e"],
                    output_dir=str(tmp_path / "out"),
                    on_event=lambda d: received.append(d),
                    context=mc,
                    named_speaker_count=2,
                )
        assert any(x.get("event") == "run_started" for x in received)

    def test_on_event_exception_swallowed(self, tmp_path, temp_transcript_file):
        p = DAGPipeline()
        p.add_module("e2", "E2", "light", [], MagicMock())
        p.finalize()
        sp = {"SPEAKER_00": "A", "SPEAKER_01": "B"}
        ctx_cm = _patch_execute_io_and_context()
        ev = ModuleExecOutcome(status="success", module_result={}, duration_ms=3.0)

        def boom(_d):
            raise RuntimeError("cb")

        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            with patch.object(p, "_execute_single_module", return_value=ev):
                r = p.execute_pipeline(
                    transcript_path=str(temp_transcript_file),
                    selected_modules=["e2"],
                    output_dir=str(tmp_path / "out"),
                    on_event=boom,
                    context=mc,
                    named_speaker_count=2,
                )
        assert "e2" in r["modules_run"]

    def test_context_none_builds_runtime_context(self, tmp_path, temp_transcript_file):
        p = DAGPipeline()
        p.add_module("e3", "E3", "light", [], MagicMock())
        p.finalize()
        ctx_cm = _patch_execute_io_and_context()
        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A"}]
            mc.get_speaker_map.return_value = {"SPEAKER_00": "A"}
            mock_ctx_cls.return_value = mc
            with (
                patch(
                    "transcriptx.core.pipeline.dag_pipeline.validate_transcript_file"
                ),
                patch(
                    "transcriptx.core.pipeline.dag_pipeline.validate_output_directory"
                ),
                patch.object(
                    p,
                    "_execute_single_module",
                    return_value=ModuleExecOutcome(status="success"),
                ),
            ):
                result = p.execute_pipeline(
                    transcript_path=str(temp_transcript_file),
                    selected_modules=["e3"],
                    output_dir=str(tmp_path / "out"),
                )
        assert "e3" in result["modules_run"]
        mock_ctx_cls.assert_called_once()

    def test_terminal_run_event_emitted_at_most_once_on_abort(
        self, tmp_path, temp_transcript_file
    ):
        p = DAGPipeline()
        p.add_module("crit", "Critical", "light", [], MagicMock())
        p.finalize()
        sp = {"SPEAKER_00": "A"}
        fail = ModuleExecOutcome(status="failed", error="Speaker mapping required")
        events: list = []
        ctx_cm = _patch_execute_io_and_context()
        with ctx_cm[0] as mock_ctx_cls, ctx_cm[1], ctx_cm[2]:
            mc = MagicMock()
            mc.validate.return_value = True
            mc.get_segments.return_value = [{"speaker": "A"}]
            mc.get_speaker_map.return_value = sp
            mock_ctx_cls.return_value = mc
            with patch.object(p, "_execute_single_module", return_value=fail):
                p.execute_pipeline(
                    transcript_path=str(temp_transcript_file),
                    selected_modules=["crit"],
                    output_dir=str(tmp_path / "out"),
                    event_collector=events,
                    context=mc,
                    named_speaker_count=1,
                )
        terminal_events = [
            e for e in events if e.get("event") in {"run_failed", "run_completed"}
        ]
        assert len(terminal_events) == 1


def test_finalize_execution_results_best_effort_when_sink_fails():
    results = {"start_time": 0.0, "errors": [], "modules_run": []}

    def _emit(_event):
        raise RuntimeError("sink failed")

    # Should never raise even when emit fails.
    out = finalize_execution_results(
        results=results,
        execution_order=[],
        aborted=False,
        setup_failed=False,
        total_modules=0,
        ev_completed=0,
        ev_skipped=0,
        ev_failed=0,
        emit=_emit,
    )
    assert "end_time" in out
