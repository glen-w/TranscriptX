import json


def test_resolve_speaker_names_from_db_accepts_session_id(
    tmp_path, monkeypatch
) -> None:
    """
    The Streamlit transcript viewer passes "<slug>/<run_id>" into
    resolve_speaker_names_from_db(). Ensure we resolve that to a transcript path
    before looking for sidecar speaker maps.
    """

    from transcriptx.web.utils import resolve_speaker_names_from_db

    transcript_path = tmp_path / "meeting.json"
    transcript_path.write_text(
        json.dumps(
            {
                "metadata": {"title": "Meeting"},
                "segments": [
                    {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0}
                ],
            }
        )
    )
    sidecar_path = tmp_path / "meeting.speaker_map.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "speaker_map": {"SPEAKER_00": "Ana"},
                "ignored_speakers": [],
            }
        )
    )

    session_id = "260509_Ana_PhD_supervision_meeting/20260324_212347_5f301703"

    # Pretend the session id resolves to our temp transcript file.
    from transcriptx.web import utils as web_utils

    monkeypatch.setattr(
        web_utils.FileService,
        "resolve_transcript_path",
        staticmethod(lambda _session_name: transcript_path),
    )

    segments = [{"speaker": "SPEAKER_00", "text": "Hello"}]
    resolved = resolve_speaker_names_from_db(segments, session_id)

    assert resolved[0]["speaker_display"] == "Ana"
    # Current resolver implementation also replaces "speaker" when it maps.
    assert resolved[0]["speaker"] == "Ana"
