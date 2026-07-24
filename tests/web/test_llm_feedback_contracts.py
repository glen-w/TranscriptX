"""Contract tests for LLM feedback wiring and shell CSS."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.llm_feedback.models import (
    FeedbackSurface,
    FeedbackTarget,
    build_event,
)
from transcriptx.core.llm_feedback.validate import validate_event
from transcriptx.web.blocks.llm_presentation import build_block_feedback_target
from transcriptx.web.blocks.context import BlockContext, BlockServices

FIXTURES = Path(__file__).parent / "fixtures" / "llm_feedback"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_shell_defines_llm_feedback_hover_css() -> None:
    source = Path("src/transcriptx/web/shell.py").read_text(encoding="utf-8")
    assert 'class*="llm_fb_"' in source or "llm_fb_" in source
    # Persistent affordance (not hover-only opacity 0)
    assert "opacity: 0.4" in source
    fb_css = source.split("LLM feedback")[1].split("Speaker chips")[0]
    assert "opacity: 0;" not in fb_css
    assert "focus-within" in fb_css
    assert "focus-visible" in fb_css


def test_feedback_widget_not_under_cache_data() -> None:
    source = Path("src/transcriptx/web/components/llm_feedback.py").read_text(
        encoding="utf-8"
    )
    assert "st.cache_data" not in source
    assert "@st.cache_resource" not in source


def test_surface_fixtures_validate(tmp_path: Path) -> None:
    assert FIXTURES.is_dir()
    names = sorted(p.name for p in FIXTURES.glob("*.json"))
    assert names == [
        "chart_caption.json",
        "custom_qa_answer.json",
        "insights_block.json",
        "overview_hero.json",
    ]
    for name in names:
        data = _load_fixture(name)
        target = FeedbackTarget.from_dict(data["target"])
        assert target.surface in {s.value for s in FeedbackSurface}
        assert data["output_text"]
        for key in (
            "run_id",
            "subject_type",
            "subject_id",
            "module",
        ):
            assert target.to_dict().get(key), f"{name} missing {key}"
        ev = build_event(
            rating=data["rating"],
            reason=data["reason"],
            note=data.get("note") or "",
            output_text=data["output_text"],
            target=target,
            submission_token=data["submission_token"],
        )
        validated = validate_event(ev)
        assert validated.target.run_id == target.run_id
        assert validated.output_sha256


def test_build_block_feedback_target_requires_ids() -> None:
    ctx = BlockContext(
        run_root=None,
        subject_type="transcript",
        subject_id="s1",
        run_id="r1",
        session_name=None,
        artifacts=(),
        run_results=None,
        services=BlockServices(),
        layout_profile_id="default",
    )
    ok = build_block_feedback_target(
        ctx,
        surface=FeedbackSurface.INSIGHTS_BLOCK,
        block_id="llm_summary_block",
        module="llm_summary",
        artifact_rel_path="llm_summary/x.md",
    )
    assert ok is not None
    missing = build_block_feedback_target(
        ctx,
        surface=FeedbackSurface.INSIGHTS_BLOCK,
        block_id="llm_summary_block",
        module="llm_summary",
        artifact_rel_path="",
    )
    assert missing is None
