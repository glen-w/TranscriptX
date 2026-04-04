from transcriptx.core.analysis.dynamics.pauses import PausesAnalysis


def test_pauses_detects_long_pause_and_post_question():
    segments = [
        {"speaker": "Alice", "text": "What do you think?", "start": 0.0, "end": 2.0},
        {"speaker": "Bob", "text": "I agree.", "start": 5.5, "end": 6.0},
    ]
    acts_data = {
        "tagged_segments": [
            {"dialogue_act": "question"},
            {"dialogue_act": "statement"},
        ]
    }
    results = PausesAnalysis().analyze(segments, acts_data=acts_data)
    kinds = {event.kind for event in results["events"]}
    assert "long_pause" in kinds
    assert "post_question_silence" in kinds
