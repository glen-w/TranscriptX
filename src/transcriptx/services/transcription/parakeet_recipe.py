"""Pinned NeMo Parakeet (and Canary copy-command) docker recipe helpers.

The inner Python runs *inside* ``nvcr.io/nvidia/nemo:24.07.1``. Host tests must
not import NeMo; they assert argv and script text only.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_NEMO_IMAGE = "nvcr.io/nvidia/nemo:24.07.1"
PARAKEET_MODEL_DEFAULT = "nvidia/parakeet-tdt-0.6b-v3"
CANARY_MODEL_DEFAULT = "nvidia/canary-1b"
INNER_SCRIPT_NAME = "_parakeet_transcribe.py"
HF_CACHE_ENV = "TRANSCRIPTX_PARAKEET_HF_CACHE"

# Executed in the NeMo container. Writes JSONL {start,end,text} for nemo_json_to_whisperx.
PARAKEET_TRANSCRIBE_PY = """\
import json
import sys
from pathlib import Path

audio = Path(sys.argv[1])
jsonl = Path(sys.argv[2])
model_id = sys.argv[3]

import nemo.collections.asr as nemo_asr

model = nemo_asr.models.ASRModel.from_pretrained(model_name=model_id)
outputs = model.transcribe([str(audio)], timestamps=True)
hyp = outputs[0] if outputs else None
text = ""
segments = []
if hyp is not None:
    text = getattr(hyp, "text", None) or str(hyp)
    ts = getattr(hyp, "timestamp", None) or {}
    if isinstance(ts, dict):
        raw = ts.get("segment") or ts.get("segments") or []
        for item in raw:
            if not isinstance(item, dict):
                continue
            seg_text = item.get("segment") or item.get("text") or ""
            start = item.get("start")
            end = item.get("end")
            if start is None or end is None:
                continue
            segments.append(
                {
                    "start": float(start),
                    "end": float(end),
                    "text": str(seg_text).strip(),
                }
            )
if not any(seg.get("text") for seg in segments):
    segments = [{"start": 0.0, "end": 0.0, "text": str(text).strip()}]
jsonl.parent.mkdir(parents=True, exist_ok=True)
with jsonl.open("w", encoding="utf-8") as fh:
    for seg in segments:
        if not str(seg.get("text") or "").strip():
            continue
        fh.write(json.dumps(seg, ensure_ascii=False) + "\\n")
"""


def write_parakeet_inner_script(output_dir: Path) -> Path:
    """Write the container transcribe script next to job outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / INNER_SCRIPT_NAME
    path.write_text(PARAKEET_TRANSCRIBE_PY, encoding="utf-8")
    return path


def resolve_hf_cache_mount() -> str | None:
    raw = os.environ.get(HF_CACHE_ENV, "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return str(path) if path.is_dir() else None


def build_parakeet_docker_argv(
    *,
    docker_binary: str,
    image: str,
    audio_path: Path,
    output_dir: Path,
    model: str,
    device: str = "cuda",
    hf_cache: str | None = None,
) -> list[str]:
    """Host container argv. Audio parent is ``/audio``; outputs ``/output``."""
    audio_path = audio_path.resolve()
    output_dir = output_dir.resolve()
    stem = audio_path.stem
    jsonl_name = f"{stem}.jsonl"
    model_id = (model or "").strip() or PARAKEET_MODEL_DEFAULT
    image_id = (image or "").strip() or DEFAULT_NEMO_IMAGE
    cmd: list[str] = [str(docker_binary), "run", "--rm"]
    if (device or "").strip().lower() == "cuda":
        cmd.extend(["--gpus", "all"])
    cmd.extend(
        [
            "-v",
            f"{audio_path.parent}:/audio:ro",
            "-v",
            f"{output_dir}:/output",
        ]
    )
    cache = hf_cache if hf_cache is not None else resolve_hf_cache_mount()
    if cache:
        cmd.extend(["-v", f"{cache}:/root/.cache/huggingface"])
    cmd.extend(
        [
            image_id,
            "python",
            f"/output/{INNER_SCRIPT_NAME}",
            f"/audio/{audio_path.name}",
            f"/output/{jsonl_name}",
            model_id,
        ]
    )
    return cmd
