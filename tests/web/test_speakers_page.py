"""Speakers page thin Streamlit orchestration contracts (L3)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.core.speaker_profiles.aggregates import ProfileListItem
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from tests.web.streamlit_doubles import DummyColumn, DummyHomeStreamlit


def _list_item(
    *,
    profile_id: str = "p1",
    name: str = "Ada Lovelace",
    status: str = "active",
    link_count: int = 1,
) -> ProfileListItem:
    return ProfileListItem(
        profile_id=profile_id,
        display_name=name,
        status=status,
        merged_into_profile_id=None,
        updated_at="2026-01-01T00:00:00+00:00",
        link_count=link_count,
    )


def _snap(*, listing: tuple[ProfileListItem, ...] = (), **overrides) -> SimpleNamespace:
    base = dict(
        incomplete=False,
        integrity_ok=True,
        listing=listing,
        profiles=(),
        aggregates_by_profile={},
        appearances_by_profile={},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _SpeakersStreamlit(DummyHomeStreamlit):
    session_state: dict = {}
    infos: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    metrics: list[tuple[str, object]] = []
    selectbox_return: object = ""

    @classmethod
    def reset(cls) -> None:
        cls.session_state = {}
        cls.infos = []
        cls.warnings = []
        cls.errors = []
        cls.metrics = []
        cls.selectbox_return = ""

    @staticmethod
    def fragment(fn=None, **_kwargs):
        if fn is None:

            def _decorator(f):
                return f

            return _decorator
        return fn

    @classmethod
    def info(cls, msg, **_kwargs):
        cls.infos.append(str(msg))

    @classmethod
    def warning(cls, msg, **_kwargs):
        cls.warnings.append(str(msg))

    @classmethod
    def error(cls, msg, **_kwargs):
        cls.errors.append(str(msg))

    @staticmethod
    def columns(n, *args, **kwargs):
        return [DummyColumn() for _ in range(int(n))]

    @classmethod
    def metric(cls, label, value, **_kwargs):
        cls.metrics.append((str(label), value))

    @classmethod
    def selectbox(cls, *_a, **_k):
        return cls.selectbox_return


@pytest.mark.unit
def test_speakers_empty_listing_renders_empty_state(monkeypatch, tmp_path) -> None:
    import transcriptx.web.page_modules.speakers as mod

    _SpeakersStreamlit.reset()
    empty_calls: list = []
    frag_calls: list = []

    monkeypatch.setattr(mod, "st", _SpeakersStreamlit)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "speaker_profiles_dir", lambda: tmp_path / "spk")
    monkeypatch.setattr(mod, "ensure_layout", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "build_aggregation_snapshot", lambda **_k: _snap())
    monkeypatch.setattr(mod, "_render_recovery_banners", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "render_empty_state",
        lambda *args, **kwargs: empty_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        mod,
        "_speakers_browser_fragment",
        lambda **kwargs: frag_calls.append(kwargs),
    )

    mod.render_speakers_page()

    assert empty_calls
    assert empty_calls[0][0][0] == "no_results_yet"
    assert "No speaker profiles yet" in empty_calls[0][0][1]
    assert frag_calls == []


@pytest.mark.unit
def test_speakers_incomplete_snapshot_warns_then_lists(monkeypatch, tmp_path) -> None:
    import transcriptx.web.page_modules.speakers as mod

    _SpeakersStreamlit.reset()
    item = _list_item()
    frag_calls: list = []

    monkeypatch.setattr(mod, "st", _SpeakersStreamlit)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "speaker_profiles_dir", lambda: tmp_path / "spk")
    monkeypatch.setattr(mod, "ensure_layout", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "build_aggregation_snapshot",
        lambda **_k: _snap(listing=(item,), incomplete=True, integrity_ok=False),
    )
    monkeypatch.setattr(mod, "_render_recovery_banners", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "_speakers_browser_fragment",
        lambda **kwargs: frag_calls.append(kwargs),
    )
    # Avoid DummyColumn.metric AttributeError — capture via columns mock.
    metrics: list[tuple[str, object]] = []

    class _Col:
        def metric(self, label, value, **_k):
            metrics.append((str(label), value))

    monkeypatch.setattr(_SpeakersStreamlit, "columns", staticmethod(lambda n, *a, **k: [_Col() for _ in range(int(n))]))

    mod.render_speakers_page()

    assert any("incomplete" in w.lower() for w in _SpeakersStreamlit.warnings)
    assert metrics == [("Active", 1)]
    assert len(frag_calls) == 1
    assert frag_calls[0]["options"] == ["p1"]
    assert frag_calls[0]["active_ids"] == ["p1"]
    assert "Ada Lovelace" in frag_calls[0]["labels"]["p1"]


@pytest.mark.unit
def test_speakers_filter_hides_all_when_only_archived(monkeypatch, tmp_path) -> None:
    import transcriptx.web.page_modules.speakers as mod

    _SpeakersStreamlit.reset()
    _SpeakersStreamlit.session_state = {"speakers_selected_profile": "archived-1"}
    archived = _list_item(profile_id="archived-1", name="Old Name", status="archived")

    monkeypatch.setattr(mod, "st", _SpeakersStreamlit)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "speaker_profiles_dir", lambda: tmp_path / "spk")
    monkeypatch.setattr(mod, "ensure_layout", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "build_aggregation_snapshot",
        lambda **_k: _snap(listing=(archived,)),
    )
    monkeypatch.setattr(mod, "_render_recovery_banners", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod, "_speakers_browser_fragment", lambda **_k: (_ for _ in ()).throw(AssertionError("fragment"))
    )

    class _Col:
        def metric(self, *_a, **_k):
            return None

    monkeypatch.setattr(_SpeakersStreamlit, "columns", staticmethod(lambda n, *a, **k: [_Col() for _ in range(max(int(n), 1))]))

    mod.render_speakers_page()

    assert any("No profiles match" in msg for msg in _SpeakersStreamlit.infos)
    assert _SpeakersStreamlit.session_state["speakers_selected_profile"] == ""


@pytest.mark.unit
def test_speakers_browser_opens_detail_for_selected_profile(monkeypatch) -> None:
    import transcriptx.web.page_modules.speakers as mod

    _SpeakersStreamlit.reset()
    _SpeakersStreamlit.selectbox_return = "p1"
    item = _list_item()
    profile = MagicMock(spec=SpeakerProfileV1)
    profile.profile_id = "p1"
    profile.status = "active"
    profile.display_name = "Ada Lovelace"
    agg = MagicMock()
    appearances = (MagicMock(),)
    snap = _snap(
        listing=(item,),
        profiles=(profile,),
        aggregates_by_profile={"p1": agg},
        appearances_by_profile={"p1": appearances},
    )

    overview_calls: list = []
    detail_calls: list = []

    monkeypatch.setattr(mod, "st", _SpeakersStreamlit)
    monkeypatch.setattr(
        mod,
        "_render_directory_overview",
        lambda *args, **kwargs: overview_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        mod,
        "_render_profile_detail",
        lambda *args, **kwargs: detail_calls.append((args, kwargs)),
    )

    mod._speakers_browser_fragment.__wrapped__(
        snap=snap,
        items=[item],
        labels={"p1": "Ada Lovelace (active · 1 links)"},
        options=["p1"],
        active_ids=["p1"],
        include_ignored=False,
    )

    assert overview_calls
    assert detail_calls
    _args, kwargs = detail_calls[0]
    assert kwargs["profile"] is profile
    assert kwargs["agg"] is agg
    assert kwargs["appearances"] is appearances

@pytest.mark.unit
def test_speakers_browser_missing_profile_errors(monkeypatch) -> None:
    import transcriptx.web.page_modules.speakers as mod

    _SpeakersStreamlit.reset()
    _SpeakersStreamlit.selectbox_return = "missing"
    item = _list_item()
    snap = _snap(listing=(item,), profiles=())

    monkeypatch.setattr(mod, "st", _SpeakersStreamlit)
    monkeypatch.setattr(mod, "_render_directory_overview", lambda *_a, **_k: None)
    detail_calls: list = []
    monkeypatch.setattr(
        mod, "_render_profile_detail", lambda *a, **k: detail_calls.append(True)
    )

    mod._speakers_browser_fragment.__wrapped__(
        snap=snap,
        items=[item],
        labels={"p1": "Ada"},
        options=["p1"],
        active_ids=["p1"],
        include_ignored=False,
    )

    assert any("missing from the snapshot" in e for e in _SpeakersStreamlit.errors)
    assert detail_calls == []


@pytest.mark.unit
def test_surname_sort_key_orders_by_surname() -> None:
    import transcriptx.web.page_modules.speakers as mod

    ada = _list_item(profile_id="a", name="Ada Lovelace")
    alan = _list_item(profile_id="b", name="Alan Turing")
    ordered = sorted([alan, ada], key=mod._surname_sort_key)
    assert [i.profile_id for i in ordered] == ["a", "b"]
