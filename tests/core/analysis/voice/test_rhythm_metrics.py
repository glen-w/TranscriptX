from transcriptx.core.analysis.voice.rhythm import npvi, varco


def test_npvi_returns_none_for_short_sequences() -> None:
    assert npvi([]) is None
    assert npvi([0.1]) is None


def test_npvi_basic_sequence() -> None:
    # Simple deterministic sequence
    values = [1.0, 2.0, 3.0]
    # nPVI = 100 * mean(|d1-d2| / ((d1+d2)/2)) => (|1-2|/1.5 + |2-3|/2.5)/2
    expected = 100.0 * ((1.0 / 1.5) + (1.0 / 2.5)) / 2.0
    assert npvi(values) == expected


def test_varco_returns_none_for_short_sequences() -> None:
    assert varco([]) is None
    assert varco([0.1]) is None


def test_varco_basic_sequence() -> None:
    values = [1.0, 2.0, 3.0]
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    expected = 100.0 * (variance**0.5) / mean
    assert varco(values) == expected
