from transcriptx.core.transcription_diagnostics import (  # type: ignore[import]
    check_model_loading_error,
    get_model_error_diagnostics,
)


def test_check_model_loading_error_ssl() -> None:
    is_error, kind = check_model_loading_error("SSL error: EOF occurred in violation")
    assert is_error is True
    assert kind == "ssl_error"


def test_check_model_loading_error_missing_model() -> None:
    stderr = "Unable to open file 'model.bin' (not found)"
    is_error, kind = check_model_loading_error(stderr)
    assert is_error is True
    assert kind == "missing_model"


def test_get_model_error_diagnostics_mentions_model() -> None:
    diagnostics = get_model_error_diagnostics("missing_model", "large-v2")
    assert "large-v2" in diagnostics
