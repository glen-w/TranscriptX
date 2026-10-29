"""Convert Nemotron 3.5 Transcribe dumps into WhisperX-shaped import JSON.

Accepts, in priority order:

1. ``ctc_timestamps.words`` when ``error`` is null (word times + speaker).
2. ``<spk:N>`` tags or ``extract_speaker_dict``-shaped turns in the transcript.
3. Plain transcript text — one undiarized segment at ``0.0``/``0.0`` (T0 admit).

Nemotron speaker ids are 0-based (``<spk:0>`` → ``SPEAKER_00``).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, List

_SPK_TAG_RE = re.compile(r"<spk:(\d+)>")
_SPEAKER_NUM_RE = re.compile(r"(\d+)")


def speaker_label(raw: Any) -> str | None:
    """Map Nemotron 0-based speaker ids onto WhisperX ``SPEAKER_XX``."""
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
    index = int(match.group(1))
    if index < 0:
        index = 0
    return f"SPEAKER_{index:02d}"


def to_whisperx_payload(segments: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return {"segments": list(segments)}


def _chat_content(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if content is not None:
                    return str(content)
            text = first.get("text")
            if text is not None:
                return str(text)
    for key in ("text", "transcript", "pred_text"):
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return ""


def _ctc_block(data: dict[str, Any]) -> dict[str, Any] | None:
    ctc = data.get("ctc_timestamps")
    if not isinstance(ctc, dict):
        return None
    error = ctc.get("error")
    if error not in (None, "", False):
        return None
    words = ctc.get("words")
    if not isinstance(words, list) or not words:
        return None
    return ctc


def _word_item(item: dict[str, Any]) -> dict[str, Any] | None:
    token = item.get("word") or item.get("text") or item.get("token")
    if token is None or str(token).strip() == "":
        return None
    start = item.get("start")
    end = item.get("end")
    out: dict[str, Any] = {"word": str(token).strip()}
    if start is not None:
        out["start"] = float(start)
    if end is not None:
        out["end"] = float(end)
    if item.get("speaker") is not None:
        speaker = speaker_label(item.get("speaker"))
        if speaker:
            out["speaker"] = speaker
    return out


def _join_words(words: list[dict[str, Any]]) -> str:
    return " ".join(str(w.get("word") or "") for w in words).strip()


def segments_from_ctc_words(words: list[Any]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for item in words:
        if not isinstance(item, dict):
            continue
        word = _word_item(item)
        if word is not None:
            parsed.append(word)
    if not parsed:
        return []
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_spk = parsed[0].get("speaker")
    for word in parsed:
        speaker = word.get("speaker")
        if current and speaker != current_spk:
            groups.append(current)
            current = []
            current_spk = speaker
        current.append(word)
    if current:
        groups.append(current)
    segments: list[dict[str, Any]] = []
    for group in groups:
        starts = [float(w["start"]) for w in group if "start" in w]
        ends = [float(w["end"]) for w in group if "end" in w]
        text = _join_words(group)
        if not text:
            continue
        seg: dict[str, Any] = {"text": text, "words": group}
        if starts:
            seg["start"] = min(starts)
        else:
            seg["start"] = 0.0
        if ends:
            seg["end"] = max(ends)
        else:
            seg["end"] = seg["start"]
        speaker = group[0].get("speaker")
        if speaker:
            seg["speaker"] = speaker
        segments.append(seg)
    return segments


def _split_spk_tags(text: str) -> list[tuple[str | None, str]]:
    stripped = text.strip()
    if not stripped:
        return []
    matches = list(_SPK_TAG_RE.finditer(stripped))
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


def _turn_from_obj(obj: dict[str, Any]) -> dict[str, Any] | None:
    text = obj.get("text") or obj.get("transcript") or obj.get("pred_text")
    if text is None or str(text).strip() == "":
        return None
    seg: dict[str, Any] = {"text": str(text).strip()}
    start = obj.get("start")
    end = obj.get("end")
    if start is None and end is None:
        start = 0.0
        end = 0.0
    if start is not None:
        seg["start"] = float(start)
    if end is not None:
        seg["end"] = float(end)
    if "speaker" in obj and obj.get("speaker") is not None:
        raw_speaker = obj.get("speaker")
    else:
        raw_speaker = obj.get("speaker_id")
    speaker = speaker_label(raw_speaker)
    if speaker:
        seg["speaker"] = speaker
    words = obj.get("words")
    if isinstance(words, list) and words:
        parsed = [_word_item(w) for w in words if isinstance(w, dict)]
        kept = [w for w in parsed if w is not None]
        if kept:
            seg["words"] = kept
    return seg


def _turn_list(data: dict[str, Any]) -> list[Any] | None:
    for key in ("turns", "speaker_turns", "extract_speaker_dict"):
        items = data.get(key)
        if isinstance(items, list) and items:
            return items
    return None


def segments_from_payload(data: Any) -> List[dict[str, Any]]:
    if isinstance(data, str):
        data = {"text": data}
    if isinstance(data, list):
        out: list[dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict):
                seg = _turn_from_obj(item)
                if seg is not None:
                    out.append(seg)
        return out
    if not isinstance(data, dict):
        return []

    ctc = _ctc_block(data)
    if ctc is not None:
        segs = segments_from_ctc_words(ctc["words"])
        if segs:
            return segs

    items = data.get("segments")
    if isinstance(items, list) and items:
        out = []
        for item in items:
            if isinstance(item, dict):
                seg = _turn_from_obj(item)
                if seg is not None:
                    out.append(seg)
        if out:
            return out

    turns = _turn_list(data)
    if turns is not None:
        out = []
        for item in turns:
            if isinstance(item, dict):
                seg = _turn_from_obj(item)
                if seg is not None:
                    out.append(seg)
        if out:
            return out

    text = _chat_content(data)
    tagged = _split_spk_tags(text) if text else []
    if tagged and any(label is not None for label, _body in tagged):
        out = []
        for label, body in tagged:
            seg: dict[str, Any] = {"text": body, "start": 0.0, "end": 0.0}
            if label:
                seg["speaker"] = label
            out.append(seg)
        return out
    if text.strip():
        return [{"text": text.strip(), "start": 0.0, "end": 0.0}]
    return []


def load_segments_from_path(path: Path) -> List[dict[str, Any]]:
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
            segments.extend(segments_from_payload(obj))
        return segments
    data = json.loads(stripped)
    return segments_from_payload(data)


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
