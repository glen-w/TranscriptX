"""Action-menu navigation must land on the right page with subject preselect."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.app.models.metadata import TranscriptMetadata
from transcriptx.web.action_menus.context import build_canonical_identity
from transcriptx.web.action_menus.handlers import HANDLERS
from transcriptx.web.action_menus.ids import ActionId, SectionId
from transcriptx.web.action_menus.services import (
    ACTION_NAV_PAGES,
    PAGE_ARTIFACTS,
    PAGE_CHARTS,
    PAGE_CORRECTIONS,
    PAGE_INSIGHTS,
    PAGE_LIBRARY,
    PAGE_OVERVIEW,
    PAGE_RUN_ANALYSIS,
    PAGE_SPEAKER_ID,
    PAGE_TRANSCRIPT,
    PAGE_TRANSCRIPT_PICKER_KEYS,
    apply_identity_to_session,
    go_rename,
    navigate_with_identity,
)
from transcriptx.web.navigation import (
    apply_library_rename_navigation,
    consume_library_transcript_nav,
)
from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.state import (
    LIBRARY_NAV_TRANSCRIPT_PATH,
    PAGE_KEY,
    RUN_SELECTOR_KEY,
    SUBJECT_ID_SELECTOR_KEY,
    SUBJECT_TYPE_SELECTOR_KEY,
    WORKFLOW_NAV_TRANSCRIPT_PATH,
)


def _transcript_identity(
    path: Path, *, slug: str | None = None, run_dir: Path | None = None
):
    kwargs = {
        "subject_type": "transcript",
        "subject_id": slug or path.stem,
        "transcript_path": path,
    }
    if run_dir is not None:
        kwargs["run_id"] = run_dir.name
        kwargs["run_dir"] = run_dir
    return build_canonical_identity(**kwargs)


def _stale_pickers() -> dict:
    return {key: 0 for key in PAGE_TRANSCRIPT_PICKER_KEYS} | {
        "run_analysis_target": "Group",
        "run_analysis_group": "stale-group",
        SUBJECT_ID_SELECTOR_KEY: "stale-subject",
        RUN_SELECTOR_KEY: "stale-run",
        SUBJECT_TYPE_SELECTOR_KEY: "Group",
    }


@pytest.fixture
def transcript_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    transcript = tmp_path / "meeting.json"
    transcript.write_text("{}", encoding="utf-8")
    other = tmp_path / "other.json"
    other.write_text("{}", encoding="utf-8")
    run_dir = tmp_path / "meeting-slug" / "20260101_120000"
    run_dir.mkdir(parents=True)

    monkeypatch.setattr(
        "transcriptx.web.services.transcript_context_resolver.load_index",
        lambda: {
            "transcripts": {
                "k": {
                    "slug": "meeting-slug",
                    "source_path": str(transcript),
                    "runs": [run_dir.name],
                }
            }
        },
    )
    monkeypatch.setattr(
        "transcriptx.web.action_menus.services.make_session_path_resolver",
        lambda: None,
    )
    monkeypatch.setattr(
        "transcriptx.web.navigation.make_session_path_resolver",
        lambda: None,
    )

    return SimpleNamespace(
        transcript=transcript,
        other=other,
        run_dir=run_dir,
        slug="meeting-slug",
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("action_id", "page"),
    [
        (ActionId.OPEN, PAGE_OVERVIEW),
        (ActionId.OPEN_TRANSCRIPT, PAGE_TRANSCRIPT),
        (ActionId.CHARTS, PAGE_CHARTS),
        (ActionId.ARTIFACTS, PAGE_ARTIFACTS),
        (ActionId.INSIGHTS, PAGE_INSIGHTS),
        (ActionId.RUN_SPEAKER_ID, PAGE_SPEAKER_ID),
        (ActionId.RUN_ANALYSIS, PAGE_RUN_ANALYSIS),
        (ActionId.CORRECTIONS, PAGE_CORRECTIONS),
    ],
)
def test_action_nav_pages_registry_matches_handlers(
    action_id: ActionId, page: str
) -> None:
    assert ACTION_NAV_PAGES[action_id.value] == page
    assert action_id in HANDLERS


@pytest.mark.unit
@pytest.mark.parametrize(
    "page",
    [
        PAGE_OVERVIEW,
        PAGE_TRANSCRIPT,
        PAGE_CHARTS,
        PAGE_ARTIFACTS,
        PAGE_INSIGHTS,
        PAGE_SPEAKER_ID,
        PAGE_RUN_ANALYSIS,
        PAGE_CORRECTIONS,
    ],
)
def test_navigate_with_identity_transcript_no_run_presets_subject_and_pickers(
    transcript_env, page: str
) -> None:
    ss = _stale_pickers()
    identity = _transcript_identity(transcript_env.transcript)
    navigate_with_identity(identity, page, session_state=ss)

    assert ss[PAGE_KEY] == page
    assert ss["subject_type"] == "transcript"
    assert ss["subject_id"] == transcript_env.slug
    assert ss["run_id"] is None
    assert ss["run_analysis_target"] == "Transcript"
    assert "run_analysis_group" not in ss
    for key in PAGE_TRANSCRIPT_PICKER_KEYS:
        assert key not in ss
    assert ss[SUBJECT_ID_SELECTOR_KEY] == transcript_env.slug
    assert RUN_SELECTOR_KEY not in ss
    assert ss[SUBJECT_TYPE_SELECTOR_KEY] == "Transcript"
    assert ss[WORKFLOW_NAV_TRANSCRIPT_PATH] == str(transcript_env.transcript)


@pytest.mark.unit
@pytest.mark.parametrize(
    "page",
    [PAGE_OVERVIEW, PAGE_CHARTS, PAGE_ARTIFACTS, PAGE_INSIGHTS, PAGE_TRANSCRIPT],
)
def test_navigate_with_identity_preserves_run_for_run_scoped_pages(
    transcript_env, page: str
) -> None:
    ss = _stale_pickers()
    identity = _transcript_identity(
        transcript_env.transcript,
        slug=transcript_env.slug,
        run_dir=transcript_env.run_dir,
    )
    navigate_with_identity(identity, page, session_state=ss)

    assert ss[PAGE_KEY] == page
    assert ss["subject_id"] == transcript_env.slug
    assert ss["run_id"] == transcript_env.run_dir.name
    for key in PAGE_TRANSCRIPT_PICKER_KEYS:
        assert key not in ss
    # Sidebar nav-bar pickers must show the navigated run so View links stay armed.
    assert ss[SUBJECT_ID_SELECTOR_KEY] == transcript_env.slug
    assert ss[RUN_SELECTOR_KEY] == transcript_env.run_dir.name
    assert ss[SUBJECT_TYPE_SELECTOR_KEY] == "Transcript"


@pytest.mark.unit
def test_navigate_with_identity_group_presets_run_analysis_target(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "group-uuid" / "run-1"
    run_dir.mkdir(parents=True)
    ss = _stale_pickers()
    ss["run_analysis_target"] = "Transcript"
    identity = build_canonical_identity(
        subject_type="group",
        subject_id="group-uuid",
        run_id=run_dir.name,
        run_dir=run_dir,
    )
    navigate_with_identity(identity, PAGE_RUN_ANALYSIS, session_state=ss)

    assert ss[PAGE_KEY] == PAGE_RUN_ANALYSIS
    assert ss["subject_type"] == "group"
    assert ss["subject_id"] == "group-uuid"
    assert ss["run_id"] == run_dir.name
    assert ss["run_analysis_target"] == "Group"
    assert ss["run_analysis_group"] == "group-uuid"
    assert "run_analysis_transcript" not in ss


@pytest.mark.unit
def test_navigate_with_identity_clears_stale_batch_target(
    transcript_env,
) -> None:
    """Identity Run Analysis must not leave a prior Batch target selected."""
    ss = _stale_pickers()
    ss["run_analysis_target"] = "Batch"
    identity = _transcript_identity(transcript_env.transcript)
    navigate_with_identity(identity, PAGE_RUN_ANALYSIS, session_state=ss)

    assert ss[PAGE_KEY] == PAGE_RUN_ANALYSIS
    assert ss["run_analysis_target"] == "Transcript"


@pytest.mark.unit
def test_navigate_with_identity_group_clears_stale_batch_target(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "group-uuid" / "run-1"
    run_dir.mkdir(parents=True)
    ss = _stale_pickers()
    ss["run_analysis_target"] = "Batch"
    identity = build_canonical_identity(
        subject_type="group",
        subject_id="group-uuid",
        run_id=run_dir.name,
        run_dir=run_dir,
    )
    navigate_with_identity(identity, PAGE_RUN_ANALYSIS, session_state=ss)

    assert ss["run_analysis_target"] == "Group"
    assert ss["run_analysis_group"] == "group-uuid"


@pytest.mark.unit
@pytest.mark.parametrize(
    "page",
    [PAGE_SPEAKER_ID, PAGE_RUN_ANALYSIS, PAGE_CORRECTIONS],
)
def test_picker_pages_resolve_default_index_after_navigation(
    monkeypatch: pytest.MonkeyPatch, transcript_env, page: str
) -> None:
    monkeypatch.setattr(
        SubjectService,
        "current_transcript_path",
        staticmethod(lambda _ss: str(transcript_env.transcript)),
    )
    ss = _stale_pickers()
    identity = _transcript_identity(transcript_env.transcript)
    navigate_with_identity(identity, page, session_state=ss)

    options = [str(transcript_env.other), str(transcript_env.transcript)]
    assert SubjectService.index_in_path_options(ss, options) == 2


@pytest.mark.unit
def test_open_library_with_path_sets_one_shot_library_preselect(
    monkeypatch: pytest.MonkeyPatch, transcript_env
) -> None:
    from transcriptx.web import navigation as nav_mod

    monkeypatch.setattr(
        nav_mod,
        "make_session_path_resolver",
        lambda: (lambda _p: (transcript_env.slug, None)),
    )
    ss: dict = {"library_transcript_select": 0}
    apply_library_rename_navigation(ss, transcript_env.transcript)
    ss[PAGE_KEY] = PAGE_LIBRARY

    assert ss[LIBRARY_NAV_TRANSCRIPT_PATH]
    assert ss["subject_id"] == transcript_env.slug

    transcripts = [
        TranscriptMetadata(path=transcript_env.other, base_name="other"),
        TranscriptMetadata(path=transcript_env.transcript, base_name="meeting"),
    ]
    consume_library_transcript_nav(ss, transcripts)
    assert LIBRARY_NAV_TRANSCRIPT_PATH not in ss
    assert ss["library_transcript_select"] == 2


@pytest.mark.unit
def test_go_rename_uses_library_rename_workflow(
    monkeypatch: pytest.MonkeyPatch, transcript_env
) -> None:
    import transcriptx.web.action_menus.services as services

    fake_ss: dict = {}
    called: dict = {}

    def _nav(ss, path):
        called["path"] = Path(path)
        ss[PAGE_KEY] = PAGE_LIBRARY
        ss[LIBRARY_NAV_TRANSCRIPT_PATH] = str(Path(path).resolve())

    monkeypatch.setattr(services, "navigate_to_library_rename_workflow", _nav)
    monkeypatch.setattr(services, "st", SimpleNamespace(session_state=fake_ss))

    identity = _transcript_identity(transcript_env.transcript, slug=transcript_env.slug)
    go_rename(identity)

    assert called["path"] == transcript_env.transcript
    assert fake_ss[PAGE_KEY] == PAGE_LIBRARY
    assert LIBRARY_NAV_TRANSCRIPT_PATH in fake_ss


@pytest.mark.unit
def test_open_library_without_path_uses_navigate_with_identity(
    transcript_env,
) -> None:
    ss = _stale_pickers()
    identity = build_canonical_identity(
        subject_type="transcript",
        subject_id=transcript_env.slug,
        transcript_path=None,
    )
    navigate_with_identity(identity, PAGE_LIBRARY, session_state=ss)
    assert ss[PAGE_KEY] == PAGE_LIBRARY
    assert ss["subject_id"] == transcript_env.slug
    assert "library_transcript_select" not in ss


@pytest.mark.unit
def test_export_zip_handler_has_no_page_navigation() -> None:
    assert ActionId.EXPORT_ZIP.value not in ACTION_NAV_PAGES
    assert HANDLERS[ActionId.EXPORT_ZIP].post_render is not None


@pytest.mark.unit
def test_apply_identity_does_not_regress_slug_to_stem(transcript_env) -> None:
    ss: dict = {}
    identity = _transcript_identity(transcript_env.transcript)  # subject_id = stem
    apply_identity_to_session(ss, identity)
    assert identity.subject_id == transcript_env.transcript.stem
    assert ss["subject_id"] == "meeting-slug"


@pytest.mark.unit
def test_action_menu_gui_sites_can_full_app_reload() -> None:
    """Every GUI action-menu strip must be able to navigate off-page.

    Fragment-hosted strips must use ``NavStyle.CLICK_RERUN`` (explicit app
    ``st.rerun`` after the button return). Non-fragment strips may use
    ``ON_CLICK`` (Streamlit full-app-reruns after the callback; never call
    ``st.rerun()`` inside ``on_click`` — it is a no-op warning).
    """
    from pathlib import Path

    import transcriptx.web.action_menus.handlers as handlers_mod
    import transcriptx.web.page_modules.batch_ops as batch_mod
    import transcriptx.web.page_modules.home as home_mod
    import transcriptx.web.page_modules.library as library_mod
    import transcriptx.web.page_modules.run_analysis as run_mod
    import transcriptx.web.page_modules.speaker_id as speaker_mod
    import transcriptx.web.page_modules.upload_transcript as import_mod

    # ON_CLICK: activate via on_click only — no st.rerun() in that branch.
    handler_src = Path(handlers_mod.__file__).read_text(encoding="utf-8")
    on_click_block = handler_src.split("if ctx.nav_style == NavStyle.ON_CLICK:", 1)[1]
    on_click_block = on_click_block.split("else:", 1)[0]
    assert "on_click=on_activate" in on_click_block
    assert "st.rerun()" not in on_click_block
    # CLICK_RERUN: button return path must still force full-app rerun.
    click_rerun_block = handler_src.split("if ctx.nav_style == NavStyle.ON_CLICK:", 1)[
        1
    ].split("else:", 1)[1]
    click_rerun_block = click_rerun_block.split("\ndef ", 1)[0]
    assert "on_activate()" in click_rerun_block
    assert "st.rerun()" in click_rerun_block

    # Library — strip lives inside ``_library_browser_fragment``.
    library_src = Path(library_mod.__file__).read_text(encoding="utf-8")
    lib_frag = library_src.split("def _library_browser_fragment", 1)[1]
    lib_frag = lib_frag.split("\ndef render_library", 1)[0]
    assert "render_configured_actions" in lib_frag
    assert "NavStyle.CLICK_RERUN" in lib_frag

    # Speaker ID — completion strip inside workspace fragment.
    speaker_src = Path(speaker_mod.__file__).read_text(encoding="utf-8")
    sid_frag = speaker_src.split("def _speaker_id_workspace_fragment", 1)[1]
    sid_frag = sid_frag.split("\ndef render_speaker_id_page", 1)[0]
    assert "_render_post_speaker_id_actions" in sid_frag
    post_fn = speaker_src.split("def _render_post_speaker_id_actions", 1)[1]
    post_fn = post_fn.split("\ndef ", 1)[0]
    assert post_fn.count("NavStyle.CLICK_RERUN") >= 2

    # Home — recent-run rows are outside any fragment (ON_CLICK ok).
    home_src = Path(home_mod.__file__).read_text(encoding="utf-8")
    assert "@st.fragment" not in home_src
    assert "render_recent_run_row" in home_src

    # Import — post-import strip is outside any fragment.
    import_src = Path(import_mod.__file__).read_text(encoding="utf-8")
    assert "@st.fragment" not in import_src
    assert "NavStyle.ON_CLICK" in import_src
    assert "SectionId.IMPORT_SUCCESS" in import_src

    # Run Analysis — post-run strip is outside the config fragment.
    run_src = Path(run_mod.__file__).read_text(encoding="utf-8")
    frag_start = run_src.index("def _run_analysis_config_and_launch_fragment")
    post_call = run_src.index("_render_post_analysis_actions()")
    assert post_call < frag_start
    assert "NavStyle.ON_CLICK" in run_src

    # Batch results — recent-run rows are outside the selection fragment.
    batch_src = Path(batch_mod.__file__).read_text(encoding="utf-8")
    batch_frag = batch_src.split("def _batch_ops_selection_fragment", 1)[1]
    batch_frag = batch_frag.split("\ndef ", 1)[0]
    assert "render_recent_run_row" not in batch_frag
    assert "render_recent_run_row" in batch_src

    # Catalogue sections covered by the sites above.
    assert set(SectionId) == {
        SectionId.HOME_RECENT_RUNS,
        SectionId.LIBRARY_SELECTED,
        SectionId.IMPORT_SUCCESS,
        SectionId.SPEAKER_ID_COMPLETE,
        SectionId.RUN_ANALYSIS_COMPLETE,
    }


@pytest.mark.unit
def test_corrections_studio_selectbox_uses_subject_default_index(
    monkeypatch: pytest.MonkeyPatch, transcript_env
) -> None:
    import transcriptx.web.page_modules.corrections_studio as mod

    captured: dict = {}

    class _St:
        session_state: dict = {}

        @staticmethod
        def markdown(*_a, **_k):
            return None

        @staticmethod
        def caption(*_a, **_k):
            return None

        @staticmethod
        def info(*_a, **_k):
            return None

        @classmethod
        def selectbox(cls, *_a, **kwargs):
            captured["index"] = kwargs.get("index")
            captured["key"] = kwargs.get("key")
            return kwargs.get("index", 0)

        @staticmethod
        def columns(_n):
            return (MagicMock(), MagicMock())

        @staticmethod
        def button(*_a, **_k):
            return False

    _St.session_state = {}
    navigate_with_identity(
        _transcript_identity(transcript_env.transcript),
        PAGE_CORRECTIONS,
        session_state=_St.session_state,
    )
    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        mod,
        "_cached_corrections_studio_transcripts",
        lambda: [
            SimpleNamespace(
                base_name="other",
                segment_count=1,
                path=transcript_env.other,
            ),
            SimpleNamespace(
                base_name="meeting",
                segment_count=2,
                path=transcript_env.transcript,
            ),
        ],
    )
    monkeypatch.setattr(mod, "CorrectionsStudioController", lambda: MagicMock())
    monkeypatch.setattr(
        "transcriptx.web.page_modules.corrections_studio.make_session_path_resolver",
        lambda: None,
    )
    monkeypatch.setattr(
        SubjectService,
        "current_transcript_path",
        staticmethod(lambda _ss: str(transcript_env.transcript)),
    )

    mod.render_corrections_studio()

    assert captured["key"] == "corrections_studio_transcript"
    assert captured["index"] == 2
