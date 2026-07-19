"""Input digest trio for group LLM synthesis."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from transcriptx.core.analysis.group_llm_synthesis.schemas import EMPTY_FILE_SENTINEL


@dataclass(frozen=True)
class InputDigests:
    global_collect_sha256: str
    speaker_rows_sha256: str
    combined_input_digest: str

    def as_dict(self) -> dict[str, str]:
        return {
            "global_collect_sha256": self.global_collect_sha256,
            "speaker_rows_sha256": self.speaker_rows_sha256,
            "combined_input_digest": self.combined_input_digest,
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | None) -> str:
    if path is None or not path.is_file():
        return EMPTY_FILE_SENTINEL
    return sha256_bytes(path.read_bytes())


def combined_input_digest(global_sha: str, speaker_sha: str) -> str:
    payload = f"{global_sha}\n{speaker_sha}".encode("ascii")
    return sha256_bytes(payload)


def compute_input_digests(
    *,
    global_collect_path: Path | None,
    speaker_rows_path: Path | None,
) -> InputDigests:
    global_sha = sha256_file(global_collect_path)
    speaker_sha = sha256_file(speaker_rows_path)
    return InputDigests(
        global_collect_sha256=global_sha,
        speaker_rows_sha256=speaker_sha,
        combined_input_digest=combined_input_digest(global_sha, speaker_sha),
    )
