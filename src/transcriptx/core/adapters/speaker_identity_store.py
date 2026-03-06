"""
Speaker identity store adapters.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, cast


class SpeakerIdentityStore(ABC):
    @abstractmethod
    def load(self, transcript_key: str) -> Optional[Dict[str, object]]:
        raise NotImplementedError

    @abstractmethod
    def save(self, transcript_key: str, data: Dict[str, object]) -> None:
        raise NotImplementedError


class FileBasedSpeakerIdentityStore(SpeakerIdentityStore):
    def __init__(self, path: str | Path):
        self._path = Path(path)

    def load(self, transcript_key: str) -> Optional[Dict[str, object]]:
        if not self._path.exists():
            return None
        with open(self._path, "r", encoding="utf-8") as handle:
            data = cast(Dict[str, object], json.load(handle))
        value = data.get(transcript_key)
        return cast(Optional[Dict[str, object]], value)

    def save(self, transcript_key: str, data: Dict[str, object]) -> None:
        payload: Dict[str, object] = {}
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        payload[transcript_key] = data
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)


class DatabaseSpeakerIdentityStore(SpeakerIdentityStore):
    def load(self, transcript_key: str) -> Optional[Dict[str, object]]:
        return None

    def save(self, transcript_key: str, data: Dict[str, object]) -> None:
        return None
