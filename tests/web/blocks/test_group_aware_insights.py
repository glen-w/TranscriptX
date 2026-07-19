"""Group-aware Insights / Overview block tests (no Streamlit runtime)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from transcriptx.web.blocks.availability import check_block_availability
from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.blocks.context import build_block_context
from transcriptx.web.blocks.implementations import insights as insights_blocks
from transcriptx.web.blocks.implementations import overview_curated as curated
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.blocks.registry import clear_registry_for_tests, get_block
from transcriptx.web.models.artifact import Artifact


def _ctx(run_root: Path, loader=None) -> SimpleNamespace:
    return SimpleNamespace(
        run_root=run_root,
        run_id="run",
        subject_id="group",
        run_results=None,
        services=SimpleNamespace(content_loader=loader),
        artifacts=(),
        health=None,
    )


def _placement(block_id: str = "highlights") -> BlockPlacement:
    return BlockPlacement(
        placement_id="p1",
        block_id=block_id,
        title_override=None,
        params={},
    )


def _artifact(module: str, rel_path: str) -> Artifact:
    return Artifact(
        id=rel_path,
        kind="data_json",
        module=module,
        scope=None,
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path=rel_path,
        bytes=1,
        mtime="",
        mime="application/json",
        tags=[],
    )


def _write_group_meta(run: Path, *, members: list[dict] | None = None) -> None:
    (run / "group_run_metadata.json").write_text("{}", encoding="utf-8")
    (run / "group_member_runs.json").write_text(
        json.dumps({"members": members or []}), encoding="utf-8"
    )


def test_render_highlights_group_uses_rollup(tmp_path: Path) -> None:
    run = tmp_path / "group"
    member = tmp_path / "member"
    (run / "highlights").mkdir(parents=True)
    (run / "highlights" / "highlight_rows.json").write_text(
        json.dumps(
            [
                {
                    "text": "Group highlight quote",
                    "speaker": "A",
                    "score": 0.8,
                    "order_index": 0,
                }
            ]
        ),
        encoding="utf-8",
    )
    dest = member / "highlights" / "data" / "global"
    dest.mkdir(parents=True)
    (dest / "m_highlights.json").write_text(
        json.dumps({"themes": [], "sections": {}}), encoding="utf-8"
    )
    _write_group_meta(
        run,
        members=[
            {
                "order_index": 0,
                "transcript_path": "/tmp/m.json",
                "transcript_key": "k",
                "run_id": "r1",
                "output_dir": str(member),
            }
        ],
    )

    st = MagicMock()
    with (
        patch.object(insights_blocks, "st", st),
        patch.object(insights_blocks, "_highlights_browser_fragment", MagicMock()),
    ):
        insights_blocks.render_highlights(_ctx(run), _placement())

    captions = [c.args[0] for c in st.caption.call_args_list if c.args]
    assert any("Group rollup" in str(c) for c in captions)
    assert any("Per session" in str(c) for c in captions)
    info_msgs = [str(c.args[0]) for c in st.info.call_args_list if c.args]
    assert not any("Run the" in m for m in info_msgs)


def test_render_insights_contract_group_rollup(tmp_path: Path) -> None:
    run = tmp_path / "group"
    (run / "insights").mkdir(parents=True)
    (run / "insights" / "insight_rows.json").write_text(
        json.dumps(
            [
                {
                    "kind": "key_theme",
                    "text": "Theme A",
                    "score": 0.5,
                    "order_index": 0,
                }
            ]
        ),
        encoding="utf-8",
    )
    (run / "insights" / "session_rows.json").write_text(
        json.dumps([{"order_index": 0, "theme_count": 1}]),
        encoding="utf-8",
    )
    _write_group_meta(run)

    st = MagicMock()
    with patch.object(insights_blocks, "st", st):
        insights_blocks.render_insights_contract(_ctx(run), _placement())

    writes = [c.args[0] for c in st.write.call_args_list if c.args]
    assert any("Theme A" in str(w) for w in writes)
    captions = [c.args[0] for c in st.caption.call_args_list if c.args]
    assert any("per-session insight counts" in str(c) for c in captions)


def test_overview_compact_has_no_session_picker(tmp_path: Path) -> None:
    run = tmp_path / "group"
    (run / "highlights").mkdir(parents=True)
    _write_group_meta(
        run,
        members=[
            {
                "order_index": 0,
                "transcript_path": "/tmp/a.json",
                "transcript_key": "k",
                "run_id": "r",
                "output_dir": str(tmp_path / "m"),
            }
        ],
    )
    st = MagicMock()
    with patch.object(curated, "st", st):
        curated.render_highlights_compact(_ctx(run), _placement("highlights_compact"))
    assert st.selectbox.call_count == 0
    infos = [str(c.args[0]) for c in st.info.call_args_list if c.args]
    assert infos  # quiet unavailable


def test_overview_compact_shows_rollup_without_picker(tmp_path: Path) -> None:
    run = tmp_path / "group"
    (run / "highlights").mkdir(parents=True)
    (run / "highlights" / "highlight_rows.json").write_text(
        json.dumps([{"text": "Across sessions", "order_index": 0}]),
        encoding="utf-8",
    )
    _write_group_meta(run)
    st = MagicMock()
    with patch.object(curated, "st", st):
        curated.render_highlights_compact(_ctx(run), _placement("highlights_compact"))
    assert st.selectbox.call_count == 0
    writes = [str(c.args[0]) for c in st.write.call_args_list if c.args]
    assert any("Across sessions" in w for w in writes)


def test_availability_group_rollup_patterns(tmp_path: Path) -> None:
    clear_registry_for_tests()
    register_builtin_blocks()
    run = tmp_path / "group"
    run.mkdir()
    _write_group_meta(run)

    highlights = get_block("highlights")
    assert highlights is not None
    ctx = build_block_context(
        run_root=run,
        subject_type="group",
        subject_id="g",
        run_id="r1",
        session_name="g/r1",
        artifacts=(_artifact("highlights", "highlights/highlight_rows.json"),),
        run_results=None,
        layout_profile_id="default",
    )
    assert check_block_availability(highlights, ctx).available

    commitments = get_block("commitments_table")
    assert commitments is not None
    ctx2 = build_block_context(
        run_root=run,
        subject_type="group",
        subject_id="g",
        run_id="r1",
        session_name="g/r1",
        artifacts=(_artifact("summary", "summary/summary.json"),),
        run_results=None,
        layout_profile_id="default",
    )
    assert check_block_availability(commitments, ctx2).available

    speakers = get_block("speaker_summary_cards")
    assert speakers is not None
    ctx3 = build_block_context(
        run_root=run,
        subject_type="group",
        subject_id="g",
        run_id="r1",
        session_name="g/r1",
        artifacts=(_artifact("stats", "stats/speaker_rows.json"),),
        run_results=None,
        layout_profile_id="default",
    )
    assert check_block_availability(speakers, ctx3).available


def test_availability_group_missing_message(tmp_path: Path) -> None:
    clear_registry_for_tests()
    register_builtin_blocks()
    run = tmp_path / "group"
    run.mkdir()
    _write_group_meta(run)
    spec = get_block("highlights")
    assert spec is not None
    ctx = build_block_context(
        run_root=run,
        subject_type="group",
        subject_id="g",
        run_id="r1",
        session_name="g/r1",
        artifacts=(),
        run_results=None,
        layout_profile_id="default",
    )
    result = check_block_availability(spec, ctx)
    assert not result.available
    assert "Group rollups" in (result.reason or "")
    assert "Run the required analysis modules" not in (result.reason or "")


def test_action_items_group_rollup(tmp_path: Path) -> None:
    run = tmp_path / "group"
    (run / "llm_action_items").mkdir(parents=True)
    (run / "llm_action_items" / "action_item_rows.json").write_text(
        json.dumps(
            [{"text": "Ship the fix", "owner": "A", "order_index": 0}],
        ),
        encoding="utf-8",
    )
    _write_group_meta(run)
    st = MagicMock()
    with patch.object(insights_blocks, "st", st):
        insights_blocks.render_llm_action_items_block(
            _ctx(run), _placement("llm_action_items_block")
        )
    captions = [str(c.args[0]) for c in st.caption.call_args_list if c.args]
    assert any("Group rollup" in c for c in captions)
