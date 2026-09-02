"""Guard: app/ and core/ must not import the Streamlit web package."""

from __future__ import annotations

from pathlib import Path


def test_app_and_core_do_not_import_web() -> None:
    src = Path(__file__).resolve().parents[2] / "src" / "transcriptx"
    forbidden: list[str] = []
    for folder in ("app", "core"):
        for path in (src / folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "from transcriptx.web" in text or "import transcriptx.web" in text:
                forbidden.append(str(path.relative_to(src)))
    assert forbidden == []
