"""Planning/gate check: T0 content modules are not skipped for SPEAKER_00-only."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.core.pipeline.dag_pipeline_run import speaker_gate_skip_reason
from transcriptx.core.pipeline.module_registry import get_module_info

_SNAPSHOT = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "module_registry"
    / "module_definitions_snapshot.json"
)

_T0_CONTENT_MODULES = (
    "wordclouds",
    "transcript_quality",
    "insight_eligibility",
    "understandability",
    "lexical_diversity",
    "epistemic_markers",
    "simplified_transcript",
    "topic_shift",
    "moments",
)


def _t0_module_ids_from_snapshot() -> tuple[str, ...]:
    data = json.loads(_SNAPSHOT.read_text(encoding="utf-8"))
    ids: list[str] = []
    for module_id, info in (data.get("modules") or {}).items():
        if int(info.get("min_named_speakers", 1)) != 0:
            continue
        if info.get("requires_multiple_speakers"):
            continue
        ids.append(str(module_id))
    return tuple(ids)


@pytest.mark.unit
@pytest.mark.parametrize("mod_id", _t0_module_ids_from_snapshot())
def test_t0_zero_named_modules_are_not_gated(mod_id: str) -> None:
    info = get_module_info(mod_id)
    assert info is not None, mod_id
    assert (
        speaker_gate_skip_reason(
            info,
            named_speaker_count=0,
            turn_taking_speaker_count=1,
            allow_unnamed_speakers=False,
        )
        is None
    ), mod_id


@pytest.mark.unit
def test_t0_snapshot_includes_content_modules() -> None:
    ids = set(_t0_module_ids_from_snapshot())
    missing = [mod_id for mod_id in _T0_CONTENT_MODULES if mod_id not in ids]
    assert missing == []


@pytest.mark.unit
def test_t0_multi_speaker_module_still_skips_on_monologue() -> None:
    info = get_module_info("conversation_loops")
    if info is None:
        info = SimpleNamespace(
            gate_on_turn_taking_speakers=False,
            requires_multiple_speakers=True,
            min_named_speakers=2,
        )
    reason = speaker_gate_skip_reason(
        info,
        named_speaker_count=0,
        turn_taking_speaker_count=1,
        allow_unnamed_speakers=True,
    )
    assert reason is not None
    assert "2" in reason or "multiple" in reason.lower() or "speakers" in reason
