"""Unit tests for Corrections Studio manifest fingerprint helpers (pure functions)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.io.speaker_map_resolver import SpeakerMapState
from transcriptx.services.corrections_studio.generation_manifest import (
    build_generation_manifest,
    corrections_config_fingerprint,
    memory_rule_fingerprint,
)
from transcriptx.services.corrections_studio.schema import (
    GenerationManifest,
    StudioRule,
)


@pytest.mark.unit
def test_corrections_config_fingerprint_none_is_empty() -> None:
    assert corrections_config_fingerprint(None) == ""


@pytest.mark.unit
def test_corrections_config_fingerprint_stable_for_same_config() -> None:
    cfg = SimpleNamespace(
        known_acronyms=["A", "B"],
        known_org_phrases={"Org One": "x"},
        consistency_similarity_threshold=0.7,
        fuzzy_similarity_threshold=0.85,
        enable_fuzzy=True,
    )
    a = corrections_config_fingerprint(cfg)
    b = corrections_config_fingerprint(cfg)
    assert len(a) == 32
    assert a == b


@pytest.mark.unit
def test_corrections_config_fingerprint_changes_when_acronyms_change() -> None:
    base = SimpleNamespace(
        known_acronyms=["X"],
        known_org_phrases={},
        consistency_similarity_threshold=None,
        fuzzy_similarity_threshold=None,
        enable_fuzzy=False,
    )
    other = SimpleNamespace(
        known_acronyms=["Y"],
        known_org_phrases={},
        consistency_similarity_threshold=None,
        fuzzy_similarity_threshold=None,
        enable_fuzzy=False,
    )
    assert corrections_config_fingerprint(base) != corrections_config_fingerprint(other)


@pytest.mark.unit
def test_memory_rule_fingerprint_empty_rules() -> None:
    mem = SimpleNamespace(rules={})
    assert len(memory_rule_fingerprint(mem)) == 32


@pytest.mark.unit
def test_memory_rule_fingerprint_sorted_rule_ids() -> None:
    mem_ab = SimpleNamespace(rules={"b": object(), "a": object()})
    mem_ba = SimpleNamespace(rules={"a": object(), "b": object()})
    assert memory_rule_fingerprint(mem_ab) == memory_rule_fingerprint(mem_ba)


@pytest.mark.unit
def test_build_generation_manifest_matches_inputs_and_detector() -> None:
    rules = {
        "r1": StudioRule(
            rule_id="r1",
            rule_type="phrase",
            wrong_variants=["foo"],
            replacement_text="bar",
            scope="global",
            confidence=1.0,
            auto_apply=False,
            is_person_name=False,
        )
    }
    mem = SimpleNamespace(rules={"m1": object()})
    cfg = SimpleNamespace(
        known_acronyms=[],
        known_org_phrases={},
        consistency_similarity_threshold=None,
        fuzzy_similarity_threshold=None,
        enable_fuzzy=False,
    )
    sm = SpeakerMapState(has_sidecar=False)
    man = build_generation_manifest(
        transcript_identity_hash="txh",
        corrections_config=cfg,
        memory=mem,
        studio_rules=rules,
        speaker_map_state=sm,
        detector_version="9",
    )
    assert isinstance(man, GenerationManifest)
    assert man.transcript_identity_hash == "txh"
    assert man.detector_version == "9"
    assert man.speaker_map_fingerprint == ""
    assert man.corrections_config_fingerprint == corrections_config_fingerprint(cfg)
    assert man.memory_rule_fingerprint == memory_rule_fingerprint(mem)
