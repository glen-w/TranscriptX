import os
import sys
from pathlib import Path

# Add src directory to sys.path for module resolution
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from transcriptx.core_utils import format_time
from transcriptx.io import load_segments, load_speaker_map
from transcriptx.io.file_io import write_transcript_files
from transcriptx.core.utils.paths import OUTPUTS_DIR


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/output_human_transcript.py <transcript.json>")
        sys.exit(1)

    transcript_path = sys.argv[1]
    if not os.path.exists(transcript_path):
        print(f"File not found: {transcript_path}")
        sys.exit(1)

    base_name = Path(transcript_path).stem
    out_dir = os.path.join(OUTPUTS_DIR, base_name, "transcripts")
    os.makedirs(out_dir, exist_ok=True)

    segments = load_segments(transcript_path)
    speaker_map = load_speaker_map(transcript_path)

    txt_path, _ = write_transcript_files(
        segments, speaker_map, base_name, out_dir, format_time
    )
    print(f"Human-friendly transcript saved to: {txt_path}")


if __name__ == "__main__":
    main()
