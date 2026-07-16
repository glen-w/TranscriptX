"""Offline unit tests for corrections CLI review branches."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from transcriptx.core.corrections.cli_review import (
    _ACTION_LEGEND,
    _build_rule_from_candidate,
    _format_time_window,
    _impact_label,
    _print_occurrence_examples,
    _prompt_action,
    _reason_label,
    _select_occurrences,
    review_candidates,
)
from transcriptx.core.corrections.models import Candidate, Occurrence


def _cand(
    kind: str = "acronym",
    wrong: str = "c s e",
    right: str = "CSE",
    conf: float = 0.7,
) -> Candidate:
    return Candidate(
        kind=kind,  # type: ignore[arg-type]
        proposed_wrong=wrong,
        proposed_right=right,
        confidence=conf,
        occurrences=[
            Occurrence(
                segment_id="s1",
                snippet=wrong,
                span=(0, 5),
                speaker="Alice",
                time_start=1.0,
                time_end=2.0,
                occurrence_id="occ-1",
            ),
            Occurrence(
                segment_id="s2",
                snippet=wrong,
                span=(0, 5),
                speaker=None,
                time_start=None,
                time_end=3.0,
                occurrence_id="occ-2",
            ),
        ],
    )


@pytest.mark.unit
def test_format_time_window_variants() -> None:
    assert _format_time_window(None, None) == "?"
    assert _format_time_window(None, 2.0).startswith("?-")
    assert _format_time_window(1.0, None).endswith("-?")
    assert "-" in _format_time_window(1.0, 2.0)


@pytest.mark.unit
def test_reason_and_impact_labels() -> None:
    assert _reason_label(_cand(kind="memory_hit")) == "From saved rule"
    assert _reason_label(_cand(kind="acronym")) == "Acronym list"
    assert _reason_label(_cand(kind="consistency")) == "Consistency"
    assert _reason_label(_cand(kind="fuzzy")) == "Fuzzy match"
    assert _reason_label(_cand(kind="ner_variant")) == "NER variant"
    # force unknown via object without going through validator — use acronym default branch
    class _K:
        kind = "other"

    assert _reason_label(_K()) == "Suggestion"  # type: ignore[arg-type]

    assert _impact_label(_cand(kind="acronym")) == "cosmetic"
    assert _impact_label(_cand(kind="fuzzy")) == "structural"
    assert _impact_label(_cand(kind="consistency")) == "semantic"


@pytest.mark.unit
def test_print_occurrence_examples(capsys) -> None:
    _print_occurrence_examples(_cand(), limit=1)
    out = capsys.readouterr().out
    assert "Occurrences: 2" in out
    assert "Alice" in out


@pytest.mark.unit
def test_prompt_action_skips_blank_then_returns(monkeypatch) -> None:
    answers = iter(["", "  ", "a"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert _prompt_action() == "a"
    assert "a=apply" in _ACTION_LEGEND


@pytest.mark.unit
def test_select_occurrences_parses_indices(monkeypatch) -> None:
    cand = _cand()
    monkeypatch.setattr("builtins.input", lambda _: "1, bogus, 2, 99,")
    ids = _select_occurrences(cand)
    assert ids == ["occ-1", "occ-2"]


@pytest.mark.unit
def test_build_rule_from_candidate_person_and_phrase() -> None:
    fuzzy = _cand(kind="fuzzy", wrong="alic", right="Alice")
    rule = _build_rule_from_candidate(fuzzy, scope="project")
    assert rule.is_person_name is True
    assert rule.type == "token"
    assert rule.scope == "project"

    phrase = _cand(kind="consistency", wrong="new york", right="New York")
    rule2 = _build_rule_from_candidate(phrase, scope="global")
    assert rule2.type == "phrase"


@pytest.mark.unit
def test_review_candidates_all_actions(monkeypatch, capsys) -> None:
    cands = [
        _cand(wrong="a", right="A", conf=0.9),
        _cand(wrong="b", right="B", conf=0.8),
        _cand(wrong="c", right="C", conf=0.7),
        _cand(wrong="d", right="D", conf=0.6),
        _cand(wrong="e", right="E", conf=0.5),
    ]
    actions = iter(["k", "r", "a", "s", "l"])
    monkeypatch.setattr(
        "transcriptx.core.corrections.cli_review._prompt_action",
        lambda: next(actions),
    )
    monkeypatch.setattr(
        "transcriptx.core.corrections.cli_review._select_occurrences",
        lambda c: [c.occurrences[0].occurrence_id],
    )
    decisions = review_candidates(cands, default_rule_scope="project")
    assert [d.decision for d in decisions] == [
        "skip",
        "reject",
        "apply_all",
        "apply_some",
        "apply_all",
    ]
    assert decisions[3].selected_occurrence_ids
    assert decisions[4].new_rule is not None
    out = capsys.readouterr().out
    assert "Saved as project rule" in out
