"""Convert mlx-audio / Granite Speech JSON into WhisperX-shaped import JSON.

mlx-audio ``--format json`` is not a stable public schema. This converter
accepts:

- ``{"text": "..."}`` (plain ASR)
- ``{"segments": [{"text", "speaker_id"|"speaker", "start", "end", "words"?}]}``
- raw ``[Speaker N]:`` tags inside ``text`` (Plus speaker-attributed ASR)

Speaker IDs are mapped to ``SPEAKER_XX`` (IBM 1-based → WhisperX 0-based).
When a chunk has text but no times, ``duration`` (seconds) plus ``time_offset``
span the chunk; multi-turn SAA without times is split by character length
(estimated timing — not WhisperX-grade alignment).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, List

_SPEAKER_TAG_RE = re.compile(r"\[Speaker\s+(\d+)\]\s*:", re.IGNORECASE)
_SPEAKER_NUM_RE = re.compile(r"(\d+)")


def speaker_label(raw: Any) -> str | None:
    """Map Granite / mlx-audio speaker ids onto WhisperX ``SPEAKER_XX``."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.upper().startswith("SPEAKER_"):
        return text
    match = _SPEAKER_NUM_RE.search(text)
    if match is None:
        return text
    number = int(match.group(1))
    index = number - 1 if number >= 1 else number
    if index < 0:
        index = 0
    return f"SPEAKER_{index:02d}"


def _estimated_spans(
    texts: list[str], start: float, end: float
) -> list[tuple[float, float]]:
    weights = [max(len(item), 1) for item in texts]
    total = float(sum(weights))
    duration = max(float(end) - float(start), 0.0)
    spans: list[tuple[float, float]] = []
    cursor = float(start)
    for i, weight in enumerate(weights):
        if i == len(weights) - 1:
            spans.append((cursor, float(end)))
        else:
            piece = duration * (weight / total)
            spans.append((cursor, cursor + piece))
            cursor += piece
    return spans


def _split_speaker_tags(text: str) -> list[tuple[str | None, str]]:
    stripped = text.strip()
    if not stripped:
        return []
    matches = list(_SPEAKER_TAG_RE.finditer(stripped))
    if not matches:
        return [(None, stripped)]
    turns: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        prefix = stripped[: matches[0].start()].strip()
        if prefix:
            turns.append((None, prefix))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(stripped)
        body = stripped[match.end() : end].strip()
        label = speaker_label(match.group(1))
        if body:
            turns.append((label, body))
    return turns


def _word_times(words: Any) -> tuple[float | None, float | None]:
    if not isinstance(words, list) or not words:
        return None, None
    starts: list[float] = []
    ends: list[float] = []
    for item in words:
        if not isinstance(item, dict):
            continue
        if item.get("start") is not None:
            starts.append(float(item["start"]))
        if item.get("end") is not None:
            ends.append(float(item["end"]))
    if not starts and not ends:
        return None, None
    start = min(starts) if starts else (min(ends) if ends else None)
    end = max(ends) if ends else (max(starts) if starts else None)
    return start, end


def _segment_from_obj(obj: dict[str, Any]) -> dict[str, Any] | None:
    text = obj.get("text") or obj.get("transcript") or obj.get("pred_text")
    if text is None or str(text).strip() == "":
        return None
    start = obj.get("start")
    end = obj.get("end")
    word_start, word_end = _word_times(obj.get("words"))
    if start is None:
        start = word_start
    if end is None:
        end = word_end
    seg: dict[str, Any] = {"text": str(text).strip()}
    if start is not None:
        seg["start"] = float(start)
    if end is not None:
        seg["end"] = float(end)
    speaker = speaker_label(obj.get("speaker") or obj.get("speaker_id"))
    if speaker:
        seg["speaker"] = speaker
    return seg


def _apply_offset_and_duration(
    segments: list[dict[str, Any]],
    *,
    time_offset: float,
    duration: float | None,
) -> list[dict[str, Any]]:
    if not segments:
        return []
    missing_times = any("start" not in seg or "end" not in seg for seg in segments)
    if missing_times:
        span_start = float(time_offset)
        span_end = span_start + float(duration or 0.0)
        texts = [str(seg.get("text") or "") for seg in segments]
        spans = _estimated_spans(texts, span_start, span_end)
        out: list[dict[str, Any]] = []
        for seg, (start, end) in zip(segments, spans):
            item = dict(seg)
            item["start"] = float(start)
            item["end"] = float(end)
            out.append(item)
        return out
    out = []
    for seg in segments:
        item = dict(seg)
        item["start"] = float(item["start"]) + float(time_offset)
        item["end"] = float(item["end"]) + float(time_offset)
        out.append(item)
    return out


def segments_from_payload(
    data: Any,
    *,
    time_offset: float = 0.0,
    duration: float | None = None,
) -> List[dict[str, Any]]:
    raw_segments: list[dict[str, Any]] = []
    if isinstance(data, str):
        data = {"text": data}
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                seg = _segment_from_obj(item)
                if seg is not None:
                    raw_segments.append(seg)
    elif isinstance(data, dict):
        items = data.get("segments")
        if isinstance(items, list) and items:
            for item in items:
                if not isinstance(item, dict):
                    continue
                seg = _segment_from_obj(item)
                if seg is not None:
                    raw_segments.append(seg)
        elif data.get("text") and (
            "start" in data
            or "end" in data
            or "speaker" in data
            or "speaker_id" in data
        ):
            seg = _segment_from_obj(data)
            if seg is not None:
                raw_segments.append(seg)
        elif data.get("text"):
            for label, body in _split_speaker_tags(str(data["text"])):
                seg: dict[str, Any] = {"text": body}
                if label:
                    seg["speaker"] = label
                raw_segments.append(seg)
    if not raw_segments:
        return []
    return _apply_offset_and_duration(
        raw_segments, time_offset=time_offset, duration=duration
    )


def load_segments_from_path(
    path: Path,
    *,
    time_offset: float = 0.0,
    duration: float | None = None,
) -> List[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []
    if path.suffix.lower() == ".jsonl":
        segments: list[dict[str, Any]] = []
        for line in stripped.splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            segments.extend(
                segments_from_payload(obj, time_offset=time_offset, duration=duration)
            )
        return segments
    data = json.loads(stripped)
    return segments_from_payload(data, time_offset=time_offset, duration=duration)


def to_whisperx_payload(segments: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return {"segments": list(segments)}


def convert_file(
    input_path: Path,
    output_path: Path,
    *,
    time_offset: float = 0.0,
    duration: float | None = None,
) -> None:
    segments = load_segments_from_path(
        input_path, time_offset=time_offset, duration=duration
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(to_whisperx_payload(segments), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def stitch_chunk_payloads(
    chunks: Iterable[tuple[Any, float, float | None]],
) -> list[dict[str, Any]]:
    """Stitch ``(payload, time_offset, duration)`` tuples into one segment list."""
    out: list[dict[str, Any]] = []
    for payload, offset, duration in chunks:
        out.extend(
            segments_from_payload(payload, time_offset=float(offset), duration=duration)
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--time-offset", type=float, default=0.0)
    parser.add_argument("--duration", type=float, default=None)
    args = parser.parse_args(argv)
    convert_file(
        args.input,
        args.output,
        time_offset=args.time_offset,
        duration=args.duration,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
