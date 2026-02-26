#!/usr/bin/env python3
"""
Simple script to create human-friendly transcript files.
"""

import csv
import json
import os
from pathlib import Path
from src.transcriptx.core.paths import OUTPUTS_DIR, READABLE_TRANSCRIPTS_DIR
import shutil


def format_time(seconds):
    """Format time in seconds to MM:SS format."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def write_transcript_files(segments, speaker_map, base_name, out_dir):
    """Create human-friendly transcript files."""
    transcript_path = os.path.join(out_dir, f"{base_name}-transcript.txt")
    csv_path = os.path.join(out_dir, f"{base_name}-transcript.csv")

    with (
        open(transcript_path, "w", encoding="utf-8") as f_txt,
        open(csv_path, "w", newline="", encoding="utf-8") as f_csv,
    ):
        writer = csv.writer(f_csv)
        writer.writerow(["Speaker", "Timestamp", "Text"])

        prev_speaker = None
        buffer = []
        start_time = None

        for seg in segments:
            spk = seg.get("speaker")
            name = speaker_map.get(spk, spk)
            text = seg.get("text", "").strip()
            pause = seg.get("pause", 0)
            timestamp = format_time(seg.get("start", 0))

            writer.writerow([name, timestamp, text])

            if name != prev_speaker:
                if prev_speaker and buffer:
                    f_txt.write(f"\n🗣️ {prev_speaker} ⏱️ {start_time}\n")
                    f_txt.write("".join(buffer) + "\n")
                    buffer = []
                start_time = timestamp
                prev_speaker = name

            if pause >= 2:
                f_txt.write(f"\n⏸️  {int(pause)} sec pause\n")

            buffer.append(text.strip() + "\n\n")

        if prev_speaker and buffer:
            f_txt.write(f"\n🗣️ {prev_speaker} ⏱️ {start_time}\n")
            f_txt.write("".join(buffer) + "\n")

    # Copy the text file to the readable transcripts directory
    os.makedirs(READABLE_TRANSCRIPTS_DIR, exist_ok=True)
    shutil.copy(
        transcript_path,
        os.path.join(READABLE_TRANSCRIPTS_DIR, os.path.basename(transcript_path)),
    )

    return transcript_path, csv_path


def main():
    # Load the transcript
    transcript_path = "example_transcript.json"
    with open(transcript_path, encoding="utf-8") as f:
        data = json.load(f)

    segments = data["segments"]

    # Load speaker map if it exists
    base_name = Path(transcript_path).stem
    speaker_map_path = os.path.join(
        OUTPUTS_DIR, base_name, f"{base_name}_speaker_map.json"
    )

    speaker_map = {}
    if os.path.exists(speaker_map_path):
        with open(speaker_map_path, encoding="utf-8") as f:
            speaker_map = json.load(f)

    # Create output directory
    out_dir = os.path.join(OUTPUTS_DIR, base_name)
    os.makedirs(out_dir, exist_ok=True)

    # Generate readable transcript
    txt_path, csv_path = write_transcript_files(
        segments, speaker_map, base_name, out_dir
    )

    print("✅ Human-friendly transcript created!")
    print(f"📄 Text file: {txt_path}")
    print(f"📊 CSV file: {csv_path}")

    # Show a preview of the text file
    print("\n📖 Preview of the friendly transcript:")
    print("-" * 50)
    with open(txt_path, encoding="utf-8") as f:
        content = f.read()
        print(content[:500] + "..." if len(content) > 500 else content)


if __name__ == "__main__":
    main()
