from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional


class DiagnosticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class DiagnosticStage(str, Enum):
    PROBE = "probe"
    PARSE = "parse"
    NORMALIZE = "normalize"
    CANONICALIZE = "canonicalize"
    MANAGED = "managed"


@dataclass(frozen=True)
class ImportDiagnostic:
    code: str
    severity: DiagnosticSeverity
    stage: DiagnosticStage
    message: str
    location: Optional[str] = None
    recoverable: bool = True
    context: Mapping[str, Any] = field(default_factory=dict)
