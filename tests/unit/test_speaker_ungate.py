"""Unit tests for speaker ungate resolution helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.pipeline.speaker_ungate import (
    effective_speaker_ungate_for_pipeline,
    resolve_allow_unnamed_speakers,
    resolve_treat_as_single_speaker,
    use_turn_taking_speaker_gate,
)
from transcriptx.core.utils.config import TranscriptXConfig, get_config, set_config


@pytest.mark.unit
def test_effective_speaker_ungate_allow_unnamed() -> None:
    assert effective_speaker_ungate_for_pipeline(
        allow_unnamed=True,
        treat_as_single=False,
        turn_taking_speaker_count=0,
    )


@pytest.mark.unit
def test_effective_speaker_ungate_treat_single_one_diarized() -> None:
    assert effective_speaker_ungate_for_pipeline(
        allow_unnamed=False,
        treat_as_single=True,
        turn_taking_speaker_count=1,
    )


@pytest.mark.unit
def test_effective_speaker_ungate_default_off() -> None:
    assert not effective_speaker_ungate_for_pipeline(
        allow_unnamed=False,
        treat_as_single=False,
        turn_taking_speaker_count=2,
    )
    assert not effective_speaker_ungate_for_pipeline(
        allow_unnamed=False,
        treat_as_single=True,
        turn_taking_speaker_count=2,
    )


@pytest.mark.unit
def test_use_turn_taking_speaker_gate_allow_unnamed() -> None:
    assert use_turn_taking_speaker_gate(
        allow_unnamed_speakers=True,
        treat_as_single_speaker=False,
        turn_taking_speaker_count=None,
    )


@pytest.mark.unit
def test_use_turn_taking_speaker_gate_single_monologue() -> None:
    assert use_turn_taking_speaker_gate(
        allow_unnamed_speakers=False,
        treat_as_single_speaker=True,
        turn_taking_speaker_count=1,
    )
    assert not use_turn_taking_speaker_gate(
        allow_unnamed_speakers=False,
        treat_as_single_speaker=True,
        turn_taking_speaker_count=2,
    )


@pytest.mark.unit
def test_use_turn_taking_speaker_gate_requires_count_for_treat_single() -> None:
    assert not use_turn_taking_speaker_gate(
        allow_unnamed_speakers=False,
        treat_as_single_speaker=True,
        turn_taking_speaker_count=None,
    )


@pytest.mark.unit
def test_resolve_allow_unnamed_per_run_overrides_config() -> None:
    assert resolve_allow_unnamed_speakers(per_run=True)


@pytest.mark.unit
def test_resolve_allow_unnamed_reads_global_config() -> None:
    original = get_config()
    cfg = TranscriptXConfig()
    cfg.analysis.allow_unnamed_speakers = True
    set_config(cfg)
    try:
        assert resolve_allow_unnamed_speakers(per_run=False)
    finally:
        set_config(original)


@pytest.mark.unit
def test_resolve_treat_as_single_per_run_and_config(monkeypatch) -> None:
    assert resolve_treat_as_single_speaker(per_run=True)

    monkeypatch.setattr(
        "transcriptx.core.utils.config.get_config",
        lambda: SimpleNamespace(
            analysis=SimpleNamespace(treat_as_single_speaker=True)
        ),
    )
    assert resolve_treat_as_single_speaker(per_run=False)


@pytest.mark.unit
def test_resolve_helpers_fail_closed_on_config_error(monkeypatch) -> None:
    def _boom():
        raise RuntimeError("no config")

    monkeypatch.setattr("transcriptx.core.utils.config.get_config", _boom)
    assert resolve_allow_unnamed_speakers(per_run=False) is False
    assert resolve_treat_as_single_speaker(per_run=False) is False
