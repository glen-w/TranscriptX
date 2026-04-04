from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from transcriptx.io.import_core.contracts import ImportOutcome, RankedCandidate


class ImportErrorBase(Exception):
    code = "import_error"


@dataclass
class UnsupportedImportError(ImportErrorBase):
    path: str
    outcome: ImportOutcome
    candidates: Sequence[RankedCandidate]

    code = "unsupported_import"

    def __str__(self) -> str:
        return f"Unsupported import for {self.path!r} ({self.outcome.value})"


@dataclass
class AmbiguousImportError(ImportErrorBase):
    path: str
    candidates: Sequence[RankedCandidate]

    code = "ambiguous_import"

    def __str__(self) -> str:
        ids = [c.adapter_id for c in self.candidates[:3]]
        return f"Ambiguous import for {self.path!r}; top candidates={ids}"


class MalformedImportError(ImportErrorBase):
    code = "malformed_import"
