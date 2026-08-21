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

    def metric(self, *_args, **_kwargs):
        return None

    def markdown(self, *_args, **_kwargs):
        return None

    def write(self, *_args, **_kwargs):
        return None

    def caption(self, *_args, **_kwargs):
        return None

    def button(self, *_args, **_kwargs):
        return False

    def checkbox(self, *_args, **_kwargs):
        return False

    def dataframe(self, *_args, **_kwargs):
        return None

    def expander(self, *_args, **_kwargs):
        return DummyExpander()

    def json(self, *_args, **_kwargs):
        return None


class DummyForm:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyExpander:
    """st.expander stand-in; ``open`` mirrors Streamlit 1.55+ dynamic expanders."""

    def __init__(self, open: bool | None = None) -> None:
        self.open = open

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyEmpty:
    """st.empty() stand-in; supports ``with slot.container():`` live panel refresh."""

    def container(self, *_args, **_kwargs):
        return DummyExpander()

    def markdown(self, *_args, **_kwargs):
        return None

    def info(self, *_args, **_kwargs):
        return None

    def empty(self):
        return self


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


class DummySelection:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.columns = []


class DummyDataframeEvent:
    def __init__(self, rows=None):
        self.selection = DummySelection(rows)


class DummyStreamlitWithDataframe:
    captured_df = None
    session_state: dict[str, object] = {}
    captions: list[str] = []
    selected_rows: list[int] = []
    button_presses: set[str] = set()
    button_labels: list[str] = []

    @staticmethod
    def markdown(*_args, **_kwargs):
        return None

    @staticmethod
    def info(*_args, **_kwargs):
        return None

    @classmethod
    def dataframe(cls, df, **_kwargs):
        cls.captured_df = df.copy()
        return DummyDataframeEvent(cls.selected_rows)

    @staticmethod
    def divider():
        return None

    @staticmethod
    def subheader(*_args, **_kwargs):
        return None

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
    def pills(cls, _label, options, key=None, **_kwargs):
        if key is not None and key in cls.session_state:
            current = cls.session_state[key]
            if current in options:
                return current
        return options[0] if options else None

    @classmethod
    def text_input(cls, *_args, key=None, **_kwargs):
        if key is not None and key in cls.session_state:
            return str(cls.session_state[key] or "")
        return str(_kwargs.get("value") or "")

    @staticmethod
    def popover(*_args, **_kwargs):
        return DummyForm()

    @staticmethod
    def columns(_n, **_kwargs):
        count = len(_n) if isinstance(_n, (list, tuple)) else int(_n)
        return tuple(DummyColumn() for _ in range(count))

    @classmethod
    def button(cls, label, key=None, **_kwargs):
        cls.button_labels.append(str(label))
        return bool(key and key in cls.button_presses)

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
    def form_submit_button(*_args, **_kwargs):
        return False

    @staticmethod
    def error(*_args, **_kwargs):
        return None

    @staticmethod
    def success(*_args, **_kwargs):
        return None

    @classmethod
    def toggle(cls, _label, *, value=False, key=None, **_kwargs):
        if key is not None and key in cls.session_state:
            return bool(cls.session_state[key])
        return value

    @staticmethod
    def expander(*_args, **_kwargs):
        return DummyForm()

    @staticmethod
    def fragment(fn=None, **_kwargs):
        if fn is None:

            def _decorator(f):
                return f

            return _decorator
        return fn


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
    def fragment(fn=None, **_kwargs):
        if fn is None:

            def _decorator(f):
                return f

            return _decorator
        return fn

    @staticmethod
    def subheader(*_args, **_kwargs):
        return None

    @staticmethod
    def columns(n, **_kwargs):
        count = len(n) if isinstance(n, (list, tuple)) else int(n)
        return tuple(DummyColumn() for _ in range(count))

    @staticmethod
    def markdown(*_args, **_kwargs):
        return None

    @staticmethod
    def write(*_args, **_kwargs):
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
    def rerun(*_args, **_kwargs):
        return None

    @classmethod
    def expander(
        cls,
        *_args,
        expanded: bool = False,
        key: str | None = None,
        on_change: str | object = "ignore",
        **_kwargs,
    ):
        if on_change == "ignore" or on_change is None:
            open_state: bool | None = None
        elif key is not None and key in cls.session_state:
            open_state = bool(cls.session_state[key])
        else:
            open_state = bool(expanded)
        return DummyExpander(open=open_state)

    @staticmethod
    def container(*_args, **_kwargs):
        return DummyExpander()

    @staticmethod
    def empty(*_args, **_kwargs):
        return DummyEmpty()

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

    @staticmethod
    def json(*_args, **_kwargs):
        return None

    @staticmethod
    def radio(_label, options, index=0, **_kwargs):
        return options[index]

    @classmethod
    def segmented_control(cls, _label, options, *, key=None, default=None, **_kwargs):
        if key is not None and key in cls.session_state:
            current = cls.session_state[key]
            if current in options:
                return current
        if default in options:
            return default
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
    def multiselect(cls, _label, options, default=None, key=None, **_kwargs):
        if key is not None and key in cls.session_state:
            return list(cls.session_state[key] or [])
        return list(default or [])

    @classmethod
    def slider(
        cls, _label, min_value=0.0, max_value=1.0, value=None, key=None, **_kwargs
    ):
        if key is not None and key in cls.session_state:
            return cls.session_state[key]
        if value is not None:
            return value
        return min_value

    @classmethod
    def toggle(cls, _label, *, value=False, key=None, **_kwargs):
        if key is not None and key in cls.session_state:
            return bool(cls.session_state[key])
        return value


class DummyRenameStreamlit:
    """Class-level session_state for rename service tests."""

    session_state: dict[str, object] = {}
