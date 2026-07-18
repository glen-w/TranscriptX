"""Shared Streamlit test doubles for web layer tests."""

from __future__ import annotations


class DummySidebar:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyForm:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyExpander:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}
        self.query_params: dict[str, str] = {}
        self.sidebar = DummySidebar()

    @staticmethod
    def error(*_args, **_kwargs):
        return None

    @staticmethod
    def exception(*_args, **_kwargs):
        return None

    @staticmethod
    def rerun():
        return None

    @staticmethod
    def markdown(*_args, **_kwargs):
        return None

    @staticmethod
    def info(*_args, **_kwargs):
        return None


class DummyStreamlitWithDataframe:
    captured_df = None
    session_state: dict[str, object] = {}
    captions: list[str] = []

    @staticmethod
    def markdown(*_args, **_kwargs):
        return None

    @staticmethod
    def info(*_args, **_kwargs):
        return None

    @classmethod
    def dataframe(cls, df, **_kwargs):
        cls.captured_df = df.copy()
        return None

    @staticmethod
    def divider():
        return None

    @staticmethod
    def subheader(*_args, **_kwargs):
        return None

    @staticmethod
    def selectbox(*_args, **_kwargs):
        return 0

    @staticmethod
    def columns(_n):
        return (DummyColumn(), DummyColumn())

    @staticmethod
    def button(*_args, **_kwargs):
        return False

    @staticmethod
    def rerun():
        return None

    @classmethod
    def caption(cls, *_args, **_kwargs):
        cls.captions.append(_args[0] if _args else "")
        return None

    @staticmethod
    def form(*_args, **_kwargs):
        return DummyForm()

    @staticmethod
    def text_input(*_args, **_kwargs):
        return ""

    @staticmethod
    def form_submit_button(*_args, **_kwargs):
        return False

    @staticmethod
    def error(*_args, **_kwargs):
        return None

    @staticmethod
    def success(*_args, **_kwargs):
        return None

    @staticmethod
    def toggle(*_args, **_kwargs):
        return False

    @staticmethod
    def expander(*_args, **_kwargs):
        return DummyForm()


class DummySidebarStreamlit:
    session_state: dict[str, object] = {}
    captions: list[str] = []
    button_presses: set[str] = set()
    toggle_calls: list[tuple[str, str | None, bool]] = []

    @staticmethod
    def markdown(*_args, **_kwargs):
        return None

    @staticmethod
    def image(*_args, **_kwargs):
        return None

    @classmethod
    def button(cls, _label, key=None, **_kwargs):
        return bool(key and key in cls.button_presses)

    @staticmethod
    def rerun():
        return None

    @staticmethod
    def radio(_label, options, index=0, **_kwargs):
        return options[index]

    @classmethod
    def segmented_control(cls, _label, options, *, key=None, **_kwargs):
        if key is not None and key in cls.session_state:
            current = cls.session_state[key]
            if current in options:
                return current
        return options[0] if options else None

    @classmethod
    def selectbox(cls, _label, options, index=0, key=None, **_kwargs):
        if key is not None and key in cls.session_state:
            current = cls.session_state[key]
            if current in options:
                return current
        if options:
            return options[index]
        return None

    @classmethod
    def caption(cls, text, **_kwargs):
        cls.captions.append(text)
        return None

    @classmethod
    def toggle(cls, label, *, value=False, key=None, **_kwargs):
        cls.toggle_calls.append((label, key, value))
        if key is not None and key in cls.session_state:
            return bool(cls.session_state[key])
        return value


class DummyHomeStreamlit:
    session_state: dict[str, object] = {}

    @staticmethod
    def subheader(*_args, **_kwargs):
        return None

    @staticmethod
    def columns(n, **_kwargs):
        return tuple(DummyColumn() for _ in range(n))

    @staticmethod
    def markdown(*_args, **_kwargs):
        return None

    @staticmethod
    def divider():
        return None

    @staticmethod
    def caption(*_args, **_kwargs):
        return None

    @staticmethod
    def button(*_args, **_kwargs):
        return False

    @staticmethod
    def download_button(*_args, **_kwargs):
        return False

    @staticmethod
    def rerun():
        return None

    @staticmethod
    def expander(*_args, **_kwargs):
        return DummyExpander()

    @staticmethod
    def warning(*_args, **_kwargs):
        return None

    @staticmethod
    def error(*_args, **_kwargs):
        return None

    @staticmethod
    def info(*_args, **_kwargs):
        return None

    @staticmethod
    def metric(*_args, **_kwargs):
        return None

    @staticmethod
    def dataframe(*_args, **_kwargs):
        return None


class DummyRenameStreamlit:
    """Class-level session_state for rename service tests."""

    session_state: dict[str, object] = {}
