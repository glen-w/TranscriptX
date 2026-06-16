"""group_resolver delegates to GroupService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.domain.group import Group
from transcriptx.core.utils.group_resolver import resolve_group


@pytest.mark.unit
def test_resolve_group_delegates_to_group_service() -> None:
    g = MagicMock(spec=Group)
    with patch(
        "transcriptx.core.utils.group_resolver.GroupService.resolve_group_identifier",
        return_value=g,
    ) as m:
        out = resolve_group("my-id")
    assert out is g
    m.assert_called_once_with("my-id")
