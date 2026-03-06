"""
Module requirements resolver for pipeline gating.
"""

from __future__ import annotations

from typing import List, Tuple

from transcriptx.core.domain.canonical_transcript import TranscriptCapabilities
from transcriptx.core.domain.module_requirements import (
    Requirement,
    check_requirements_met,
)


class ModuleRequirementsResolver:
    def __init__(self, capabilities: TranscriptCapabilities, has_db: bool):
        self._capabilities = capabilities
        self._has_db = has_db

    def should_skip(self, requirements: List[Requirement]) -> Tuple[bool, List[str]]:
        met, missing = check_requirements_met(
            requirements, self._capabilities, self._has_db
        )
        return (not met, missing)
