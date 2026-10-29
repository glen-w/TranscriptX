"""Local OpenAI-compatible client for NVIDIA Nemotron 3.5 Transcribe.

Talks to a user-started vLLM / NeMo Speech / NIM server on loopback.
Uses stdlib urllib — no ``openai`` package and no analysis-image weights.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

DEFAULT_MODEL = "nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B"
DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_TIMEOUT_SECONDS = 600
_AUDIO_MIME = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
    ".mp4": "audio/mp4",
}

SPEAKER_PROMPT = (
    "Transcribe this audio with punctuation and capitalization. "
    "Include all spoken words and verbal fillers. "
    "Write numbers in their standard written form. "
    "Put speaker tags <spk:0> <spk:1> <spk:2> <spk:3> on the transcription."
)
WRITTEN_PROMPT = (
    "Audio transcription. Language: as spoken. "
    "Wording: omit fillers and accidental repetitions; keep the remaining "
    "spoken wording unchanged. Formatting: punctuation and capitalization. "
    "Output: transcript only."
)


def default_base_url(env: Mapping[str, str] | None = None) -> str:
    merged = env if env is not None else os.environ
    raw = str(merged.get("TRANSCRIPTX_NEMOTRON_BASE_URL") or "").strip()
    return raw or DEFAULT_BASE_URL


def is_loopback_base_url(url: str) -> bool:
    """True for 127.0.0.1 / localhost / ::1 (no silent cloud NIM)."""
    parsed = urlparse(url if "://" in url else f"http://{url}")
    host = (parsed.hostname or "").strip().lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        info = socket.getaddrinfo(host, parsed.port or 80, type=socket.SOCK_STREAM)
    except (OSError, ValueError, socket.gaierror):
        return False
    for item in info:
        sockaddr = item[4]
        if not sockaddr:
            continue
        ip = sockaddr[0]
        if ip in {"127.0.0.1", "::1"} or str(ip).startswith("127."):
            return True
    return False


def allow_remote_endpoint(env: Mapping[str, str] | None = None) -> bool:
    merged = env if env is not None else os.environ
    return str(merged.get("TRANSCRIPTX_NEMOTRON_ALLOW_REMOTE") or "").strip() in {
        "1",
        "true",
        "yes",
        "on",
    }


def build_prompt(
    *,
    diarize: bool,
    keywords: Sequence[str] = (),
) -> str:
    prompt = SPEAKER_PROMPT if diarize else WRITTEN_PROMPT
    terms = [str(item).strip() for item in keywords if str(item).strip()]
    if terms:
        prompt = f"{prompt} Context terms: {', '.join(terms)}."
    return prompt


def _mime_for(path: Path) -> str:
    return _AUDIO_MIME.get(path.suffix.lower(), "application/octet-stream")


def _normalize_base_url(base_url: str) -> str:
    text = (base_url or "").strip() or DEFAULT_BASE_URL
    if not text.startswith(("http://", "https://")):
        text = "http://" + text
    return text.rstrip("/")


def completions_url(base_url: str) -> str:
    root = _normalize_base_url(base_url)
    if root.endswith("/chat/completions"):
        return root
    if root.endswith("/v1"):
        return root + "/chat/completions"
    return root + "/v1/chat/completions"


def models_url(base_url: str) -> str:
    root = _normalize_base_url(base_url)
    if root.endswith("/v1"):
        return root + "/models"
    if root.endswith("/chat/completions"):
        return root[: -len("/chat/completions")] + "/models"
    return root + "/v1/models"


def probe_endpoint(
    base_url: str,
    *,
    timeout_seconds: float = 2.0,
    env: Mapping[str, str] | None = None,
) -> tuple[bool, str]:
    """Return (reachable, message) for a local OpenAI-compatible server."""
    url = _normalize_base_url(base_url)
    if not is_loopback_base_url(url) and not allow_remote_endpoint(env):
        return (
            False,
            "Nemotron endpoint must be loopback "
            "(http://127.0.0.1:8000/v1); set "
            "TRANSCRIPTX_NEMOTRON_ALLOW_REMOTE=1 only for an explicit remote GPU.",
        )
    request = urllib.request.Request(models_url(url), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            if 200 <= int(response.status) < 300:
                return True, "endpoint reachable"
            return False, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403, 404}:
            return True, f"HTTP {exc.code} (server present)"
        return False, f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, str(getattr(exc, "reason", None) or exc)


def transcribe_file(
    audio_path: Path,
    *,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    diarize: bool = True,
    keywords: Sequence[str] = (),
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """POST one audio file; return the raw JSON dump (including timestamps)."""
    url = _normalize_base_url(base_url)
    if not is_loopback_base_url(url) and not allow_remote_endpoint(env):
        raise ValueError(
            "Refusing non-loopback Nemotron URL "
            f"{url!r}. Use 127.0.0.1 or set TRANSCRIPTX_NEMOTRON_ALLOW_REMOTE=1."
        )
    audio_path = audio_path.resolve()
    payload_audio = base64.b64encode(audio_path.read_bytes()).decode("ascii")
    mime = _mime_for(audio_path)
    prompt = build_prompt(diarize=diarize, keywords=keywords)
    body: dict[str, Any] = {
        "model": model.strip() or DEFAULT_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "audio_url",
                        "audio_url": {"url": f"data:{mime};base64,{payload_audio}"},
                    },
                ],
            }
        ],
        "temperature": 0,
        "top_p": 1.0,
        "max_tokens": 16384,
        "chat_template_kwargs": {"enable_thinking": False},
        "skip_special_tokens": False,
        "spaces_between_special_tokens": False,
        "seed": 0,
    }
    if diarize:
        body["mm_processor_kwargs"] = {"capture_ctc_timestamps": True}
    encoded = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        completions_url(url),
        data=encoded,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer EMPTY",
        },
    )
    try:
        with urllib.request.urlopen(
            request, timeout=timeout_seconds or DEFAULT_TIMEOUT_SECONDS
        ) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Nemotron HTTP {exc.code}: {detail[:500]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Nemotron request failed: {exc}") from exc
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("Nemotron response was not a JSON object")
    return data


def write_raw_dump(data: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output-raw", required=True, type=Path)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--diarize", action="store_true", default=True)
    parser.add_argument("--no-diarize", dest="diarize", action="store_false")
    parser.add_argument(
        "--keyword",
        action="append",
        default=[],
        help="Repeatable context term for the prompt.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    dump = transcribe_file(
        args.audio,
        base_url=args.base_url,
        model=args.model,
        diarize=bool(args.diarize),
        keywords=tuple(args.keyword or ()),
        timeout_seconds=int(args.timeout_seconds),
    )
    write_raw_dump(dump, args.output_raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
