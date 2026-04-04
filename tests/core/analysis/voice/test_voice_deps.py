"""Unit tests for voice optional dependency checks (no heavy imports)."""

from __future__ import annotations

from unittest.mock import patch

from transcriptx.core.analysis.voice.deps import check_voice_optional_deps


@patch("transcriptx.core.analysis.voice.deps._missing_specs")
def test_egemaps_disabled_skips_opensmile_requirement(
    mock_missing: object,
) -> None:
    """When egemaps_enabled is False, opensmile is not required."""
    captured: list[list[str]] = []

    def _capture(packages: object) -> list[str]:
        captured.append(list(packages))  # type: ignore[arg-type]
        return []

    mock_missing.side_effect = _capture

    check_voice_optional_deps(egemaps_enabled=False)

    assert captured, "_missing_specs should have been called"
    assert "opensmile" not in captured[0]


@patch("transcriptx.core.analysis.voice.deps._missing_specs")
def test_egemaps_enabled_includes_opensmile_requirement(
    mock_missing: object,
) -> None:
    """When egemaps_enabled is True (default), opensmile is in the required set."""
    captured: list[list[str]] = []

    def _capture(packages: object) -> list[str]:
        captured.append(list(packages))  # type: ignore[arg-type]
        return []

    mock_missing.side_effect = _capture

    check_voice_optional_deps(egemaps_enabled=True)

    assert "opensmile" in captured[0]


def test_explicit_required_overrides_default_list() -> None:
    """Caller-supplied required list is used as-is."""
    out = check_voice_optional_deps(required=["only_this_pkg_xyz_123"])
    assert out["ok"] is False
    assert out["missing_optional_deps"] == ["only_this_pkg_xyz_123"]
