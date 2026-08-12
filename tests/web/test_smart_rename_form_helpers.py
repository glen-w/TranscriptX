"""Light tests for smart rename form session helpers."""

from __future__ import annotations

from transcriptx.core.utils.rename.smart_name import append_token_to_name
from transcriptx.web.components.rename_form import (
    sticky_smart_rename_keys,
    sticky_suggested_name_keys,
)


def test_sticky_key_helpers() -> None:
    bound, target, suggestion = sticky_suggested_name_keys("import_rename_form")
    assert bound.endswith("__bound_path")
    assert target.endswith("__target")
    assert suggestion.endswith("__last_suggestion")
    bubbles, date_root = sticky_smart_rename_keys("import_rename_form")
    assert bubbles.endswith("__bubbles")
    assert date_root.endswith("__date_root")


def test_bubble_append_matches_smart_helper() -> None:
    assert append_token_to_name("260810_", "afternoon") == "260810_afternoon"
    assert append_token_to_name("260810_afternoon", "1") == "260810_afternoon_1"
