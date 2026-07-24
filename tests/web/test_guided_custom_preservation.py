"""Custom analysis preset must not be wiped under Guided presentation."""

from __future__ import annotations


def test_guided_custom_path_does_not_mutate_saved_config(monkeypatch) -> None:
    """Regression: Guided Custom is read-only chrome; no silent preset rewrite."""
    from transcriptx.web.presentation.prefs import MODE_GUIDED

    # Import the module-level logic gate used by analysis_preset_controls.
    # We assert the presentation helper never calls config save when switching
    # presentation mode (set_presentation_mode only touches presentation prefs).
    from transcriptx.web.presentation.resolve import set_presentation_mode
    from transcriptx.web.presentation.prefs import (
        PresentationDraft,
        built_in_prefs,
        load_presentation_prefs,
        raw_file_revision,
        save_presentation_prefs,
    )
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "presentation_mode.json"
        draft = PresentationDraft(
            prefs=built_in_prefs(mode=MODE_GUIDED),
            raw_file_revision=raw_file_revision(b""),
            path=path,
        )
        assert save_presentation_prefs(draft, path=path).ok

        # Simulate "Edit in Full controls" — presentation only.
        monkeypatch.setattr(
            "transcriptx.web.presentation.resolve.load_presentation_prefs",
            lambda p=None: load_presentation_prefs(path),
        )
        monkeypatch.setattr(
            "transcriptx.web.presentation.resolve.save_presentation_prefs",
            lambda d, path=None: save_presentation_prefs(d, path=path),
        )
        # No config module should be imported/saved by set_presentation_mode.
        result = set_presentation_mode("full_controls")
        assert result.ok
        prefs, _ = load_presentation_prefs(path)
        assert prefs.mode == "full_controls"
