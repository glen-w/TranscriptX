"""Golden tests for speaker filename sanitisation, including documented collisions."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.llm_support.filenames import safe_speaker_filename


@pytest.mark.unit
@pytest.mark.parametrize(
    ("speaker", "expected"),
    [
        ("Alice Smith", "Alice_Smith"),
        ("QA/Ops", "QA_Ops"),
        ("José Álvarez", "José_Álvarez"),
        ("O'Brien, Jr.", "O'Brien,_Jr."),
        ("", ""),
        ("  ", "__"),
        ("Ana-María", "Ana-María"),
        ("Tab\there", "Tab\there"),
        ("dot.name", "dot.name"),
        ("A B/C", "A_B_C"),
    ],
)
def test_safe_speaker_filename_goldens(speaker: str, expected: str) -> None:
    assert safe_speaker_filename(speaker) == expected


@pytest.mark.unit
def test_safe_speaker_filename_documented_collisions() -> None:
    """Distinct display names that currently collide to the same filename.

    Documented, intentionally preserved behaviour: this refactor must not
    introduce collision disambiguation (that would change artifact paths).
    Collision-safe filename identity is tracked as separate work.
    """
    assert (
        safe_speaker_filename("A B")
        == safe_speaker_filename("A_B")
        == safe_speaker_filename("A/B")
        == "A_B"
    )


@pytest.mark.unit
def test_aggregation_uses_shared_filename_helper() -> None:
    """Aggregation formerly duplicated this sanitisation; both implementations
    produced identical outputs for every golden case, so it was consolidated
    onto llm_support.filenames. Guard against re-divergence."""
    from transcriptx.core.analysis.aggregation import llm as aggregation_llm

    assert aggregation_llm.safe_speaker_filename is safe_speaker_filename
