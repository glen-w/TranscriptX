from transcriptx.core.config.validation import validate_config


def test_validate_config_type_error():
    config = {"analysis": {"sentiment_window_size": "bad"}}
    errors = validate_config(config)
    assert "analysis.sentiment_window_size" in errors
