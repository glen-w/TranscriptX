import tempfile
from pathlib import Path

from transcriptx.core.corrections.apply import apply_corrections
from transcriptx.core.corrections.detect import (
    detect_acronym_candidates,
    detect_consistency_candidates,
    detect_memory_hits,
    resolve_segment_id,
)
from transcriptx.core.corrections.memory import _load_rules_from_yaml
from transcriptx.core.corrections.models import (
    Candidate,
    CorrectionConditions,
    CorrectionRule,
    Decision,
    Occurrence,
)
from transcriptx.core.corrections.workflow import _dedupe_candidates, _rule_signature_for_dedupe


def _segment(text: str, speaker: str = "Alice", start: float = 0.0, end: float = 1.0):
    return {"text": text, "speaker": speaker, "start": start, "end": end}


def test_memory_hit_replaces_phrase():
    segments = [_segment("We met with wren twenty one today.")]
    rule = CorrectionRule(
        type="phrase",
        wrong=["wren twenty one"],
        right="REN21",
        scope="project",
        confidence=0.9,
        auto_apply=True,
    )
    candidates = detect_memory_hits(segments, "key", [rule])
    updated_segments, patch_log = apply_corrections(
        segments, candidates, transcript_key="key", rules_by_id={rule.id: rule}
    )
    assert "REN21" in updated_segments[0]["text"]
    assert updated_segments[0]["text_raw"] == "We met with wren twenty one today."
    assert patch_log


def test_acronym_detector_flags_spaced_letters():
    segments = [_segment("We discussed c s e initiatives.")]
    candidates = detect_acronym_candidates(
        segments, "key", known_acronyms=["CSE"], known_org_phrases={}
    )
    assert any(c.proposed_right == "CSE" for c in candidates)


def test_consistency_detector_flags_minority_variant():
    segments = [
        _segment("REN21 is leading."),
        _segment("We partnered with REN21."),
        _segment("REN21 launched the program."),
        _segment("Ren21 was mentioned in notes."),
    ]
    candidates = detect_consistency_candidates(segments, "key", similarity_threshold=0.88)
    assert any(
        c.proposed_wrong == "Ren21" and c.proposed_right == "REN21" for c in candidates
    )


def test_speaker_conditioned_rule_only_applies_to_speaker():
    segments = [
        _segment("Hello from Alice.", speaker="Alice"),
        _segment("Hello from Alice.", speaker="Bob"),
    ]
    rule = CorrectionRule(
        type="token",
        wrong=["Alice"],
        right="Alicia",
        scope="project",
        confidence=0.9,
        auto_apply=True,
        conditions=CorrectionConditions(speaker="Alice"),
    )
    candidates = detect_memory_hits(segments, "key", [rule])
    updated_segments, _ = apply_corrections(
        segments, candidates, transcript_key="key", rules_by_id={rule.id: rule}
    )
    assert "Alicia" in updated_segments[0]["text"]
    assert "Alicia" not in updated_segments[1]["text"]


def test_conflicts_prefer_longer_match_span():
    segments = [_segment("REN21 is here.")]
    segment_id = resolve_segment_id(segments[0], "key")
    long_occ = Occurrence(
        segment_id=segment_id,
        speaker="Alice",
        time_start=0.0,
        time_end=1.0,
        span=(0, 5),
        snippet="REN21",
    )
    short_occ = Occurrence(
        segment_id=segment_id,
        speaker="Alice",
        time_start=0.0,
        time_end=1.0,
        span=(0, 3),
        snippet="REN",
    )
    long_candidate = Candidate(
        proposed_wrong="REN21",
        proposed_right="REN21X",
        kind="consistency",
        confidence=0.9,
        occurrences=[long_occ],
    )
    short_candidate = Candidate(
        proposed_wrong="REN",
        proposed_right="RENX",
        kind="consistency",
        confidence=0.95,
        occurrences=[short_occ],
    )
    updated_segments, patch_log = apply_corrections(
        segments, [long_candidate, short_candidate], transcript_key="key"
    )
    assert "REN21X" in updated_segments[0]["text"]
    assert "RENX" not in updated_segments[0]["text"]
    assert any(entry.get("status") == "conflict_skipped" for entry in patch_log)


# --- context_any ---


def test_context_any_rule_applies_only_when_segment_contains_term():
    segments = [
        _segment("The report mentions REN21.", speaker="Alice"),
        _segment("We met with REN21 today.", speaker="Bob"),
    ]
    rule = CorrectionRule(
        type="token",
        wrong=["REN21"],
        right="REN 21",
        scope="project",
        confidence=0.9,
        auto_apply=True,
        conditions=CorrectionConditions(context_any=["report", "document"]),
    )
    candidates = detect_memory_hits(segments, "key", [rule])
    updated_segments, _ = apply_corrections(
        segments, candidates, transcript_key="key", rules_by_id={rule.id: rule}
    )
    assert "REN 21" in updated_segments[0]["text"]
    assert "REN 21" not in updated_segments[1]["text"]


def test_context_any_empty_applies_everywhere():
    segments = [_segment("REN21 is here.")]
    rule = CorrectionRule(
        type="token",
        wrong=["REN21"],
        right="REN 21",
        scope="project",
        confidence=0.9,
        auto_apply=True,
        conditions=CorrectionConditions(context_any=[]),
    )
    candidates = detect_memory_hits(segments, "key", [rule])
    updated_segments, _ = apply_corrections(
        segments, candidates, transcript_key="key", rules_by_id={rule.id: rule}
    )
    assert "REN 21" in updated_segments[0]["text"]


# --- apply_some / apply_all span handling ---


def test_apply_some_skips_occurrence_without_span_and_logs():
    segments = [_segment("REN21 and REN21 again.")]
    seg_id = resolve_segment_id(segments[0], "key", segment_index=0)
    occ_no_span = Occurrence(
        segment_id=seg_id,
        speaker="Alice",
        time_start=0.0,
        time_end=1.0,
        span=None,
        snippet="REN21",
    )
    cand = Candidate(
        proposed_wrong="REN21",
        proposed_right="REN21X",
        kind="consistency",
        confidence=0.9,
        occurrences=[occ_no_span],
    )
    # Select this occurrence by id so we reach the span check; apply_some requires span so we log skipped_no_span
    decisions = [
        Decision(
            candidate_id=cand.candidate_id,
            decision="apply_some",
            selected_occurrence_ids=[occ_no_span.occurrence_id],
        )
    ]
    updated_segments, patch_log = apply_corrections(
        segments, [cand], transcript_key="key", decisions=decisions
    )
    skipped = [e for e in patch_log if e.get("status") == "skipped_no_span"]
    assert len(skipped) >= 1
    assert "REN21X" not in updated_segments[0]["text"]


def test_apply_all_with_occurrence_span_none_uses_finditer():
    segments = [_segment("foo bar foo bar.")]
    seg_id = resolve_segment_id(segments[0], "key", segment_index=0)
    occ_no_span = Occurrence(
        segment_id=seg_id,
        speaker="Alice",
        time_start=0.0,
        time_end=1.0,
        span=None,
        snippet="foo",
    )
    cand = Candidate(
        proposed_wrong="foo",
        proposed_right="FOO",
        kind="memory_hit",
        confidence=0.9,
        occurrences=[occ_no_span],
    )
    decisions = [Decision(candidate_id=cand.candidate_id, decision="apply_all")]
    updated_segments, _ = apply_corrections(
        segments, [cand], transcript_key="key", decisions=decisions
    )
    assert updated_segments[0]["text"] == "FOO bar FOO bar."


# --- conflict metadata ---


def test_patch_log_has_resolution_policy_and_conflict_metadata():
    segments = [_segment("REN21 is here.")]
    seg_id = resolve_segment_id(segments[0], "key", segment_index=0)
    long_occ = Occurrence(
        segment_id=seg_id,
        speaker="Alice",
        time_start=0.0,
        time_end=1.0,
        span=(0, 5),
        snippet="REN21",
    )
    short_occ = Occurrence(
        segment_id=seg_id,
        speaker="Alice",
        time_start=0.0,
        time_end=1.0,
        span=(0, 3),
        snippet="REN",
    )
    long_candidate = Candidate(
        proposed_wrong="REN21",
        proposed_right="REN21X",
        kind="consistency",
        confidence=0.9,
        occurrences=[long_occ],
    )
    short_candidate = Candidate(
        proposed_wrong="REN",
        proposed_right="RENX",
        kind="consistency",
        confidence=0.95,
        occurrences=[short_occ],
    )
    _, patch_log = apply_corrections(
        segments, [long_candidate, short_candidate], transcript_key="key"
    )
    first = patch_log[0]
    assert first.get("resolution_policy") == "longest_span > confidence > kind_priority > left_to_right"
    conflict_entry = next(
        (e for e in patch_log if e.get("status") == "conflict_skipped"),
        None,
    )
    assert conflict_entry is not None
    assert "conflicts_with" in conflict_entry
    assert len(conflict_entry["conflicts_with"]) >= 1


# --- is_person_name ---


def test_is_person_name_skipped_for_unidentified_speaker():
    segments = [
        _segment("Alice said hello.", speaker="SPEAKER_01"),
        _segment("Bob said hi.", speaker="Alice"),
    ]
    rule = CorrectionRule(
        type="token",
        wrong=["Alice"],
        right="Alicia",
        scope="project",
        confidence=0.9,
        auto_apply=True,
        is_person_name=True,
    )
    candidates = detect_memory_hits(segments, "key", [rule])
    updated_segments, _ = apply_corrections(
        segments, candidates, transcript_key="key", rules_by_id={rule.id: rule}
    )
    assert "Alicia" not in updated_segments[0]["text"]
    assert "Alicia" in updated_segments[1]["text"]


# --- resolve_segment_id ---


def test_resolve_segment_id_uses_explicit_id():
    seg = {"id": "abc-123", "text": "Hi", "start": 0.0, "end": 1.0}
    assert resolve_segment_id(seg, "key") == "abc-123"
    assert resolve_segment_id(seg, "key", segment_index=5) == "abc-123"


def test_resolve_segment_id_uses_timestamps_when_no_id():
    seg = {"text": "Hi", "start": 1.5, "end": 2.5}
    a = resolve_segment_id(seg, "tk")
    b = resolve_segment_id(seg, "tk", segment_index=0)
    assert a == b
    # Same timestamps yield same id (text is not part of timestamp-based id)
    seg2 = {"text": "Bye", "start": 1.5, "end": 2.5}
    c = resolve_segment_id(seg2, "tk", segment_index=0)
    assert a == c
    # Different timestamps yield different id
    seg3 = {"text": "Hi", "start": 1.6, "end": 2.5}
    d = resolve_segment_id(seg3, "tk")
    assert a != d


def test_resolve_segment_id_falls_back_to_index():
    seg = {"text": "Hi"}
    a = resolve_segment_id(seg, "tk", segment_index=0)
    b = resolve_segment_id(seg, "tk", segment_index=1)
    assert a != b


# --- dedupe candidates ---


def test_dedupe_merges_same_kind_wrong_right_keeps_max_confidence():
    seg_id = "sid"
    o1 = Occurrence(segment_id=seg_id, span=(0, 3), snippet="foo")
    o2 = Occurrence(segment_id=seg_id, span=(10, 13), snippet="foo")
    c1 = Candidate(
        proposed_wrong="foo",
        proposed_right="FOO",
        kind="consistency",
        confidence=0.8,
        occurrences=[o1],
    )
    c2 = Candidate(
        proposed_wrong="foo",
        proposed_right="FOO",
        kind="consistency",
        confidence=0.95,
        occurrences=[o2],
    )
    merged = _dedupe_candidates([c1, c2])
    assert len(merged) == 1
    assert merged[0].confidence == 0.95
    assert len(merged[0].occurrences) == 2


def test_dedupe_with_different_conditions_keeps_separate():
    seg_id = "sid"
    o1 = Occurrence(segment_id=seg_id, span=(0, 3), snippet="REN21")
    o2 = Occurrence(segment_id=seg_id, span=(0, 3), snippet="Ren21")
    rule_a = CorrectionRule(
        type="token",
        wrong=["REN21"],
        right="REN 21",
        scope="project",
        conditions=CorrectionConditions(speaker="Alice"),
    )
    rule_b = CorrectionRule(
        type="token",
        wrong=["Ren21"],
        right="REN 21",
        scope="project",
        conditions=CorrectionConditions(speaker="Bob"),
    )
    c1 = Candidate(
        proposed_wrong="REN21",
        proposed_right="REN 21",
        kind="memory_hit",
        confidence=0.9,
        rule_id=rule_a.id,
        occurrences=[o1],
    )
    c2 = Candidate(
        proposed_wrong="Ren21",
        proposed_right="REN 21",
        kind="memory_hit",
        confidence=0.9,
        rule_id=rule_b.id,
        occurrences=[o2],
    )
    merged = _dedupe_candidates([c1, c2], rules_by_id={rule_a.id: rule_a, rule_b.id: rule_b})
    assert len(merged) == 2


# --- replay fallback (apply_some by span+wrong) ---


def test_apply_some_replay_fallback_matches_by_span_and_wrong():
    segments = [_segment("REN21 is here.")]
    seg_id = resolve_segment_id(segments[0], "key", segment_index=0)
    occ = Occurrence(
        segment_id=seg_id,
        speaker="Alice",
        time_start=0.0,
        time_end=1.0,
        span=(0, 5),
        snippet="REN21",
    )
    cand = Candidate(
        proposed_wrong="REN21",
        proposed_right="REN21X",
        kind="consistency",
        confidence=0.9,
        occurrences=[occ],
    )
    # Decision references an occurrence_id that might not match (e.g. from old replay);
    # we allow by (segment_id, span, wrong) when text at span equals proposed_wrong
    wrong_occurrence_id = "nonexistent_id"
    decisions = [
        Decision(
            candidate_id=cand.candidate_id,
            decision="apply_some",
            selected_occurrence_ids=[wrong_occurrence_id],
        )
    ]
    updated_segments, _ = apply_corrections(
        segments, [cand], transcript_key="key", decisions=decisions
    )
    assert "REN21X" in updated_segments[0]["text"]


# --- YAML keyed rule IDs ---


def test_yaml_keyed_rule_id_wins_over_inline_id():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "corrections.yml"
        path.write_text(
            "rules:\n  my_stable_key:\n    type: token\n    wrong: [REN21]\n    right: REN 21\n"
            "    scope: project\n    id: computed_sha_id\n"
        )
        rules = _load_rules_from_yaml(path)
        assert len(rules) == 1
        rule = list(rules.values())[0]
        assert rule.id == "my_stable_key"


# --- rule signature for dedupe ---


def test_rule_signature_for_dedupe_none_for_no_rule():
    assert _rule_signature_for_dedupe(None) == (None, None)


def test_rule_signature_for_dedupe_includes_conditions():
    rule = CorrectionRule(
        type="token",
        wrong=["x"],
        right="y",
        scope="project",
        conditions=CorrectionConditions(speaker="Alice", context_any=["report"]),
    )
    sig, speaker = _rule_signature_for_dedupe(rule)
    assert speaker == "Alice"
    assert sig is not None
    assert sig[0] == "Alice"
    assert "report" in sig[2]
