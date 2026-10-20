"""Convert NeMo / generic JSONL segment lines into WhisperX-shaped import JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, List


def _segment_from_obj(obj: dict[str, Any]) -> dict[str, Any] | None:
    text = obj.get("text") or obj.get("pred_text") or obj.get("transcript")
    if text is None or str(text).strip() == "":
        return None
    start = obj.get("start")
    end = obj.get("end")
    if start is None and end is None:
        start = 0.0
        end = 0.0
    if start is None or end is None:
        return None
    seg: dict[str, Any] = {
        "start": float(start),
        "end": float(end),
        "text": str(text).strip(),
    }
    speaker = obj.get("speaker")
    if speaker is not None and str(speaker).strip():
        seg["speaker"] = str(speaker).strip()
    return seg


def parse_segment_lines(lines: Iterable[str]) -> List[dict[str, Any]]:
    segments: List[dict[str, Any]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        obj = json.loads(stripped)
        if not isinstance(obj, dict):
            continue
        seg = _segment_from_obj(obj)
        if seg is not None:
            segments.append(seg)
    return segments


def load_segments_from_path(path: Path) -> List[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return parse_segment_lines(text.splitlines())
    data = json.loads(text)
    if isinstance(data, dict) and isinstance(data.get("segments"), list):
        out: List[dict[str, Any]] = []
        for item in data["segments"]:
            if isinstance(item, dict):
                seg = _segment_from_obj(item)
                if seg is not None:
                    out.append(seg)
        return out
    if isinstance(data, list):
        out = []
        for item in data:
            if isinstance(item, dict):
                seg = _segment_from_obj(item)
                if seg is not None:
                    out.append(seg)
        return out
    raise ValueError(f"Unsupported NeMo/ASR JSON shape in {path}")


def to_whisperx_payload(segments: List[dict[str, Any]]) -> dict[str, Any]:
    return {"segments": segments}


def convert_file(input_path: Path, output_path: Path) -> None:
    segments = load_segments_from_path(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(to_whisperx_payload(segments), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    convert_file(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
