"""Light tests for smart rename form session helpers."""

from __future__ import annotations

from transcriptx.core.utils.rename.smart_name import append_token_to_name
from transcriptx.web.components.rename_form import (
    _configured_rename_default_case,
    _default_rename_case_label,
    sticky_content_rename_keys,
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


def test_rename_default_case_from_config(monkeypatch) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(
        "transcriptx.core.utils.config_provider.get_config",
        lambda: SimpleNamespace(input=SimpleNamespace(rename_default_case="upper")),
    )
    assert _configured_rename_default_case() == "upper"
    assert _default_rename_case_label() == "UPPERCASE"


def test_sticky_content_rename_keys() -> None:
    options, pick, status = sticky_content_rename_keys("import_rename_form")
    assert options.endswith("__content_options")
    assert pick.endswith("__content_pick")
    assert status.endswith("__content_status")
