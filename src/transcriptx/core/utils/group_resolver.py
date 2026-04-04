"""
Resolve group identifiers to file-backed groups.
"""

from __future__ import annotations

from transcriptx.core.domain.group import Group
from transcriptx.core.services.group_service import GroupService


def resolve_group(identifier: str) -> Group:
    return GroupService.resolve_group_identifier(identifier)
