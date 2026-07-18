"""Groups page thin Streamlit orchestration contracts (L3)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.core.domain.group import Group
from tests.web.streamlit_doubles import DummyColumn, DummyExpander, DummyHomeStreamlit


def _sample_group(
    *,
    group_id: str = "g-1",
    name: str = "Alpha",
    members: list[str] | None = None,
) -> Group:
    return Group(
        group_id=group_id,
        name=name,
        members=members or ["/tmp/a.json"],
        description="desc",
        created_at="2026-01-01",
        updated_at="2026-01-02",
    )


class _GroupsStreamlit(DummyHomeStreamlit):
    session_state: dict = {}
    button_returns: dict[str, bool] = {}
    multiselect_returns: dict[str, list] = {}
    selectbox_return: object = ""
    text_input_returns: dict[str, str] = {}
    errors: list[str] = []
    rerun_calls: int = 0

    @classmethod
    def reset(cls) -> None:
        cls.session_state = {}
        cls.button_returns = {}
        cls.multiselect_returns = {}
        cls.selectbox_return = ""
        cls.text_input_returns = {}
        cls.errors = []
        cls.rerun_calls = 0

    @staticmethod
    def fragment(fn=None, **_kwargs):
        if fn is None:

            def _decorator(f):
                return f

            return _decorator
        return fn

    @staticmethod
    def expander(*_a, **_k):
        return DummyExpander()

    @staticmethod
    def text_input(label, value="", key=None, **_kwargs):
        if key and key in _GroupsStreamlit.text_input_returns:
            return _GroupsStreamlit.text_input_returns[key]
        if key and key in _GroupsStreamlit.session_state:
            return str(_GroupsStreamlit.session_state[key])
        return value

    @staticmethod
    def text_area(*_a, **_k):
        return ""

    @classmethod
    def multiselect(cls, _label, options=None, default=None, key=None, **_kwargs):
        if key and key in cls.multiselect_returns:
            return cls.multiselect_returns[key]
        return list(default or [])

    @classmethod
    def button(cls, label, key=None, **_kwargs):
        if key and key in cls.button_returns:
            return cls.button_returns[key]
        return bool(cls.button_returns.get(label, False))

    @classmethod
    def selectbox(cls, *_a, **_k):
        return cls.selectbox_return

    @classmethod
    def error(cls, msg, **_kwargs):
        cls.errors.append(str(msg))

    @classmethod
    def rerun(cls):
        cls.rerun_calls += 1

    @staticmethod
    def write(*_a, **_k):
        return None

    @staticmethod
    def columns(_n):
        return (DummyColumn(), DummyColumn())

    @staticmethod
    def dataframe(*_a, **_k):
        return None


def _patch_groups_common(monkeypatch, mod) -> list:
    empty_calls: list = []
    _GroupsStreamlit.reset()
    monkeypatch.setattr(mod, "st", _GroupsStreamlit)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "render_empty_state",
        lambda *args, **kwargs: empty_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(mod, "set_page_flash", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "try_page_toast", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "clear_group_workspace_cache", lambda: None)
    monkeypatch.setattr(
        mod,
        "_cached_get_members",
        MagicMock(return_value=[], clear=MagicMock()),
    )
    return empty_calls


@pytest.mark.unit
def test_groups_empty_list_renders_empty_state(monkeypatch) -> None:
    import transcriptx.web.page_modules.groups as mod

    empty_calls = _patch_groups_common(monkeypatch, mod)
    monkeypatch.setattr(mod, "get_cached_list_transcripts", lambda: [])
    monkeypatch.setattr(mod, "cached_list_groups", lambda: [])
    monkeypatch.setattr(
        mod, "_render_create_group_transcripts_fragment", lambda *_a, **_k: None
    )

    mod.render_groups()

    assert empty_calls
    assert empty_calls[0][0][0] == "no_results_yet"
    assert "No groups yet" in empty_calls[0][0][1]


@pytest.mark.unit
def test_create_group_calls_service_and_clears_caches(monkeypatch) -> None:
    import transcriptx.web.page_modules.groups as mod

    _patch_groups_common(monkeypatch, mod)
    create_calls: list = []
    clear_calls: list = []

    group = _sample_group()
    monkeypatch.setattr(
        mod.GroupService,
        "create_group_with_status",
        lambda **kwargs: create_calls.append(kwargs) or (group, True),
    )
    monkeypatch.setattr(
        mod,
        "_clear_group_caches",
        lambda: clear_calls.append(True),
    )

    _GroupsStreamlit.session_state = {"create_group_name": "Alpha"}
    _GroupsStreamlit.multiselect_returns = {
        "create_group_transcripts": ["/tmp/a.json"],
    }
    _GroupsStreamlit.button_returns = {"create_group_submit": True}

    create_fn = getattr(
        mod._render_create_group_transcripts_fragment, "__wrapped__", None
    )
    assert create_fn is not None
    create_fn(["/tmp/a.json"], {"/tmp/a.json": "a"})

    assert create_calls
    assert create_calls[0]["transcript_refs"] == ["/tmp/a.json"]
    assert create_calls[0]["name"] == "Alpha"
    assert clear_calls
    assert _GroupsStreamlit.rerun_calls == 1


@pytest.mark.unit
def test_create_group_requires_transcripts(monkeypatch) -> None:
    import transcriptx.web.page_modules.groups as mod

    _patch_groups_common(monkeypatch, mod)
    _GroupsStreamlit.button_returns = {"create_group_submit": True}
    _GroupsStreamlit.multiselect_returns = {"create_group_transcripts": []}

    create_fn = mod._render_create_group_transcripts_fragment.__wrapped__
    create_fn(["/tmp/a.json"], {"/tmp/a.json": "a"})

    assert _GroupsStreamlit.errors
    assert "at least one transcript" in _GroupsStreamlit.errors[0]


@pytest.mark.unit
def test_rename_group_calls_service(monkeypatch) -> None:
    import transcriptx.web.page_modules.groups as mod

    empty_calls = _patch_groups_common(monkeypatch, mod)
    group = _sample_group()
    rename_calls: list = []
    monkeypatch.setattr(
        mod.GroupService,
        "rename_group",
        lambda gid, name: rename_calls.append((gid, name)) or group,
    )
    monkeypatch.setattr(mod, "_clear_group_caches", lambda: None)
    monkeypatch.setattr(
        mod,
        "_render_edit_membership_fragment",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(mod, "render_action_link", lambda *_a, **_k: False)

    _GroupsStreamlit.selectbox_return = group.group_id
    _GroupsStreamlit.text_input_returns = {
        f"group_rename_input_{group.group_id}": "Beta"
    }
    _GroupsStreamlit.button_returns = {f"rename_btn_{group.group_id}": True}

    detail = mod._groups_detail_fragment.__wrapped__
    detail(
        {group.group_id: group},
        {group.group_id: "Alpha • 1 transcripts"},
        ["/tmp/a.json"],
        {"/tmp/a.json": "a"},
        {"/tmp/a.json": "/tmp/a.json"},
    )

    assert rename_calls == [(group.group_id, "Beta")]
    assert _GroupsStreamlit.rerun_calls == 1
    assert empty_calls == []


@pytest.mark.unit
def test_delete_group_confirm_calls_service(monkeypatch) -> None:
    import transcriptx.web.page_modules.groups as mod

    _patch_groups_common(monkeypatch, mod)
    group = _sample_group()
    delete_calls: list = []
    monkeypatch.setattr(
        mod.GroupService,
        "delete_group",
        lambda gid: delete_calls.append(gid) or True,
    )
    monkeypatch.setattr(mod, "_clear_group_caches", lambda: None)
    monkeypatch.setattr(
        mod,
        "_render_edit_membership_fragment",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(mod, "render_action_link", lambda *_a, **_k: False)

    _GroupsStreamlit.selectbox_return = group.group_id
    _GroupsStreamlit.session_state = {f"confirm_delete_group_{group.group_id}": True}
    _GroupsStreamlit.button_returns = {f"confirm_del_{group.group_id}": True}

    detail = mod._groups_detail_fragment.__wrapped__
    detail(
        {group.group_id: group},
        {group.group_id: "Alpha • 1 transcripts"},
        ["/tmp/a.json"],
        {"/tmp/a.json": "a"},
        {"/tmp/a.json": "/tmp/a.json"},
    )

    assert delete_calls == [group.group_id]
    assert _GroupsStreamlit.rerun_calls == 1


@pytest.mark.unit
def test_view_group_in_subject_panel_sets_session(monkeypatch) -> None:
    import transcriptx.web.page_modules.groups as mod

    _patch_groups_common(monkeypatch, mod)
    group = _sample_group()
    monkeypatch.setattr(
        mod,
        "_render_edit_membership_fragment",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(mod, "render_action_link", lambda *_a, **_k: True)

    _GroupsStreamlit.selectbox_return = group.group_id
    _GroupsStreamlit.session_state = {}

    detail = mod._groups_detail_fragment.__wrapped__
    detail(
        {group.group_id: group},
        {group.group_id: "Alpha • 1 transcripts"},
        ["/tmp/a.json"],
        {"/tmp/a.json": "a"},
        {"/tmp/a.json": "/tmp/a.json"},
    )

    assert _GroupsStreamlit.session_state["subject_type"] == "group"
    assert _GroupsStreamlit.session_state["subject_id"] == group.group_id
    assert _GroupsStreamlit.session_state["page"] == "Overview"


@pytest.mark.unit
def test_groups_with_list_invokes_detail_fragment(monkeypatch) -> None:
    import transcriptx.web.page_modules.groups as mod

    _patch_groups_common(monkeypatch, mod)
    group = _sample_group()
    detail_calls: list = []
    monkeypatch.setattr(
        mod,
        "get_cached_list_transcripts",
        lambda: [SimpleNamespace(path="/tmp/a.json", base_name="a")],
    )
    monkeypatch.setattr(mod, "cached_list_groups", lambda: [group])
    monkeypatch.setattr(mod, "canonical_group_member_path", lambda p: str(p))
    monkeypatch.setattr(
        mod, "_render_create_group_transcripts_fragment", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        mod,
        "_groups_detail_fragment",
        lambda *args, **kwargs: detail_calls.append(args),
    )

    mod.render_groups()

    assert detail_calls
    assert group.group_id in detail_calls[0][0]
