"""
Resolve group identifiers to persisted groups (domain).
"""

from __future__ import annotations

from transcriptx.core.domain.group import Group
from transcriptx.core.services.group_service import GroupService


def resolve_group(identifier: str) -> Group:
    """
    Resolve an identifier to a Group domain object.

    Identifier can be UUID, deterministic key, or unique name.
    """
    return GroupService.resolve_group_identifier(identifier)
