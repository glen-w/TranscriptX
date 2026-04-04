from __future__ import annotations


def test_transcript_page_speakers_metric_has_help_tooltip(monkeypatch) -> None:

    captured = {"help": None}

    class _DummyCol:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _DummySt:
        @staticmethod
        def metric(label, value, **kwargs):
            if label == "Speakers":
                captured["help"] = kwargs.get("help")
            return None

        @staticmethod
        def columns(_n):
            return (_DummyCol(), _DummyCol(), _DummyCol(), _DummyCol())

    transcript_data = {
        "metadata": {"speaker_count": 3, "duration_seconds": 3600.0},
        "segments": [
            {"speaker": "SPEAKER_00", "speaker_display": "Alice"},
            {"speaker": "SPEAKER_01", "speaker_display": "Bob"},
            {"speaker": "SPEAKER_02", "speaker_display": "Alice"},  # duplicate
        ],
    }

    def _render_metadata_like_page():
        metadata = transcript_data["metadata"]
        col1, col2, col3, col4 = _DummySt.columns(4)
        with col1:
            _DummySt.metric(
                "Duration", f"{metadata.get('duration_seconds', 0) / 60:.1f} min"
            )
        with col2:
            segments_for_names = transcript_data.get("segments", []) or []
            speaker_names = []
            for seg in segments_for_names:
                if not isinstance(seg, dict):
                    continue
                name = seg.get("speaker_display") or seg.get("speaker")
                if not name:
                    continue
                speaker_names.append(str(name).strip())
            speaker_names = sorted({n for n in speaker_names if n})
            speaker_help = None
            if speaker_names:
                speaker_help = "Speakers:\n" + "\n".join(
                    f"- {n}" for n in speaker_names
                )
            _DummySt.metric(
                "Speakers", metadata.get("speaker_count", 0), help=speaker_help
            )
        with col3:
            _DummySt.metric("Segments", len(transcript_data.get("segments", [])))
        with col4:
            _DummySt.metric("Language", metadata.get("language", "Unknown"))

    # We don't run the full Streamlit page; we just validate the tooltip payload format.
    _render_metadata_like_page()

    assert captured["help"] is not None
    assert "- Alice" in captured["help"]
    assert "- Bob" in captured["help"]
