"""
Contract: transcript JSON writes go only through TranscriptStore or SpeakerMappingService.
Static check that the private speaker-map writer is only referenced in allowed modules.
"""

from __future__ import annotations

from pathlib import Path


def test_update_transcript_json_with_speaker_names_only_in_allowed_files() -> None:
    """Only core.py and mapping_service may reference the private speaker-map writer."""
    repo = Path(__file__).resolve().parents[2]
    src = repo / "src" / "transcriptx"
    files = []
    for py in src.rglob("*.py"):
        try:
            t = py.read_text(encoding="utf-8")
            if (
                "update_transcript_json_with_speaker_names" in t
                or "_update_transcript_json_with_speaker_names" in t
            ):
                files.append(py.name)
        except Exception:
            pass
    allowed = {"core.py", "mapping_service.py"}
    for f in files:
        assert f in allowed, (
            f"Only core.py and mapping_service.py may reference "
            f"update_transcript_json_with_speaker_names; found in {f}"
        )
