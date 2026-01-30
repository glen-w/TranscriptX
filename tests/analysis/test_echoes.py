from transcriptx.core.analysis.dynamics.echoes import EchoesAnalysis


def test_echoes_detect_explicit_quote_and_echo():
    segments = [
        {"speaker": "Alice", "text": "We should ship tomorrow.", "start": 0.0, "end": 2.0},
        {"speaker": "Bob", "text": "As you said, we should ship tomorrow.", "start": 3.0, "end": 5.0},
    ]
    results = EchoesAnalysis().analyze(segments)
    kinds = {event.kind for event in results["events"]}
    assert "explicit_quote" in kinds
    assert "echo" in kinds
