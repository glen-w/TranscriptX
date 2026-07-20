"""Gallery ↔ chart_descriptions linking contracts (GUI resolution path).

These tests catch key-mismatch / provenance bugs where inventory generates
descriptions but the Charts page cannot resolve them (wrong run_target_id,
folder module vs meta.module, missing source_run_id, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from transcriptx.core.analysis.chart_descriptions.chart_key import (
    build_chart_key_payload,
    build_logical_chart_id,
    chart_key_digest,
)
from transcriptx.core.analysis.chart_descriptions.inventory_builder import (
    build_logical_chart_inventory,
)
from transcriptx.core.analysis.chart_descriptions.resolve import (
    invalidate_resolver_cache,
    resolve_gallery_run_identity,
)
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services.artifact_service import (
    ArtifactService,
    clear_artifact_caches,
)
from transcriptx.web.services.chart_llm_description import (
    chart_key_for_gallery_artifact,
    resolve_chart_llm_description,
)
from tests.web.chart_llm_linking_support import (
    chart_artifact as _chart_artifact,
    seed_linking_fixture_run as _seed_linking_fixture_run,
    write_single_active as _write_single_active,
)

@pytest.mark.unit
def test_gallery_key_matches_transcript_inventory_provenance(tmp_path: Path) -> None:
    invalidate_resolver_cache()
    run_root = tmp_path / "20260720_run"
    run_root.mkdir()
    transcript_key = "sha256:abcdef"
    viz_id = "stats.foo.global"
    logical = build_logical_chart_id(
        module="stats",
        viz_id=viz_id,
        scope="global",
        speaker_identity=None,
        name="foo",
    )
    expected_key = chart_key_digest(
        build_chart_key_payload(
            run_target_id=transcript_key,
            logical_chart_id=logical,
            viz_id=viz_id,
            scope="global",
            speaker_identity=None,
            slice_identity=None,
            source_run_id=transcript_key,
            member_session_id=None,
        )
    )
    _write_single_active(
        run_root,
        run_target_id=transcript_key,
        run_kind="transcript",
        chart_key=expected_key,
        description="Momentum rose then fell.",
        viz_id=viz_id,
    )
    (run_root / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_root.name,
                "run_metadata": {"transcript_key": transcript_key},
            }
        ),
        encoding="utf-8",
    )

    target, kind = resolve_gallery_run_identity(run_root)
    assert target == transcript_key
    assert kind == "transcript"

    artifact = _chart_artifact(viz_id=viz_id)
    wrong = chart_key_for_gallery_artifact(
        artifact, run_target_id=run_root.name, run_kind="transcript"
    )
    assert wrong != expected_key

    key = chart_key_for_gallery_artifact(
        artifact, run_target_id=transcript_key, run_kind="transcript"
    )
    assert key == expected_key
    assert resolve_chart_llm_description(run_root, artifact) == "Momentum rose then fell."


@pytest.mark.unit
def test_gallery_key_group_aggregate_empty_source_run(tmp_path: Path) -> None:
    invalidate_resolver_cache()
    run_root = tmp_path / "group_run"
    run_root.mkdir()
    group_id = "370be99d-8d2c-4c23-9507-ff67856f3fae"
    viz_id = "group.sentiment.temporal_overlay.global"
    logical = build_logical_chart_id(
        module="sentiment",
        viz_id=viz_id,
        scope="global",
        speaker_identity=None,
        name="temporal_overlay",
    )
    expected_key = chart_key_digest(
        build_chart_key_payload(
            run_target_id=group_id,
            logical_chart_id=logical,
            viz_id=viz_id,
            scope="global",
            speaker_identity=None,
            slice_identity=None,
            source_run_id=None,
            member_session_id=None,
        )
    )
    _write_single_active(
        run_root,
        run_target_id=group_id,
        run_kind="group",
        chart_key=expected_key,
        description="Group overlay summary.",
        viz_id=viz_id,
    )
    artifact = Artifact(
        id="g1",
        kind="chart_static",
        module="sentiment",
        scope="global",
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path="sentiment/charts/global/static/temporal/temporal_overlay.png",
        bytes=10,
        mtime="0",
        mime="image/png",
        tags=["group_aggregate"],
        title="Overlay",
        meta={
            "viz_id": viz_id,
            "module": "sentiment",
            "scope": "global",
            "name": "temporal_overlay",
        },
    )
    key = chart_key_for_gallery_artifact(
        artifact, run_target_id=group_id, run_kind="group"
    )
    assert key == expected_key
    assert resolve_chart_llm_description(run_root, artifact) == "Group overlay summary."


@pytest.mark.unit
def test_gallery_key_prefers_meta_module_over_artifact_folder_label(
    tmp_path: Path,
) -> None:
    """Voice charts: gallery folder module is ``voice``, inventory uses meta module."""
    invalidate_resolver_cache()
    run_root = tmp_path / "voice_run"
    run_root.mkdir()
    transcript_key = "sha256:voicekey"
    viz_id = "voice.burstiness.speaker"
    inventory_module = "voice_charts_core"
    name = "burstiness__speaker__Ana"
    logical = build_logical_chart_id(
        module=inventory_module,
        viz_id=viz_id,
        scope="speaker",
        speaker_identity="Ana",
        name=name,
    )
    expected_key = chart_key_digest(
        build_chart_key_payload(
            run_target_id=transcript_key,
            logical_chart_id=logical,
            viz_id=viz_id,
            scope="speaker",
            speaker_identity="Ana",
            slice_identity=None,
            source_run_id=transcript_key,
            member_session_id=None,
        )
    )
    _write_single_active(
        run_root,
        run_target_id=transcript_key,
        run_kind="transcript",
        chart_key=expected_key,
        description="Ana speech burstiness rose mid-session.",
        viz_id=viz_id,
    )
    artifact = Artifact(
        id="voice_ana",
        kind="chart_static",
        module="voice",
        scope="speaker",
        speaker="Ana",
        subview=None,
        slice_id=None,
        rel_path="voice/v1/charts/speakers/Ana/static/burstiness/burstiness__speaker__Ana.png",
        bytes=10,
        mtime="0",
        mime="image/png",
        tags=["voice"],
        title="Burstiness",
        meta={
            "viz_id": viz_id,
            "module": inventory_module,
            "scope": "speaker",
            "speaker": "Ana",
            "name": name,
        },
    )
    wrong_if_folder_module = chart_key_digest(
        build_chart_key_payload(
            run_target_id=transcript_key,
            logical_chart_id=build_logical_chart_id(
                module="voice",
                viz_id=viz_id,
                scope="speaker",
                speaker_identity="Ana",
                name=name,
            ),
            viz_id=viz_id,
            scope="speaker",
            speaker_identity="Ana",
            slice_identity=None,
            source_run_id=transcript_key,
            member_session_id=None,
        )
    )
    assert wrong_if_folder_module != expected_key

    key = chart_key_for_gallery_artifact(
        artifact, run_target_id=transcript_key, run_kind="transcript"
    )
    assert key == expected_key
    assert (
        resolve_chart_llm_description(run_root, artifact)
        == "Ana speech burstiness rose mid-session."
    )


@pytest.mark.unit
def test_gallery_key_none_without_viz_id() -> None:
    """NER map images and other chart-like files without viz_id are not keyed."""
    artifact = Artifact(
        id="ner_map",
        kind="chart_static",
        module="ner",
        scope="global",
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path="ner/maps/images/session-locations-ALL.png",
        bytes=10,
        mtime="0",
        mime="image/png",
        tags=["ner"],
        title="Locations",
        meta={},
    )
    assert (
        chart_key_for_gallery_artifact(
            artifact, run_target_id="sha256:x", run_kind="transcript"
        )
        is None
    )


@pytest.mark.unit
def test_artifact_service_gallery_resolves_all_inventoried_charts(
    tmp_path: Path,
) -> None:
    """End-to-end: inventory → ACTIVE → ArtifactService gallery must link 1:1."""
    invalidate_resolver_cache()
    clear_artifact_caches()
    run = tmp_path / "20260720_link_run"
    run.mkdir()
    transcript_key = "sha256:linkfixture01"
    expected = _seed_linking_fixture_run(run, transcript_key=transcript_key)

    target, kind = resolve_gallery_run_identity(run)
    assert target == transcript_key
    assert kind == "transcript"

    gallery = [
        a
        for a in ArtifactService.list_artifacts(run)
        if a.kind in {"chart_static", "chart_dynamic"}
    ]
    # Folder label vs meta.module must diverge for voice (regression signal).
    voice = [a for a in gallery if (a.meta or {}).get("viz_id") == "voice.burstiness.speaker"]
    assert voice
    assert any(a.module == "voice" for a in voice)
    assert all((a.meta or {}).get("module") == "voice_charts_core" for a in voice)

    linkable = [
        a for a in gallery if isinstance((a.meta or {}).get("viz_id"), str)
    ]
    unmatched: list[str] = []
    for artifact in linkable:
        key = chart_key_for_gallery_artifact(
            artifact, run_target_id=target, run_kind=kind
        )
        text = resolve_chart_llm_description(run, artifact)
        if key not in expected or text != expected[key]:
            unmatched.append(
                f"{artifact.rel_path} module={artifact.module!r} "
                f"meta.module={(artifact.meta or {}).get('module')!r} "
                f"key={key} text={text!r}"
            )
    assert not unmatched, "gallery↔inventory key mismatches:\n" + "\n".join(unmatched)

    # Charts without viz_id stay unlinkable (NER maps).
    no_viz = [a for a in gallery if not (a.meta or {}).get("viz_id")]
    assert no_viz
    for artifact in no_viz:
        assert resolve_chart_llm_description(run, artifact) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "broken_kwargs,reason",
    [
        (
            {"run_target_id": "20260720_link_run", "source_run_id": "20260720_link_run"},
            "run_folder_id_instead_of_transcript_key",
        ),
        (
            {
                "run_target_id": "sha256:linkfixture01",
                "source_run_id": "",
            },
            "empty_source_run_id_for_transcript",
        ),
        (
            {
                "module": "voice",
            },
            "folder_module_instead_of_meta_module",
        ),
    ],
)
def test_known_bad_key_inputs_do_not_match_inventory(
    tmp_path: Path,
    broken_kwargs: dict[str, Any],
    reason: str,
) -> None:
    """Document mismatch vectors that previously hid LLM summaries in the GUI."""
    invalidate_resolver_cache()
    clear_artifact_caches()
    run = tmp_path / "20260720_link_run"
    run.mkdir()
    transcript_key = "sha256:linkfixture01"
    expected = _seed_linking_fixture_run(run, transcript_key=transcript_key)

    inventory, _ = build_logical_chart_inventory(
        run, run_kind="transcript", run_target_id=transcript_key
    )
    voice = next(c for c in inventory.charts if c.viz_id == "voice.burstiness.speaker")
    assert voice.chart_key in expected

    module = broken_kwargs.get("module", voice.module)
    run_target_id = broken_kwargs.get("run_target_id", transcript_key)
    if "source_run_id" in broken_kwargs:
        raw = broken_kwargs["source_run_id"]
        source_run_id = raw or None
    else:
        source_run_id = transcript_key

    logical = build_logical_chart_id(
        module=module,
        viz_id=voice.viz_id,
        scope=voice.scope,
        speaker_identity=voice.speaker,
        name="burstiness__speaker__Ana",
    )
    bad_key = chart_key_digest(
        build_chart_key_payload(
            run_target_id=run_target_id,
            logical_chart_id=logical,
            viz_id=voice.viz_id,
            scope=voice.scope,
            speaker_identity=voice.speaker,
            slice_identity=voice.slice_id,
            source_run_id=source_run_id,
            member_session_id=voice.member_session_id,
        )
    )
    assert bad_key != voice.chart_key, f"expected mismatch for {reason}"


@pytest.mark.unit
def test_charts_gallery_card_renders_llm_summary_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUI card path must surface resolved LLM text when the toggle is on."""
    invalidate_resolver_cache()
    run_root = tmp_path / "gui_card_run"
    run_root.mkdir()
    transcript_key = "sha256:guicard"
    viz_id = "stats.foo.global"
    logical = build_logical_chart_id(
        module="stats",
        viz_id=viz_id,
        scope="global",
        speaker_identity=None,
        name="foo",
    )
    expected_key = chart_key_digest(
        build_chart_key_payload(
            run_target_id=transcript_key,
            logical_chart_id=logical,
            viz_id=viz_id,
            scope="global",
            speaker_identity=None,
            slice_identity=None,
            source_run_id=transcript_key,
            member_session_id=None,
        )
    )
    llm_text = "GUI-visible LLM chart narrative."
    _write_single_active(
        run_root,
        run_target_id=transcript_key,
        run_kind="transcript",
        chart_key=expected_key,
        description=llm_text,
        viz_id=viz_id,
    )
    (run_root / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_root.name,
                "run_metadata": {"transcript_key": transcript_key},
            }
        ),
        encoding="utf-8",
    )

    captured: list[str] = []

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _DummySt:
        session_state: dict = {}

        @staticmethod
        def container(**_k):
            return _Ctx()

        @staticmethod
        def columns(_n):
            return [_Ctx()]

        @staticmethod
        def markdown(body, **_k):
            captured.append(str(body))

        @staticmethod
        def caption(*_a, **_k):
            return None

        @staticmethod
        def image(*_a, **_k):
            return None

        @staticmethod
        def button(*_a, **_k):
            return False

        @staticmethod
        def iframe(*_a, **_k):
            return None

    import transcriptx.web.page_modules.charts as charts_mod

    monkeypatch.setattr(charts_mod, "st", _DummySt)
    monkeypatch.setattr(
        charts_mod.ArtifactService,
        "generate_thumbnail",
        staticmethod(lambda *_a, **_k: None),
    )
    monkeypatch.setattr(
        charts_mod,
        "resolve_chart_display_description",
        lambda _a: None,
    )

    charts_mod._render_chart_gallery_card(
        run_root,
        _chart_artifact(viz_id=viz_id),
        "btn_test",
        show_registry_description=False,
        show_llm_summary=True,
    )
    assert llm_text in captured

    captured.clear()
    charts_mod._render_chart_gallery_card(
        run_root,
        _chart_artifact(viz_id=viz_id),
        "btn_test_off",
        show_registry_description=False,
        show_llm_summary=False,
    )
    assert llm_text not in captured
