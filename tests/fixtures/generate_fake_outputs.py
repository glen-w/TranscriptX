"""
Generate a small deterministic fake outputs tree for dashboard testing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

from transcriptx.core.pipeline.manifest_builder import build_output_manifest


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def generate_fake_outputs() -> Path:
    from transcriptx.core.utils.paths import OUTPUTS_DIR

    session = "fake_session"
    run_id = "00000000_test"
    run_dir = Path(OUTPUTS_DIR) / session / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Module outputs
    _write_json(
        run_dir / "sentiment" / "data" / "global" / "sentiment.json",
        {"scores": [0.1, -0.2, 0.3]},
    )
    _write_text(
        run_dir / "sentiment" / "data" / "global" / "sentiment.csv",
        "score\n0.1\n-0.2\n0.3\n",
    )
    _write_text(
        run_dir / "sentiment" / "charts" / "global" / "sentiment_timeline.png",
        "PNGDATA",
    )
    _write_text(
        run_dir / "sentiment" / "charts" / "global" / "sentiment_timeline.html",
        "<html><body>Small HTML Chart</body></html>",
    )

    _write_json(
        run_dir / "emotion" / "data" / "global" / "emotion.json",
        {"joy": 0.2, "sadness": 0.1},
    )
    _write_text(
        run_dir / "emotion" / "charts" / "global" / "emotion_heatmap.png",
        "PNGDATA",
    )

    # Create a large HTML artifact (over 10MB)
    large_html = "<html><body>" + ("x" * (11 * 1024 * 1024)) + "</body></html>"
    _write_text(run_dir / "emotion" / "charts" / "global" / "huge_chart.html", large_html)

    # Transcript output
    _write_text(
        run_dir / "transcripts" / "fake_session-transcript.txt",
        "Speaker A: Hello\nSpeaker B: Hi\n",
    )

    manifest = build_output_manifest(
        run_dir=run_dir,
        run_id=run_id,
        transcript_key="fake_key",
        modules_enabled=["sentiment", "emotion"],
    )

    # Add missing file entry
    manifest["artifacts"].append(
        {
            "id": "missing_artifact",
            "kind": "data_json",
            "module": "sentiment",
            "scope": "global",
            "rel_path": "sentiment/data/global/missing.json",
            "bytes": 0,
            "mtime": "2026-01-18T00:00:00Z",
            "mime": "application/json",
            "tags": ["sentiment"],
            "title": "Missing File",
        }
    )

    manifest_path = run_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    return run_dir


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    test_outputs_dir = repo_root / ".test_outputs"
    test_outputs_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TRANSCRIPTX_OUTPUT_DIR", str(test_outputs_dir))

    path = generate_fake_outputs()
    print(f"Fake outputs generated at {path}")
